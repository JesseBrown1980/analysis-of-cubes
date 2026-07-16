#!/usr/bin/env python3
"""Build the cold-body to geometric-body language bridge.

The bridge is deliberately narrow:

* H01..H08 map by ordinal to CUBE_8POLE body 01..08.
* A01..A12 map by ordinal to TRI_12SECTOR body 01..12.
* P01..P20 map by ordinal to PI_20LENS body 01..20.

It does not claim that any named domain body trained a geometric body
exclusively.  The geometric families partition the whole shared stream.
The cold XOR-SHA256 language and geometric LANGUAGE_GENESIS_V1 codebook are
separate language layers and are never equated.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


SCHEMA = "ASOLARIA-UNIFIED-BODY-LANGUAGE-BRIDGE-V1"
PROJECT = Path(__file__).resolve().parent
DEFAULT_BODY_MAP = PROJECT / "BODY-MAP.hbp"
DEFAULT_COLD_LANGUAGES = (
    PROJECT / "artifacts" / "cold-corpus-v2" / "receipts" / "BODY-LANGUAGES.hbp"
)
DEFAULT_UNIFIED_RESULT = (
    PROJECT / "artifacts" / "unified-omega-result" / "UNIFIED-OMEGA-RESULT.hbp"
)
DEFAULT_OUTPUT_DIR = PROJECT
DEFAULT_STEM = "UNIFIED-BODY-LANGUAGE-BRIDGE"

HEX64 = re.compile(r"^[0-9a-f]{64}$")

FAMILY_BRIDGES: dict[str, tuple[str, str, int, int]] = {
    "HERITAGE_8": ("H", "CUBE_8POLE", 8, 800),
    "ARCHITECTURE_12": ("A", "TRI_12SECTOR", 12, 1200),
    "ASTRONOMY_PI_20": ("P", "PI_20LENS", 20, 2000),
}


@dataclass(frozen=True)
class ParsedRow:
    kind: str
    fields: dict[str, str]
    raw: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_token(value: Any) -> str:
    text = str(int(value) if isinstance(value, bool) else value)
    return (
        text.replace("%", "%25")
        .replace("|", "%7C")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
    )


def hbp_row(kind: str, **fields: Any) -> str:
    parts = [safe_token(kind)]
    for key in sorted(fields):
        parts.append(f"{safe_token(key)}={safe_token(fields[key])}")
    if "json" not in fields:
        parts.append("json=0")
    return "|".join(parts)


def parse_hbp_line(line: str) -> ParsedRow:
    raw = line.rstrip("\r\n")
    parts = raw.split("|")
    fields: dict[str, str] = {}
    for token in parts[1:]:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        fields[key] = value
    return ParsedRow(parts[0], fields, raw)


def read_stable_rows(path: Path) -> tuple[bytes, list[ParsedRow]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    before = path.stat()
    data = path.read_bytes()
    after = path.stat()
    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        raise RuntimeError(f"input changed while being read: {path}")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError(f"input is not UTF-8: {path}") from exc
    rows = [parse_hbp_line(line) for line in text.splitlines() if line.strip()]
    if not rows:
        raise RuntimeError(f"input has no HBP rows: {path}")
    return data, rows


def one_row(rows: Sequence[ParsedRow], kind: str) -> ParsedRow:
    matches = [row for row in rows if row.kind == kind]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one {kind} row, found {len(matches)}")
    return matches[0]


def int_field(row: ParsedRow, name: str) -> int:
    try:
        return int(row.fields[name])
    except (KeyError, ValueError) as exc:
        raise RuntimeError(f"{row.kind} missing integer field {name}") from exc


def require_field(row: ParsedRow, name: str, expected: str | None = None) -> str:
    try:
        value = row.fields[name]
    except KeyError as exc:
        raise RuntimeError(f"{row.kind} missing field {name}") from exc
    if expected is not None and value != expected:
        raise RuntimeError(
            f"{row.kind} field {name}={value!r}; expected {expected!r}"
        )
    return value


def require_sha(value: str, context: str) -> str:
    lowered = value.lower()
    if not HEX64.fullmatch(lowered):
        raise RuntimeError(f"invalid SHA-256 for {context}: {value!r}")
    return lowered


def verify_optional_sidecar(path: Path) -> None:
    sidecar = path.with_name(path.name + ".sha256")
    if not sidecar.is_file():
        return
    tokens = sidecar.read_text(encoding="utf-8").split()
    if len(tokens) < 2:
        raise RuntimeError(f"malformed SHA-256 sidecar: {sidecar}")
    if tokens[0].lower() != sha256_file(path):
        raise RuntimeError(f"SHA-256 sidecar mismatch: {path}")
    if tokens[1] != path.name:
        raise RuntimeError(f"SHA-256 sidecar target mismatch: {sidecar}")


def validate_body_map(
    rows: Sequence[ParsedRow],
) -> tuple[list[dict[str, str]], ParsedRow]:
    header = one_row(rows, "BODYMAP")
    if int_field(header, "total") != 40:
        raise RuntimeError("BODYMAP total must be 40")
    if require_field(header, "codec") != "XOR_SHA256_CTR":
        raise RuntimeError("BODYMAP codec must be XOR_SHA256_CTR")
    objective = one_row(rows, "OBJECTIVECARRIAGEMAP")
    if require_field(objective, "execution") != "0":
        raise RuntimeError("objective carriage must remain reference-only")
    if require_field(objective, "live_absorption") != "0":
        raise RuntimeError("objective carriage live absorption must remain zero")
    if require_field(objective, "promotion") != "0":
        raise RuntimeError("objective carriage promotion must remain zero")

    bodies = [dict(row.fields) for row in rows if row.kind == "BODY"]
    if len(bodies) != 40:
        raise RuntimeError(f"BODY-MAP requires 40 BODY rows, found {len(bodies)}")
    seen_ids: set[str] = set()
    for family, (prefix, _geometric, expected_count, expected_cells) in (
        FAMILY_BRIDGES.items()
    ):
        members = sorted(
            (body for body in bodies if body.get("family") == family),
            key=lambda body: int(body["ordinal"]),
        )
        if len(members) != expected_count:
            raise RuntimeError(
                f"{family} requires {expected_count} bodies, found {len(members)}"
            )
        for ordinal, body in enumerate(members, 1):
            expected_id = f"{prefix}{ordinal:02d}"
            if body.get("body_id") != expected_id:
                raise RuntimeError(
                    f"{family} ordinal {ordinal} must be {expected_id}, "
                    f"found {body.get('body_id')}"
                )
            if int(body.get("ordinal", "-1")) != ordinal:
                raise RuntimeError(f"{expected_id} ordinal mismatch")
            if int(body.get("passes", "-1")) != expected_cells:
                raise RuntimeError(f"{expected_id} pass count mismatch")
            if not body.get("name"):
                raise RuntimeError(f"{expected_id} has no body name")
            if expected_id in seen_ids:
                raise RuntimeError(f"duplicate body ID: {expected_id}")
            seen_ids.add(expected_id)
    return bodies, objective


def validate_cold_languages(
    rows: Sequence[ParsedRow], bodies: Sequence[dict[str, str]]
) -> dict[str, dict[str, str]]:
    header = one_row(rows, "BODYLANGUAGES")
    if int_field(header, "bodies") != 40:
        raise RuntimeError("BODYLANGUAGES bodies must be 40")
    require_field(header, "codec", "XOR_SHA256_CTR")
    require_field(header, "historical_language_is_not_cube_codec", "1")
    require_field(header, "roundtrip_required", "1")
    require_sha(
        require_field(header, "system_binding_root"), "cold system binding root"
    )

    language_rows = [row for row in rows if row.kind == "BODYLANGUAGE"]
    if len(language_rows) != 40:
        raise RuntimeError(
            f"BODY-LANGUAGES requires 40 BODYLANGUAGE rows, found "
            f"{len(language_rows)}"
        )
    by_id: dict[str, dict[str, str]] = {}
    language_ids: set[str] = set()
    seed_hashes: set[str] = set()
    map_by_id = {body["body_id"]: body for body in bodies}
    for row in language_rows:
        body_id = require_field(row, "body_id")
        if body_id in by_id:
            raise RuntimeError(f"duplicate cold language body ID: {body_id}")
        if body_id not in map_by_id:
            raise RuntimeError(f"cold language body not in BODY-MAP: {body_id}")
        require_field(row, "codec", "XOR_SHA256_CTR")
        require_field(row, "roundtrip", "1")
        language_id = require_field(row, "local_language_id")
        seed = require_sha(
            require_field(row, "language_seed_sha256"),
            f"{body_id} cold language seed",
        )
        if language_id in language_ids:
            raise RuntimeError(f"duplicate cold local language ID: {language_id}")
        if seed in seed_hashes:
            raise RuntimeError(f"duplicate cold language seed: {seed}")
        language_ids.add(language_id)
        seed_hashes.add(seed)
        mapped = map_by_id[body_id]
        if require_field(row, "family") != mapped["family"]:
            raise RuntimeError(f"{body_id} cold family mismatch")
        if require_field(row, "body_name") != mapped["name"]:
            raise RuntimeError(f"{body_id} cold body name mismatch")
        if int_field(row, "passes") != int(mapped["passes"]):
            raise RuntimeError(f"{body_id} cold pass count mismatch")
        by_id[body_id] = dict(row.fields)
    if set(by_id) != set(map_by_id):
        raise RuntimeError("BODY-MAP and BODY-LANGUAGES body sets differ")
    return by_id


def validate_unified_result(
    rows: Sequence[ParsedRow],
) -> tuple[
    dict[tuple[str, int], dict[str, str]],
    dict[str, int],
    str,
    str,
]:
    header = one_row(rows, "UNIFIEDHDR")
    require_field(header, "schema", "ASOLARIA-UNIFIED-OMEGA-8-12-PI-V1")
    require_field(header, "families", "3")
    require_field(header, "claims_final_apex", "0")
    shared_root = require_sha(
        require_field(header, "shared_root_sha256"), "geometric shared root"
    )

    unified = one_row(rows, "UNIFIEDOMEGA")
    if int_field(unified, "bodies") != 40:
        raise RuntimeError("UNIFIEDOMEGA bodies must be 40")
    if int_field(unified, "cells") != 60800:
        raise RuntimeError("UNIFIEDOMEGA cells must be 60800")
    omega_unified = require_sha(
        require_field(unified, "omega_unified"), "unified Omega"
    )

    footer = one_row(rows, "UNIFIEDFTR")
    require_field(footer, "status", "PASS")
    if int_field(footer, "bodies") != 40:
        raise RuntimeError("UNIFIEDFTR bodies must be 40")
    if int_field(footer, "cells") != 60800:
        raise RuntimeError("UNIFIEDFTR cells must be 60800")
    if require_sha(
        require_field(footer, "omega_unified"), "footer unified Omega"
    ) != omega_unified:
        raise RuntimeError("UNIFIEDOMEGA and UNIFIEDFTR roots differ")

    family_headers = {
        require_field(row, "family"): row
        for row in rows
        if row.kind == "FAMILYHDR"
    }
    body_headers: dict[tuple[str, int], dict[str, str]] = {}
    languages: dict[tuple[str, int], dict[str, str]] = {}
    codebooks: set[str] = set()
    for row in rows:
        if row.kind not in {"BODYHDR", "LANGUAGE"}:
            continue
        family = require_field(row, "family")
        body_number = int_field(row, "body")
        key = (family, body_number)
        target = body_headers if row.kind == "BODYHDR" else languages
        if key in target:
            raise RuntimeError(f"duplicate {row.kind} row: {family}/{body_number}")
        target[key] = dict(row.fields)

    family_byte_totals: dict[str, int] = {}
    for _named, (_prefix, geometric, count, cells) in FAMILY_BRIDGES.items():
        family_header = family_headers.get(geometric)
        if family_header is None:
            raise RuntimeError(f"missing FAMILYHDR: {geometric}")
        if int_field(family_header, "bodies") != count:
            raise RuntimeError(f"{geometric} body count mismatch")
        if int_field(family_header, "cells_per_body") != cells:
            raise RuntimeError(f"{geometric} cell count mismatch")
        if require_sha(
            require_field(family_header, "shared_root"),
            f"{geometric} shared root",
        ) != shared_root:
            raise RuntimeError(f"{geometric} shared root mismatch")
        byte_total = 0
        for ordinal in range(1, count + 1):
            key = (geometric, ordinal)
            body = body_headers.get(key)
            language = languages.get(key)
            if body is None or language is None:
                raise RuntimeError(f"missing geometric body/language: {key}")
            if int(body.get("cells", "-1")) != cells:
                raise RuntimeError(f"{key} cells mismatch")
            body_bytes = int(body.get("bytes", "0"))
            if body_bytes <= 0:
                raise RuntimeError(f"{key} must contain shared-stream bytes")
            byte_total += body_bytes
            body_codebook = require_sha(
                body.get("codebook_sha256", ""), f"{key} body codebook"
            )
            body["src_sha256"] = require_sha(
                body.get("src_sha256", ""), f"{key} body source"
            )
            require_field(
                ParsedRow("LANGUAGE", language, ""),
                "law",
                "LANGUAGE_GENESIS_V1",
            )
            language_codebook = require_sha(
                language.get("codebook_sha256", ""), f"{key} language codebook"
            )
            if body_codebook != language_codebook:
                raise RuntimeError(f"{key} codebook mismatch")
            if body_codebook in codebooks:
                raise RuntimeError(f"duplicate geometric codebook: {body_codebook}")
            codebooks.add(body_codebook)
            body["codebook_sha256"] = body_codebook
            body["language_law"] = "LANGUAGE_GENESIS_V1"
        family_byte_totals[geometric] = byte_total

    if len(body_headers) != 40 or len(languages) != 40:
        raise RuntimeError("unified result must contain exactly 40 body/language rows")
    if len(set(family_byte_totals.values())) != 1:
        raise RuntimeError(
            "geometric family byte totals differ; whole shared-stream partition "
            f"not established: {family_byte_totals}"
        )
    return body_headers, family_byte_totals, shared_root, omega_unified


def build_mapping_rows(
    bodies: Sequence[dict[str, str]],
    cold_languages: dict[str, dict[str, str]],
    geometric_bodies: dict[tuple[str, int], dict[str, str]],
) -> list[str]:
    rows: list[str] = []
    for body in sorted(
        bodies,
        key=lambda item: (
            list(FAMILY_BRIDGES).index(item["family"]),
            int(item["ordinal"]),
        ),
    ):
        named_family = body["family"]
        _prefix, geometric_family, _count, expected_cells = FAMILY_BRIDGES[
            named_family
        ]
        ordinal = int(body["ordinal"])
        cold = cold_languages[body["body_id"]]
        geometric = geometric_bodies[(geometric_family, ordinal)]
        rows.append(
            hbp_row(
                "BODYLANGUAGEBRIDGE",
                body_id=body["body_id"],
                body_name=body["name"],
                bridge_semantics="ORDINAL_CONFIGURATION_ONLY",
                cold_codec="XOR_SHA256_CTR",
                cold_language_id=cold["local_language_id"],
                cold_language_seed_sha256=cold["language_seed_sha256"],
                cold_roundtrip=1,
                domain_exclusive_training=0,
                geometric_body=f"{ordinal:02d}",
                geometric_body_bytes=geometric["bytes"],
                geometric_body_src_sha256=geometric["src_sha256"],
                geometric_cells=geometric["cells"],
                geometric_codebook_sha256=geometric["codebook_sha256"],
                geometric_family=geometric_family,
                geometric_language_law="LANGUAGE_GENESIS_V1",
                geometric_stream_scope="WHOLE_SHARED_STREAM_PARTITION",
                historical_decipherment=0,
                historical_translation=0,
                language_layers_distinct=1,
                layers_equated=0,
                named_family=named_family,
                objectives_executed=0,
                objectives_referenced=1,
                ordinal=ordinal,
                passes=expected_cells,
            )
        )
    return rows


def write_lf_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".tmp-{os.getpid()}")
    temp.write_bytes(data)
    os.replace(temp, path)


def write_sidecar_atomic(path: Path) -> Path:
    sidecar = path.with_name(path.name + ".sha256")
    write_lf_atomic(
        sidecar, f"{sha256_file(path)}  {path.name}\n".encode("utf-8")
    )
    return sidecar


def write_bundle_atomic(
    output_dir: Path, stem: str, rows: Iterable[str]
) -> tuple[Path, Path, Path]:
    encoded_rows = [(row.rstrip("\r\n") + "\n").encode("utf-8") for row in rows]
    hbp = output_dir / f"{stem}.hbp"
    hbi = output_dir / f"{stem}.hbi"
    whole_hex = output_dir / f"{stem}.hbp.hex"

    body = b"".join(encoded_rows)
    write_lf_atomic(hbp, body)
    index_rows = [
        hbp_row(
            "HBIHDR",
            encoding="UTF8_NO_BOM",
            line_endings="LF",
            rows=len(encoded_rows),
            schema=SCHEMA,
            target=hbp.name,
            target_bytes=len(body),
            target_sha256=sha256_bytes(body),
        )
    ]
    offset = 0
    for row_number, encoded in enumerate(encoded_rows, 1):
        index_rows.append(
            hbp_row(
                "HBIROW",
                len=len(encoded),
                off=offset,
                row=row_number,
                row_hex=encoded.hex(),
                row_sha256=sha256_bytes(encoded),
            )
        )
        offset += len(encoded)
    write_lf_atomic(hbi, ("\n".join(index_rows) + "\n").encode("utf-8"))
    write_lf_atomic(whole_hex, (body.hex() + "\n").encode("utf-8"))
    for path in (hbp, hbi, whole_hex):
        write_sidecar_atomic(path)
    verify_bundle(output_dir, stem)
    return hbp, hbi, whole_hex


def verify_sidecar(path: Path) -> None:
    sidecar = path.with_name(path.name + ".sha256")
    if not sidecar.is_file():
        raise RuntimeError(f"missing sidecar: {sidecar}")
    tokens = sidecar.read_text(encoding="utf-8").split()
    if len(tokens) < 2:
        raise RuntimeError(f"malformed sidecar: {sidecar}")
    if tokens[0].lower() != sha256_file(path):
        raise RuntimeError(f"sidecar hash mismatch: {path}")
    if tokens[1] != path.name:
        raise RuntimeError(f"sidecar target mismatch: {sidecar}")


def verify_bundle(output_dir: Path, stem: str) -> int:
    hbp = output_dir / f"{stem}.hbp"
    hbi = output_dir / f"{stem}.hbi"
    whole_hex = output_dir / f"{stem}.hbp.hex"
    for path in (hbp, hbi, whole_hex):
        if not path.is_file():
            raise RuntimeError(f"missing bridge artifact: {path}")
        verify_sidecar(path)
    body = hbp.read_bytes()
    if bytes.fromhex(whole_hex.read_text(encoding="utf-8").strip()) != body:
        raise RuntimeError("whole-file hexadecimal mirror mismatch")
    cursor = 0
    indexed = 0
    header_rows: int | None = None
    header_hash: str | None = None
    for line in hbi.read_text(encoding="utf-8").splitlines():
        row = parse_hbp_line(line)
        if row.kind == "HBIHDR":
            header_rows = int_field(row, "rows")
            header_hash = require_sha(
                require_field(row, "target_sha256"), "HBI target"
            )
            if int_field(row, "target_bytes") != len(body):
                raise RuntimeError("HBI target byte count mismatch")
            continue
        if row.kind != "HBIROW":
            continue
        offset = int_field(row, "off")
        length = int_field(row, "len")
        if offset != cursor:
            raise RuntimeError("HBI has a byte gap or overlap")
        chunk = body[offset : offset + length]
        if len(chunk) != length:
            raise RuntimeError("HBI row extends beyond HBP")
        if sha256_bytes(chunk) != require_sha(
            require_field(row, "row_sha256"), "HBI row"
        ):
            raise RuntimeError("HBI row hash mismatch")
        if chunk.hex() != require_field(row, "row_hex").lower():
            raise RuntimeError("HBI row hex mismatch")
        cursor += length
        indexed += 1
    if cursor != len(body):
        raise RuntimeError("HBI does not cover the HBP")
    if header_rows != indexed:
        raise RuntimeError("HBI indexed-row count mismatch")
    if header_hash != sha256_bytes(body):
        raise RuntimeError("HBI target hash mismatch")
    return indexed


def build_bridge(
    body_map_path: Path,
    cold_languages_path: Path,
    unified_result_path: Path,
    output_dir: Path,
    stem: str = DEFAULT_STEM,
) -> dict[str, Any]:
    body_map_data, body_map_rows = read_stable_rows(body_map_path)
    cold_data, cold_rows = read_stable_rows(cold_languages_path)
    unified_data, unified_rows = read_stable_rows(unified_result_path)
    for path in (body_map_path, cold_languages_path, unified_result_path):
        verify_optional_sidecar(path)

    bodies, objective = validate_body_map(body_map_rows)
    cold_languages = validate_cold_languages(cold_rows, bodies)
    cold_header = one_row(cold_rows, "BODYLANGUAGES")
    geometric, byte_totals, shared_root, omega_unified = (
        validate_unified_result(unified_rows)
    )
    mapping_rows = build_mapping_rows(bodies, cold_languages, geometric)
    if len(mapping_rows) != 40:
        raise RuntimeError("bridge mapping must contain exactly 40 rows")
    bridge_root = sha256_bytes(
        b"".join((row + "\n").encode("utf-8") for row in mapping_rows)
    )
    shared_stream_bytes = next(iter(byte_totals.values()))

    family_rows = []
    for named_family, (_prefix, geometric_family, count, cells) in (
        FAMILY_BRIDGES.items()
    ):
        family_rows.append(
            hbp_row(
                "BRIDGEFAMILY",
                bodies=count,
                bridge_semantics="ORDINAL_CONFIGURATION_ONLY",
                cells_per_body=cells,
                domain_exclusive_training=0,
                geometric_family=geometric_family,
                geometric_partition_bytes=byte_totals[geometric_family],
                geometric_stream_scope="WHOLE_SHARED_STREAM_PARTITION",
                named_family=named_family,
            )
        )

    header = hbp_row(
        "UBLBRIDGEHDR",
        bodies=40,
        body_map_sha256=sha256_bytes(body_map_data),
        bridge_map_root_sha256=bridge_root,
        claim="ORDINAL_CONFIGURATION_BRIDGE_ONLY",
        cold_codec="XOR_SHA256_CTR",
        cold_languages_sha256=sha256_bytes(cold_data),
        cold_system_binding_root_sha256=require_sha(
            require_field(cold_header, "system_binding_root"),
            "cold system binding root",
        ),
        families=3,
        geometric_language_law="LANGUAGE_GENESIS_V1",
        geometric_shared_root_sha256=shared_root,
        geometric_shared_stream_bytes=shared_stream_bytes,
        partition_evidence="EQUAL_FAMILY_BODY_BYTE_TOTALS",
        schema=SCHEMA,
        unified_omega_sha256=omega_unified,
        unified_result_sha256=sha256_bytes(unified_data),
    )
    boundary = hbp_row(
        "BRIDGEBOUNDARY",
        bridge_semantics="ORDINAL_CONFIGURATION_ONLY",
        domain_exclusive_training=0,
        geometric_bodies_partition_whole_shared_stream=1,
        partition_evidence="EQUAL_FAMILY_BODY_BYTE_TOTALS",
        historical_decipherment=0,
        historical_translation=0,
        language_layers_distinct=1,
        layers_equated=0,
        live_absorption=0,
        objectives_executed=0,
        objectives_referenced=1,
        physical_mechanism_claim=0,
        promotion=0,
    )
    objective_row = hbp_row(
        "OBJECTIVEREF",
        carriage_artifact=require_field(objective, "carriage_artifact"),
        carriage_root_sha256=require_sha(
            require_field(objective, "carriage_root_sha256"),
            "objective carriage root",
        ),
        formula_rows=int_field(objective, "formula_rows"),
        objective_root_sha256=require_sha(
            require_field(objective, "objective_root_sha256"),
            "objective root",
        ),
        objectives_executed=0,
        objectives_referenced=1,
        source_artifact=require_field(objective, "source_artifact"),
        source_sha256=require_sha(
            require_field(objective, "source_sha256"), "objective source"
        ),
    )
    footer = hbp_row(
        "UBLBRIDGEFTR",
        bodies=40,
        bridge_map_root_sha256=bridge_root,
        domain_exclusive_training=0,
        geometric_bodies_partition_whole_shared_stream=1,
        historical_decipherment=0,
        historical_translation=0,
        objectives_executed=0,
        status="PASS",
    )
    output_rows = [
        header,
        boundary,
        objective_row,
        *family_rows,
        *mapping_rows,
        footer,
    ]

    # No output is touched until all three inputs and all boundary invariants pass.
    hbp, hbi, whole_hex = write_bundle_atomic(output_dir, stem, output_rows)
    return {
        "bodies": 40,
        "bridge_map_root_sha256": bridge_root,
        "geometric_shared_root_sha256": shared_root,
        "geometric_shared_stream_bytes": shared_stream_bytes,
        "hbp": hbp,
        "hbi": hbi,
        "hbp_hex": whole_hex,
        "omega_unified": omega_unified,
        "rows": len(output_rows),
    }


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--body-map", type=Path, default=DEFAULT_BODY_MAP)
    parser.add_argument(
        "--cold-languages", type=Path, default=DEFAULT_COLD_LANGUAGES
    )
    parser.add_argument(
        "--unified-result", type=Path, default=DEFAULT_UNIFIED_RESULT
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--stem", default=DEFAULT_STEM)
    parser.add_argument("--verify-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.verify_only:
        rows = verify_bundle(args.output_dir.resolve(), args.stem)
        print(f"BRIDGEVERIFY|ok=1|rows={rows}|stem={args.stem}|json=0")
        return 0
    result = build_bridge(
        body_map_path=args.body_map.resolve(),
        cold_languages_path=args.cold_languages.resolve(),
        unified_result_path=args.unified_result.resolve(),
        output_dir=args.output_dir.resolve(),
        stem=args.stem,
    )
    print(
        "BRIDGEDONE|"
        f"bodies={result['bodies']}|"
        f"bridge_map_root_sha256={result['bridge_map_root_sha256']}|"
        f"geometric_shared_root_sha256="
        f"{result['geometric_shared_root_sha256']}|"
        f"geometric_shared_stream_bytes="
        f"{result['geometric_shared_stream_bytes']}|"
        f"omega_unified={result['omega_unified']}|"
        f"rows={result['rows']}|json=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
