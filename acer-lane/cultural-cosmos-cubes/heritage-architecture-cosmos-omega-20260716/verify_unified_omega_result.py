#!/usr/bin/env python3
"""Verify and optionally offset-index a native unified-Omega result.

The verifier is read-only toward input and native result artifacts. With
``--write-offset-index`` it may write only a companion offset HBI and its
SHA-256 sidecar. The native run is a geometric 8/12/20 shadow over one folded
stream, not a replay of the named domain/body-language map.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


SCHEMA = "ASOLARIA-UNIFIED-OMEGA-RESULT-VERIFIER-V1"
PROJECT = Path(__file__).resolve().parent
DEFAULT_INPUT = PROJECT / "artifacts" / "unified-training-input"
DEFAULT_RESULT = PROJECT / "artifacts" / "unified-omega-result"
EXPECTED_INPUT_PAYLOADS = 1025
EXPECTED_INPUT_SIDECARS = 1025
EXPECTED_SLICE_PAYLOADS = 1024
EXPECTED_TOTAL_CELLS = 60800
NATIVE_FILES = (
    "UNIFIED-OMEGA-RESULT.hbp",
    "UNIFIED-OMEGA-RESULT.hbp.sha256",
    "UNIFIED-OMEGA-RESULT.hbi",
    "UNIFIED-OMEGA-RESULT.hbi.sha256",
    "SHA256SUMS",
    "SHA256SUMS.sha256",
)
FAMILY_SPECS = {
    "CUBE_8POLE": {"bodies": 8, "epochs": 10, "cells": 800, "subomega": "omega_8"},
    "TRI_12SECTOR": {"bodies": 12, "epochs": 15, "cells": 1200, "subomega": "omega_12"},
    "PI_20LENS": {"bodies": 20, "epochs": 25, "cells": 2000, "subomega": "omega_pi"},
}
A_VIEW_NAMES = {
    "G_ID", "G_REV", "G_XORD", "G_ROT", "G_HALF", "G_BLKREV", "G_EVODD", "G_QPRISM",
}


class VerificationError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe(value: Any) -> str:
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, (list, tuple, set)):
        value = ",".join(str(item) for item in value)
    return urllib.parse.quote(str(value), safe="-._~,:;+/@[]")


def hbp_row(row_kind: str, **fields: Any) -> str:
    parts = [safe(row_kind)]
    for key in sorted(fields):
        parts.append(f"{safe(key)}={safe(fields[key])}")
    if "json" not in fields:
        parts.append("json=0")
    return "|".join(parts)


def parse_fields(text: str) -> tuple[str, dict[str, str]]:
    parts = text.split("|")
    kind = parts[0]
    fields: dict[str, str] = {}
    current_key: str | None = None
    for token in parts[1:]:
        if "=" in token:
            key, value = token.split("=", 1)
            if key in fields:
                raise VerificationError(f"duplicate field {key} in {kind}")
            fields[key] = value
            current_key = key
        elif current_key == "method":
            fields[current_key] += "|" + token
        elif token:
            if token in fields:
                raise VerificationError(f"duplicate bare flag {token} in {kind}")
            fields[token] = "1"
            current_key = None
    return kind, fields


@dataclass(frozen=True)
class ExactRow:
    number: int
    offset: int
    encoded: bytes
    raw: bytes
    text: str
    kind: str
    fields: dict[str, str]


def read_exact_lf_rows(path: Path) -> tuple[bytes, list[ExactRow]]:
    data = path.read_bytes()
    if b"\r" in data:
        raise VerificationError(f"CR byte found in LF-only artifact: {path}")
    if data and not data.endswith(b"\n"):
        raise VerificationError(f"missing final LF: {path}")
    rows: list[ExactRow] = []
    offset = 0
    for number, encoded in enumerate(data.splitlines(keepends=True), 1):
        if not encoded.endswith(b"\n"):
            raise VerificationError(f"unterminated row {number}: {path}")
        raw = encoded[:-1]
        text = raw.decode("utf-8")
        kind, fields = parse_fields(text)
        rows.append(ExactRow(number, offset, encoded, raw, text, kind, fields))
        offset += len(encoded)
    if offset != len(data):
        raise VerificationError(f"row walk did not cover artifact: {path}")
    return data, rows


def require_hex(value: str, length: int, label: str) -> str:
    lowered = value.lower()
    if len(lowered) != length:
        raise VerificationError(f"{label} length is not {length}: {value}")
    try:
        bytes.fromhex(lowered)
    except ValueError as error:
        raise VerificationError(f"{label} is not hexadecimal: {value}") from error
    return lowered


def integer(fields: dict[str, str], key: str, context: str) -> int:
    try:
        return int(fields[key])
    except (KeyError, ValueError) as error:
        raise VerificationError(f"invalid integer {context}.{key}") from error


def one(rows: Sequence[ExactRow], kind: str) -> ExactRow:
    matches = [row for row in rows if row.kind == kind]
    if len(matches) != 1:
        raise VerificationError(f"expected one {kind}, found {len(matches)}")
    return matches[0]


def verify_sidecar(target: Path) -> str:
    sidecar = target.with_name(target.name + ".sha256")
    if not sidecar.is_file():
        raise VerificationError(f"missing sidecar: {sidecar}")
    lines = sidecar.read_text(encoding="utf-8").splitlines()
    if len(lines) != 1:
        raise VerificationError(f"sidecar must contain one row: {sidecar}")
    parts = lines[0].split(None, 1)
    if len(parts) != 2:
        raise VerificationError(f"malformed sidecar: {sidecar}")
    expected = require_hex(parts[0], 64, f"sidecar hash {sidecar.name}")
    if parts[1].strip() != target.name:
        raise VerificationError(f"sidecar target mismatch: {sidecar}")
    actual = sha256_file(target)
    if expected != actual:
        raise VerificationError(f"sidecar SHA-256 mismatch: {target}")
    return actual


def write_sidecar(target: Path) -> Path:
    sidecar = target.with_name(target.name + ".sha256")
    sidecar.write_bytes(f"{sha256_file(target)}  {target.name}\n".encode("utf-8"))
    return sidecar


@dataclass(frozen=True)
class InputVerification:
    payload_names: tuple[str, ...]
    source_bytes: bytes
    shared_root_sha256: str
    slice_stream_sha256: str
    slice_corpus_root_sha256: str
    binding_rows: tuple[ExactRow, ...]
    claim_boundary: dict[str, str]
    objective_boundary: dict[str, str]


def verify_training_input(input_dir: Path) -> InputVerification:
    if not input_dir.is_dir():
        raise VerificationError(f"input directory missing: {input_dir}")
    if any(path.is_dir() for path in input_dir.iterdir()):
        raise VerificationError("trainer input contains a directory")
    files = sorted((path for path in input_dir.iterdir() if path.is_file()), key=lambda p: p.name)
    payloads = [path for path in files if not path.name.endswith(".sha256")]
    sidecars = [path for path in files if path.name.endswith(".sha256")]
    if len(payloads) != EXPECTED_INPUT_PAYLOADS or len(sidecars) != EXPECTED_INPUT_SIDECARS:
        raise VerificationError(
            f"input count mismatch: payloads={len(payloads)} sidecars={len(sidecars)}"
        )
    expected_sidecars = {path.name + ".sha256" for path in payloads}
    if {path.name for path in sidecars} != expected_sidecars:
        raise VerificationError("input sidecar set is not one-to-one with payloads")
    for payload in payloads:
        verify_sidecar(payload)
    payloads.sort(key=lambda path: path.name)
    if payloads[0].name != "0000-TRAINING-ROOTS.hbp":
        raise VerificationError("training-roots packet is not lexical payload zero")
    slices = [path for path in payloads if path.name.startswith("slice-")]
    if len(slices) != EXPECTED_SLICE_PAYLOADS or len(payloads) != len(slices) + 1:
        raise VerificationError("input must contain one binding packet plus 1,024 slices")
    source_bytes = b"".join(path.read_bytes() for path in payloads)
    shared_root = sha256_bytes(source_bytes)
    slice_data = [path.read_bytes() for path in slices]
    slice_hashes = [sha256_bytes(data) for data in slice_data]
    slice_stream = sha256_bytes(b"".join(slice_data))
    slice_corpus_root = sha256_bytes(b"".join(bytes.fromhex(value) for value in slice_hashes))

    _, binding_rows = read_exact_lf_rows(payloads[0])
    header = one(binding_rows, "TRAININGROOTSHDR").fields
    roots = one(binding_rows, "SOURCEROOTS").fields
    objectives = one(binding_rows, "OBJECTIVEROOTS").fields
    trainer = one(binding_rows, "TRAINERBINDING").fields
    execution = one(binding_rows, "EXECUTIONBOUNDARY").fields
    claims = one(binding_rows, "CLAIMBOUNDARY").fields
    if (
        integer(header, "source_files", "TRAININGROOTSHDR") != EXPECTED_SLICE_PAYLOADS
        or integer(header, "families", "TRAININGROOTSHDR") != 3
        or integer(header, "bodies", "TRAININGROOTSHDR") != 40
        or integer(header, "cells_planned", "TRAININGROOTSHDR") != EXPECTED_TOTAL_CELLS
        or header.get("claims_final_apex") != "0"
    ):
        raise VerificationError("training-root header contract mismatch")
    if (
        roots.get("source_stream_sha256") != slice_stream
        or roots.get("corpus_root_sha256") != slice_corpus_root
        or integer(roots, "slice_count", "SOURCEROOTS") != EXPECTED_SLICE_PAYLOADS
        or integer(roots, "slice_sha256_verified", "SOURCEROOTS") != EXPECTED_SLICE_PAYLOADS
        or integer(roots, "unique_slice_sha256", "SOURCEROOTS") != len(set(slice_hashes))
    ):
        raise VerificationError("binding source roots do not match staged slices")
    slice_bytes = integer(roots, "slice_bytes", "SOURCEROOTS")
    if any(len(data) != slice_bytes for data in slice_data):
        raise VerificationError("input slice byte-size mismatch")
    if trainer.get("load_rule") != "LEXICAL_TOP_LEVEL_NON_SHA256_CONCATENATION":
        raise VerificationError("trainer lexical load rule missing")
    if (
        objectives.get("pointer_semantics") != "CONTENT_ADDRESS_ONLY_NOT_EXECUTION"
        or objectives.get("objective_execution") != "0"
    ):
        raise VerificationError("objective execution boundary was not preserved")
    for key in (
        "external_model_calls", "external_gnn_calls", "live_gitram_ingestion",
        "live_omega_absorption", "paid_spend_usd", "promotion", "minting",
    ):
        if execution.get(key) != "0":
            raise VerificationError(f"execution boundary {key} is not zero")
    if execution.get("higher_floors") != "HELD":
        raise VerificationError("higher floors are not held")
    if (
        claims.get("identity_claim") != "NONE"
        or claims.get("uap_hypothesis_is_training_label") != "0"
        or "PHYSICAL_PROJECTION" not in claims.get("unverified", "")
    ):
        raise VerificationError("training claim boundary mismatch")
    return InputVerification(
        tuple(path.name for path in payloads), source_bytes, shared_root,
        slice_stream, slice_corpus_root, tuple(binding_rows), claims, objectives,
    )


def verify_native_files(result_dir: Path) -> tuple[Path, Path]:
    if not result_dir.is_dir():
        raise VerificationError(f"result directory missing: {result_dir}")
    for name in NATIVE_FILES:
        if not (result_dir / name).is_file():
            raise VerificationError(f"missing native result file: {name}")
    hbp = result_dir / "UNIFIED-OMEGA-RESULT.hbp"
    hbi = result_dir / "UNIFIED-OMEGA-RESULT.hbi"
    hbp_hash = verify_sidecar(hbp)
    hbi_hash = verify_sidecar(hbi)
    sums = result_dir / "SHA256SUMS"
    verify_sidecar(sums)
    sum_rows = [line for line in sums.read_text(encoding="utf-8").splitlines() if line]
    if len(sum_rows) != 2:
        raise VerificationError("native SHA256SUMS must contain exactly two rows")
    actual: dict[str, str] = {}
    for line in sum_rows:
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise VerificationError("malformed native SHA256SUMS row")
        actual[parts[1].strip()] = require_hex(parts[0], 64, "SHA256SUMS hash")
    expected = {
        "UNIFIED-OMEGA-RESULT.hbp": hbp_hash,
        "UNIFIED-OMEGA-RESULT.hbi": hbi_hash,
    }
    if actual != expected:
        raise VerificationError("native SHA256SUMS does not match HBP/HBI")
    return hbp, hbi


def verify_native_hbi(hbp: Path, hbi: Path) -> tuple[bytes, list[ExactRow]]:
    hbp_bytes, hbp_rows = read_exact_lf_rows(hbp)
    _, hbi_rows = read_exact_lf_rows(hbi)
    if len(hbi_rows) != len(hbp_rows):
        raise VerificationError("native HBI/HBP row-count mismatch")
    for expected_number, (source, index) in enumerate(zip(hbp_rows, hbi_rows), 1):
        if index.kind != "HBI":
            raise VerificationError(f"native HBI row kind mismatch: {index.number}")
        if integer(index.fields, "row", "HBI") != expected_number:
            raise VerificationError(f"native HBI row ordinal mismatch: {index.number}")
        if index.fields.get("sha256") != sha256_bytes(source.raw):
            raise VerificationError(f"native HBI row SHA mismatch: {index.number}")
        if index.fields.get("hex") != source.raw.hex():
            raise VerificationError(f"native HBI row hex mismatch: {index.number}")
        if index.fields.get("json") != "0":
            raise VerificationError(f"native HBI json boundary mismatch: {index.number}")
    return hbp_bytes, hbp_rows


def epoch_root(epoch: int, parent: str, leaves: Iterable[str]) -> str:
    material = bytearray(b"UNIFIED-OMEGA-V1\x00")
    material.extend(epoch.to_bytes(8, "little"))
    parent_bytes = parent.encode("utf-8")
    material.extend(len(parent_bytes).to_bytes(4, "little"))
    material.extend(parent_bytes)
    for leaf_value in sorted(leaves):
        encoded = leaf_value.encode("utf-8")
        material.extend(len(encoded).to_bytes(4, "little"))
        material.extend(encoded)
    return sha256_bytes(bytes(material))


def pid16(family: str, source_sha256: str) -> str:
    return sha256_bytes(f"UNI-BODY|{family}|{source_sha256}".encode("utf-8"))[:16]


def canonical_field_encoding(fields: Sequence[tuple[str, str]]) -> bytes:
    output = bytearray()
    for key, value in fields:
        key_bytes = key.encode("utf-8")
        value_bytes = value.encode("utf-8")
        output.extend(len(key_bytes).to_bytes(4, "little"))
        output.extend(key_bytes)
        output.extend(len(value_bytes).to_bytes(4, "little"))
        output.extend(value_bytes)
    return bytes(output)


def omnisubmit_lambda(
    seat: str, family: str, pid: str, cells: int, codebook: str, audit: str
) -> str:
    fields = (
        ("actor", seat), ("verb", "TRAIN"), ("family", family), ("pid", pid),
        ("cells", str(cells)), ("codebook", codebook), ("audit", audit),
        ("quorum", "SEAT_SINGLE"), ("omega_state", "closure"),
        ("claims_final_apex", "0"),
    )
    return sha256_bytes(b"UNIFIED-LEAF-V1\x00" + canonical_field_encoding(fields))


@dataclass(frozen=True)
class ResultVerification:
    shared_root_sha256: str
    omega_8: str
    omega_12: str
    omega_pi: str
    omega_unified: str
    cells: int
    accepted: int
    held: int
    gain_bytes: int
    bodies: int
    codebooks: int
    hbp_sha256: str
    claim_boundary: dict[str, str]


def verify_result_semantics(
    rows: Sequence[ExactRow],
    input_result: InputVerification,
    hbp_sha256: str,
    seat: str | None,
) -> ResultVerification:
    header = one(rows, "UNIFIEDHDR").fields
    shared_key_row = one(rows, "SHAREDKEY")
    shared_key = shared_key_row.fields
    if (
        header.get("schema") != "ASOLARIA-UNIFIED-OMEGA-8-12-PI-V1"
        or header.get("mode") != "SHADOW_MEASURED"
        or header.get("families") != "3"
        or header.get("shared_root_sha256") != input_result.shared_root_sha256
        or header.get("cube") != "8x800"
        or header.get("seam") != "12x1200"
        or header.get("hull") != "20x2000"
        or header.get("higher_floors") != "HELD"
        or header.get("claims_final_apex") != "0"
    ):
        raise VerificationError("UNIFIEDHDR contract mismatch")
    if (
        shared_key.get("law") != "one_reversible_codec_root"
        or "|k_body=H(root||family||index)|" not in shared_key_row.text
        or shared_key.get("all_bodies_distinct_languages") != "1"
        or shared_key.get("restore") != "byte_exact_state_match"
        or shared_key.get("not_quantum_entanglement") != "1"
    ):
        raise VerificationError("SHAREDKEY claim boundary mismatch")

    exact_kind_counts = {
        "FAMILYHDR": 3,
        "BODYHDR": 40,
        "LANGUAGE": 40,
        "GROUPGATE": 40,
        "AVIEW": 320,
        "DENSITY": 40,
        "BODYRESTORE": 40,
        "OMEGALEAF": 40,
        "OMNISUBMIT": 40,
        "OMEGAANCHOR": 3,
        "OMEGALEAFREF": 40,
        "FAMILYOMEGA": 3,
    }
    for row_kind, expected_count in exact_kind_counts.items():
        actual_count = sum(row.kind == row_kind for row in rows)
        if actual_count != expected_count:
            raise VerificationError(
                f"{row_kind} count mismatch: {actual_count} != {expected_count}"
            )
    family_row_kinds = set(exact_kind_counts)
    for row in rows:
        if row.kind in family_row_kinds and row.fields.get("family") not in FAMILY_SPECS:
            raise VerificationError(
                f"unknown family on {row.kind} row {row.number}: "
                f"{row.fields.get('family')}"
            )

    prefix_digests: dict[int, str] = {}
    prefix = hashlib.sha256()
    for row in rows:
        prefix_digests[row.number] = prefix.hexdigest()
        prefix.update(row.encoded)

    family_results: dict[str, dict[str, Any]] = {}
    all_codebooks: set[str] = set()
    total_cells = total_accepted = total_held = total_gain = total_bodies = 0
    for family, spec in FAMILY_SPECS.items():
        family_headers = [
            row for row in rows
            if row.kind == "FAMILYHDR" and row.fields.get("family") == family
        ]
        if len(family_headers) != 1:
            raise VerificationError(f"FAMILYHDR count mismatch: {family}")
        family_header = family_headers[0].fields
        if (
            integer(family_header, "bodies", family) != spec["bodies"]
            or integer(family_header, "epochs", family) != spec["epochs"]
            or integer(family_header, "cells_per_body", family) != spec["cells"]
            or family_header.get("shared_root") != input_result.shared_root_sha256
        ):
            raise VerificationError(f"FAMILYHDR semantic mismatch: {family}")

        body_data: dict[int, dict[str, Any]] = {}
        family_accepted = family_held = family_gain = 0
        source_length = len(input_result.source_bytes)
        for body in range(1, spec["bodies"] + 1):
            context = f"{family}.{body:02d}"

            def body_row(row_kind: str) -> ExactRow:
                matches = [
                    row for row in rows
                    if row.kind == row_kind
                    and row.fields.get("family") == family
                    and integer(row.fields, "body", row_kind) == body
                ]
                if len(matches) != 1:
                    raise VerificationError(
                        f"expected one {row_kind} for {context}, found {len(matches)}"
                    )
                return matches[0]

            body_header_row = body_row("BODYHDR")
            body_header = body_header_row.fields
            start = (body - 1) * source_length // spec["bodies"]
            end = body * source_length // spec["bodies"]
            partition = input_result.source_bytes[start:end]
            partition_sha = sha256_bytes(partition)
            codebook = require_hex(
                body_header.get("codebook_sha256", ""), 64, f"{context} codebook"
            )
            if (
                integer(body_header, "bytes", context) != len(partition)
                or integer(body_header, "glyphs", context) != (len(partition) * 8 + 9) // 10
                or body_header.get("src_sha256") != partition_sha
                or integer(body_header, "cells", context) != spec["cells"]
                or body_header.get("bits") != "10"
            ):
                raise VerificationError(f"body partition source mismatch: {context}")
            if codebook in all_codebooks:
                raise VerificationError(f"duplicate codebook: {context}")
            all_codebooks.add(codebook)

            language = body_row("LANGUAGE").fields
            if (
                language.get("law") != "LANGUAGE_GENESIS_V1"
                or language.get("codebook_sha256") != codebook
                or language.get("seeded_by") != "shared_root"
                or language.get("never_english") != "1"
            ):
                raise VerificationError(f"LANGUAGE mismatch: {context}")
            group = body_row("GROUPGATE").fields
            if (
                group.get("status") != "PASS"
                or group.get("sq") != "1,1,1"
                or group.get("comm") != "1,1,1"
                or group.get("distinct") != "8"
                or group.get("rnq") != "1"
            ):
                raise VerificationError(f"GROUPGATE mismatch: {context}")
            views = [
                row for row in rows
                if row.kind == "AVIEW"
                and row.fields.get("family") == family
                and integer(row.fields, "body", "AVIEW") == body
            ]
            if (
                len(views) != 8
                or {row.fields.get("a") for row in views} != A_VIEW_NAMES
                or any(row.fields.get("roundtrip") != "1" for row in views)
            ):
                raise VerificationError(f"AVIEW coverage mismatch: {context}")
            for view in views:
                require_hex(view.fields.get("view_sha256", ""), 64, f"{context} view")

            density = body_row("DENSITY").fields
            accepted = integer(density, "accepted", context)
            held = integer(density, "held", context)
            gain = integer(density, "gain_bytes", context)
            if (
                accepted + held != spec["cells"]
                or density.get("meaning") != "structure_repetition_only"
                or density.get("archive_ratio") != "NOT_CLAIMED"
            ):
                raise VerificationError(f"DENSITY mismatch: {context}")
            restore = body_row("BODYRESTORE").fields
            if restore.get("src_sha256") != partition_sha or restore.get("restore") != "1":
                raise VerificationError(f"BODYRESTORE mismatch: {context}")
            leaf_row = body_row("OMEGALEAF")
            leaf = require_hex(
                leaf_row.fields.get("leaf_sha256", ""), 64, f"{context} leaf"
            )
            if (
                leaf != prefix_digests[leaf_row.number]
                or integer(leaf_row.fields, "cells", context) != spec["cells"]
                or leaf_row.fields.get("restore") != "1"
            ):
                raise VerificationError(f"OMEGALEAF mismatch: {context}")
            submit = body_row("OMNISUBMIT").fields
            body_pid = pid16(family, partition_sha)
            lambda_value = require_hex(submit.get("lambda", ""), 64, f"{context} lambda")
            if submit.get("pid") != body_pid or submit.get("claims_final_apex") != "0":
                raise VerificationError(f"OMNISUBMIT mismatch: {context}")
            if seat is not None:
                expected_lambda = omnisubmit_lambda(
                    seat, family, body_pid, spec["cells"], codebook, leaf
                )
                if lambda_value != expected_lambda:
                    raise VerificationError(f"OMNISUBMIT lambda mismatch: {context}")

            body_data[body] = {"leaf": leaf, "codebook": codebook, "lambda": lambda_value}
            family_accepted += accepted
            family_held += held
            family_gain += gain
            total_cells += spec["cells"]
            total_accepted += accepted
            total_held += held
            total_gain += gain
            total_bodies += 1

        anchors = [
            row for row in rows
            if row.kind == "OMEGAANCHOR" and row.fields.get("family") == family
        ]
        refs = [
            row for row in rows
            if row.kind == "OMEGALEAFREF" and row.fields.get("family") == family
        ]
        omegas = [
            row for row in rows
            if row.kind == "FAMILYOMEGA" and row.fields.get("family") == family
        ]
        if len(anchors) != 1 or len(refs) != spec["bodies"] or len(omegas) != 1:
            raise VerificationError(f"family closure row count mismatch: {family}")
        anchor = anchors[0]
        if (
            anchor.fields.get("shared_root") != input_result.shared_root_sha256
            or anchor.fields.get("epoch") != "1"
            or integer(anchor.fields, "bodies", family) != spec["bodies"]
        ):
            raise VerificationError(f"OMEGAANCHOR mismatch: {family}")
        refs.sort(key=lambda row: integer(row.fields, "body", "OMEGALEAFREF"))
        if [integer(row.fields, "body", "OMEGALEAFREF") for row in refs] != list(
            range(1, spec["bodies"] + 1)
        ):
            raise VerificationError(f"OMEGALEAFREF body sequence mismatch: {family}")
        lambdas: list[str] = []
        for ref in refs:
            body = integer(ref.fields, "body", "OMEGALEAFREF")
            expected_body = body_data[body]
            if (
                ref.fields.get("leaf_sha256") != expected_body["leaf"]
                or ref.fields.get("codebook_sha256") != expected_body["codebook"]
                or ref.fields.get("lambda") != expected_body["lambda"]
            ):
                raise VerificationError(f"OMEGALEAFREF mismatch: {family}.{body:02d}")
            lambdas.append(expected_body["lambda"])
        family_material = anchor.raw + b"\n" + b"".join(ref.raw + b"\n" for ref in refs)
        family_omega = sha256_bytes(family_material)
        family_epoch = epoch_root(1, input_result.shared_root_sha256, lambdas)
        omega = omegas[0].fields
        if (
            omega.get("omega_sha256") != family_omega
            or omega.get("epoch_root") != family_epoch
            or integer(omega, "bodies", family) != spec["bodies"]
            or integer(omega, "accepted", family) != family_accepted
            or integer(omega, "held", family) != family_held
            or integer(omega, "gain_bytes", family) != family_gain
            or family_accepted + family_held != spec["bodies"] * spec["cells"]
        ):
            raise VerificationError(f"FAMILYOMEGA mismatch: {family}")
        family_results[family] = {
            "omega": family_omega,
            "epoch": family_epoch,
            "accepted": family_accepted,
            "held": family_held,
            "gain": family_gain,
        }

    if total_bodies != 40 or len(all_codebooks) != 40:
        raise VerificationError("40-body distinct-codebook invariant failed")
    if total_cells != EXPECTED_TOTAL_CELLS or total_accepted + total_held != total_cells:
        raise VerificationError("60,800-cell total invariant failed")

    subomegas = one(rows, "SUBOMEGAS").fields
    for family, spec in FAMILY_SPECS.items():
        if subomegas.get(spec["subomega"]) != family_results[family]["omega"]:
            raise VerificationError(f"SUBOMEGAS mismatch: {family}")
    omega_values = [family_results[family]["omega"] for family in FAMILY_SPECS]
    unified_expected = epoch_root(1, input_result.shared_root_sha256, omega_values)
    unified = one(rows, "UNIFIEDOMEGA").fields
    if (
        unified.get("omega_unified") != unified_expected
        or unified.get("method")
        != "H(D||e||shared_root||sorted[omega_8,omega_12,omega_pi])"
        or integer(unified, "families", "UNIFIEDOMEGA") != 3
        or integer(unified, "bodies", "UNIFIEDOMEGA") != 40
        or integer(unified, "cells", "UNIFIEDOMEGA") != total_cells
        or integer(unified, "accepted", "UNIFIEDOMEGA") != total_accepted
        or integer(unified, "held", "UNIFIEDOMEGA") != total_held
        or integer(unified, "gain_bytes", "UNIFIEDOMEGA") != total_gain
    ):
        raise VerificationError("UNIFIEDOMEGA mismatch")
    held_boundary = one(rows, "HELD").fields
    if (
        held_boundary.get("no_physics_claims") != "1"
        or held_boundary.get("owning_gate") != "UNVERIFIED"
        or held_boundary.get("omega_gnn") != "SPEC_ONLY"
        or not held_boundary.get("claims_final_apex", "").startswith("0")
    ):
        raise VerificationError("HELD claim boundary mismatch")
    footer = one(rows, "UNIFIEDFTR").fields
    if (
        footer.get("status") != "PASS"
        or footer.get("omega_unified") != unified_expected
        or integer(footer, "families", "UNIFIEDFTR") != 3
        or integer(footer, "bodies", "UNIFIEDFTR") != 40
        or integer(footer, "cells", "UNIFIEDFTR") != total_cells
        or integer(footer, "accepted", "UNIFIEDFTR") != total_accepted
        or integer(footer, "held", "UNIFIEDFTR") != total_held
    ):
        raise VerificationError("UNIFIEDFTR mismatch")
    return ResultVerification(
        shared_root_sha256=input_result.shared_root_sha256,
        omega_8=family_results["CUBE_8POLE"]["omega"],
        omega_12=family_results["TRI_12SECTOR"]["omega"],
        omega_pi=family_results["PI_20LENS"]["omega"],
        omega_unified=unified_expected,
        cells=total_cells,
        accepted=total_accepted,
        held=total_held,
        gain_bytes=total_gain,
        bodies=total_bodies,
        codebooks=len(all_codebooks),
        hbp_sha256=hbp_sha256,
        claim_boundary={
            "mode": "GEOMETRIC_SHADOW_8_12_20_FULL_STREAM",
            "named_domain_body_alignment": "NOT_ESTABLISHED_BY_NATIVE_TRAINER",
            "named_domain_language_replay": "NOT_ESTABLISHED_BY_NATIVE_TRAINER",
            "objective_execution": "0",
            "physical_mechanism": "UNVERIFIED",
            "identity_claim": "NONE",
            "uap_hypothesis_is_training_label": "0",
            "no_physics_claims": "1",
        },
    )


def write_offset_index(result_dir: Path, hbp: Path, rows: Sequence[ExactRow]) -> Path:
    index_rows = [
        hbp_row(
            "HBIHDR",
            schema=SCHEMA,
            target=hbp.name,
            target_bytes=hbp.stat().st_size,
            target_sha256=sha256_file(hbp),
            rows=len(rows),
            encoding="UTF8_NO_BOM",
            line_endings="LF",
            row_hash_scope="EXACT_ROW_BYTES_INCLUDING_LF",
            mode="GEOMETRIC_SHADOW_8_12_20_FULL_STREAM",
            named_domain_language_replay="NOT_ESTABLISHED_BY_NATIVE_TRAINER",
            objective_execution=0,
            physical_mechanism="UNVERIFIED",
            identity_claim="NONE",
        )
    ]
    for row in rows:
        index_rows.append(
            hbp_row(
                "HBIOFF",
                schema=SCHEMA,
                row=row.number,
                off=row.offset,
                len=len(row.encoded),
                target_row_kind=row.kind,
                row_sha256=sha256_bytes(row.encoded),
                row_hex=row.encoded.hex(),
            )
        )
    output = result_dir / "UNIFIED-OMEGA-RESULT.offsets.hbi"
    output.write_bytes(("\n".join(index_rows) + "\n").encode("utf-8"))
    write_sidecar(output)
    return output


def verify_all(
    input_dir: Path,
    result_dir: Path,
    write_offsets: bool = False,
    seat: str | None = None,
) -> ResultVerification:
    input_result = verify_training_input(input_dir)
    hbp, hbi = verify_native_files(result_dir)
    _, rows = verify_native_hbi(hbp, hbi)
    result = verify_result_semantics(rows, input_result, sha256_file(hbp), seat)
    if write_offsets:
        write_offset_index(result_dir, hbp, rows)
    return result


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--result-dir", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--write-offset-index", action="store_true")
    parser.add_argument(
        "--seat", help="optional seat PID for recomputing every OMNISUBMIT lambda"
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = verify_all(
            args.input_dir.resolve(), args.result_dir.resolve(),
            write_offsets=args.write_offset_index, seat=args.seat,
        )
    except (OSError, UnicodeError, VerificationError) as error:
        print(
            hbp_row(
                "UNIFIEDVERIFY", schema=SCHEMA, status="FAIL",
                error=str(error), wrote_offset_index=0,
            ),
            file=sys.stderr,
        )
        return 1
    print(
        hbp_row(
            "UNIFIEDVERIFY",
            schema=SCHEMA,
            status="PASS",
            shared_root_sha256=result.shared_root_sha256,
            bodies=result.bodies,
            codebooks=result.codebooks,
            cells=result.cells,
            accepted=result.accepted,
            held=result.held,
            gain_bytes=result.gain_bytes,
            omega_8=result.omega_8,
            omega_12=result.omega_12,
            omega_pi=result.omega_pi,
            omega_unified=result.omega_unified,
            result_sha256=result.hbp_sha256,
            wrote_offset_index=int(args.write_offset_index),
        )
    )
    print(hbp_row("UNIFIEDVERIFYBOUNDARY", schema=SCHEMA, **result.claim_boundary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
