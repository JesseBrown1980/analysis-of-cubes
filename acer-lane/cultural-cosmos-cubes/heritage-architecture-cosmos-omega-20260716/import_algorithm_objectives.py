#!/usr/bin/env python3
"""Import the pinned Algorithms-of-Asolaria formula corpus as cold objectives.

Each exact ``FORMULA`` source row is one immutable objective slice. The
carriage packet maps every objective slice to every one of the 40 configured
bodies through a content-address pointer bound to that body's unique local
language slot.

This importer performs no objective execution, model call, GNN call, training,
GitRAM/Omega absorption, promotion, minting, or paid operation.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import fetch_and_slice_sources as cold


SCHEMA = "ASOLARIA-ALGORITHM-OBJECTIVE-CARRIAGE-V1"
PROJECT = Path(__file__).resolve().parent
DEFAULT_SOURCE = Path(
    os.environ.get(
        "ASOLARIA_ALGORITHMS_SOURCE",
        str(
            PROJECT
            / "authority"
            / "ALGORITHMS-PID-REGISTRATION-ACER-2026-06-19.hbp"
        ),
    )
)
DEFAULT_CATALOG = PROJECT / "SOURCE-CATALOG.hbp"
DEFAULT_BODY_MAP = PROJECT / "BODY-MAP.hbp"
DEFAULT_OUTPUT = PROJECT
EXPECTED_SOURCE_SHA256 = (
    "782b39c159de8ca3c40f011e631fba57aab2562f706898fb91fe8ecb02f514af"
)
FORMULA_COUNT = 242
BODY_COUNT = 40
POINTER_COUNT = FORMULA_COUNT * BODY_COUNT
OBJECTIVE_ROOT_DOMAIN = b"ASOLARIA-ALGORITHM-OBJECTIVE-ROOT-V1\x00"
OBJECTIVE_ADDRESS_DOMAIN = b"ASOLARIA-ALGORITHM-OBJECTIVE-ADDRESS-V1\x00"
LANGUAGE_BINDING_DOMAIN = b"ASOLARIA-OBJECTIVE-LANGUAGE-BINDING-V1\x00"
CARRIAGE_POINTER_DOMAIN = b"ASOLARIA-OBJECTIVE-CARRIAGE-POINTER-V1\x00"
BODY_ROOT_DOMAIN = b"ASOLARIA-BODY-OBJECTIVE-ROOT-V1\x00"
CARRIAGE_ROOT_DOMAIN = b"ASOLARIA-OBJECTIVE-CARRIAGE-ROOT-V1\x00"


@dataclass(frozen=True)
class ExactRow:
    line: int
    offset: int
    encoded: bytes
    text: str
    row_sha256: str


@dataclass(frozen=True)
class FormulaObjective:
    ordinal: int
    name: str
    pid: str
    kind: str
    tag: str
    formula_class: str
    prof: str
    source: ExactRow


@dataclass(frozen=True)
class BodyRecord:
    fields: dict[str, str]
    source: ExactRow


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def exact_rows(path: Path) -> list[ExactRow]:
    data = path.read_bytes()
    rows: list[ExactRow] = []
    offset = 0
    for line, encoded in enumerate(data.splitlines(keepends=True), 1):
        payload = encoded.rstrip(b"\r\n")
        text = payload.decode("utf-8")
        rows.append(
            ExactRow(
                line=line,
                offset=offset,
                encoded=encoded,
                text=text,
                row_sha256=sha256_bytes(encoded),
            )
        )
        offset += len(encoded)
    if offset != len(data):
        raise RuntimeError(f"exact row walk did not cover source: {path}")
    return rows


def parse_formula_row(row: ExactRow, ordinal: int) -> FormulaObjective:
    parts = row.text.split("|")
    if len(parts) < 3 or parts[0] != "FORMULA":
        raise ValueError(f"not a FORMULA row at source line {row.line}")
    name = parts[1]
    fields: dict[str, str] = {}
    for token in parts[2:]:
        if "=" not in token:
            raise ValueError(
                f"malformed FORMULA field at source line {row.line}: {token}"
            )
        key, value = token.split("=", 1)
        if key in fields:
            raise ValueError(
                f"duplicate FORMULA field at source line {row.line}: {key}"
            )
        fields[key] = value
    for key in ("PID", "KIND", "TAG", "CLASS", "PROF"):
        if key not in fields:
            raise ValueError(
                f"FORMULA row missing {key} at source line {row.line}"
            )
    pid = fields["PID"].lower()
    if re.fullmatch(r"[0-9a-f]{16}", pid) is None:
        raise ValueError(f"invalid formula PID at source line {row.line}: {pid}")
    return FormulaObjective(
        ordinal=ordinal,
        name=name,
        pid=pid,
        kind=fields["KIND"],
        tag=fields["TAG"],
        formula_class=fields["CLASS"],
        prof=fields["PROF"],
        source=row,
    )


def load_objectives(
    source_path: Path,
    expected_source_sha256: str = EXPECTED_SOURCE_SHA256,
) -> tuple[list[FormulaObjective], str, int]:
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    source_sha256 = cold.sha256_file(source_path)
    if source_sha256 != expected_source_sha256.lower():
        raise RuntimeError(
            f"algorithm source SHA-256 mismatch: {source_sha256} != "
            f"{expected_source_sha256.lower()}"
        )
    source_rows = exact_rows(source_path)
    formula_rows = [row for row in source_rows if row.text.startswith("FORMULA|")]
    if len(formula_rows) != FORMULA_COUNT:
        raise RuntimeError(
            f"expected {FORMULA_COUNT} FORMULA rows, found {len(formula_rows)}"
        )
    objectives = [
        parse_formula_row(row, ordinal)
        for ordinal, row in enumerate(formula_rows, 1)
    ]
    pids = [objective.pid for objective in objectives]
    if len(set(pids)) != len(pids):
        raise RuntimeError("formula PID collision in source authority")
    return objectives, source_sha256, len(source_rows)


def objective_root(
    objectives: Sequence[FormulaObjective], source_sha256: str
) -> str:
    digest = hashlib.sha256()
    digest.update(OBJECTIVE_ROOT_DOMAIN)
    digest.update(bytes.fromhex(source_sha256))
    for objective in objectives:
        digest.update(objective.ordinal.to_bytes(4, "big"))
        digest.update(bytes.fromhex(objective.source.row_sha256))
    return digest.hexdigest()


def objective_address(root: str, objective: FormulaObjective) -> str:
    return sha256_bytes(
        OBJECTIVE_ADDRESS_DOMAIN
        + bytes.fromhex(root)
        + objective.ordinal.to_bytes(4, "big")
        + bytes.fromhex(objective.source.row_sha256)
    )


def load_body_records(
    catalog_path: Path, body_map_path: Path
) -> tuple[list[BodyRecord], str]:
    _, source_by_id = cold.load_source_catalog(catalog_path)
    bodies, _ = cold.load_body_map(body_map_path, source_by_id)
    exact = exact_rows(body_map_path)
    body_rows: dict[str, ExactRow] = {}
    for row in exact:
        kind, fields = cold.parse_hbp_line(row.text)
        if kind != "BODY":
            continue
        body_id = fields.get("body_id")
        if not body_id:
            raise ValueError(f"BODY row missing body_id at line {row.line}")
        if body_id in body_rows:
            raise ValueError(f"duplicate exact BODY row: {body_id}")
        body_rows[body_id] = row
    if set(body_rows) != {body["body_id"] for body in bodies}:
        raise RuntimeError("validated bodies and exact BODY rows differ")
    records = [
        BodyRecord(fields=body, source=body_rows[body["body_id"]])
        for body in sorted(bodies, key=lambda item: item["body_id"])
    ]
    slots = [record.fields["language_slot"] for record in records]
    if len(records) != BODY_COUNT or len(set(slots)) != BODY_COUNT:
        raise RuntimeError("40 distinct body language slots are required")
    return records, cold.sha256_file(body_map_path)


def language_binding(root: str, body: BodyRecord) -> str:
    return sha256_bytes(
        LANGUAGE_BINDING_DOMAIN
        + bytes.fromhex(root)
        + bytes.fromhex(body.source.row_sha256)
        + body.fields["language_slot"].encode("utf-8")
    )


def carriage_pointer(
    root: str,
    body: BodyRecord,
    objective: FormulaObjective,
) -> str:
    return sha256_bytes(
        CARRIAGE_POINTER_DOMAIN
        + bytes.fromhex(root)
        + bytes.fromhex(body.source.row_sha256)
        + body.fields["body_id"].encode("ascii")
        + b"\x00"
        + body.fields["language_slot"].encode("utf-8")
        + b"\x00"
        + objective.ordinal.to_bytes(4, "big")
        + bytes.fromhex(objective.source.row_sha256)
    )


def build_algorithm_rows(
    source_path: Path,
    objectives: Sequence[FormulaObjective],
    source_sha256: str,
    source_rows: int,
    root: str,
) -> list[str]:
    rows = [
        cold.hbp_row(
            "ALGORITHMOBJECTIVESHDR",
            schema=SCHEMA,
            source_path=source_path.resolve().as_posix(),
            source_sha256=source_sha256,
            source_rows=source_rows,
            formula_rows=len(objectives),
            objective_slices=len(objectives),
            objective_root_sha256=root,
            objective_root_rule=(
                "SHA256_DOMAIN_SOURCE_SHA256_ORDERED_ORDINAL_AND_SOURCE_ROW_SHA256"
            ),
            source_row_hash_scope="EXACT_SOURCE_BYTES_INCLUDING_LINE_ENDING",
            execution=0,
            training=0,
            live_absorption=0,
            promotion=0,
        )
    ]
    for objective in objectives:
        rows.append(
            cold.hbp_row(
                "ALGORITHMOBJECTIVE",
                schema=SCHEMA,
                objective_slice=objective.ordinal,
                name=objective.name,
                pid=objective.pid,
                formula_kind=objective.kind,
                tag=objective.tag,
                formula_class=objective.formula_class,
                prof=objective.prof,
                objective_address_sha256=objective_address(root, objective),
                source_line=objective.source.line,
                source_offset=objective.source.offset,
                source_len=len(objective.source.encoded),
                source_row_sha256=objective.source.row_sha256,
                execution=0,
            )
        )
    return rows


def build_carriage_rows(
    objectives: Sequence[FormulaObjective],
    bodies: Sequence[BodyRecord],
    root: str,
    body_map_sha256: str,
) -> tuple[list[str], str, dict[str, str]]:
    body_rows: list[
        tuple[BodyRecord, str, str, list[tuple[FormulaObjective, str]]]
    ] = []
    for body in bodies:
        binding = language_binding(root, body)
        pointers = [
            (objective, carriage_pointer(root, body, objective))
            for objective in objectives
        ]
        body_digest = hashlib.sha256()
        body_digest.update(BODY_ROOT_DOMAIN)
        body_digest.update(bytes.fromhex(root))
        body_digest.update(bytes.fromhex(body.source.row_sha256))
        for _, pointer in pointers:
            body_digest.update(bytes.fromhex(pointer))
        body_rows.append((body, binding, body_digest.hexdigest(), pointers))

    carriage_digest = hashlib.sha256()
    carriage_digest.update(CARRIAGE_ROOT_DOMAIN)
    carriage_digest.update(bytes.fromhex(root))
    body_roots: dict[str, str] = {}
    for body, _, body_root, _ in body_rows:
        carriage_digest.update(body.fields["body_id"].encode("ascii"))
        carriage_digest.update(bytes.fromhex(body_root))
        body_roots[body.fields["body_id"]] = body_root
    carriage_root = carriage_digest.hexdigest()

    rows = [
        cold.hbp_row(
            "OBJECTIVECARRIAGEHDR",
            schema=SCHEMA,
            bodies=len(bodies),
            objective_slices=len(objectives),
            pointers=len(bodies) * len(objectives),
            objective_root_sha256=root,
            carriage_root_sha256=carriage_root,
            body_map_sha256=body_map_sha256,
            distinct_language_slots=len(
                {body.fields["language_slot"] for body in bodies}
            ),
            local_language_id_state="DEFERRED_UNTIL_CORPUS_ROOT",
            local_language_binding="BODY_LANGUAGE_SLOT_PLUS_EXACT_BODY_ROW_HASH",
            pointer_semantics="CONTENT_ADDRESS_ONLY_NOT_EXECUTION",
            execution=0,
            external_model_calls=0,
            external_gnn_calls=0,
            live_gitram_ingestion=0,
            live_gnn_training=0,
            live_omega_absorption=0,
            promotion=0,
            minting=0,
            paid_spend_usd=0,
        )
    ]
    for body, binding, body_root, pointers in body_rows:
        fields = body.fields
        rows.append(
            cold.hbp_row(
                "BODYOBJECTIVEROOT",
                schema=SCHEMA,
                body_id=fields["body_id"],
                body_name=fields["name"],
                family=fields["family"],
                passes=fields["passes"],
                local_language_slot=fields["language_slot"],
                language_binding_sha256=binding,
                body_source_line=body.source.line,
                body_source_row_sha256=body.source.row_sha256,
                objective_slices=len(objectives),
                objective_root_sha256=root,
                body_objective_root_sha256=body_root,
                execution=0,
            )
        )
        for objective, pointer in pointers:
            rows.append(
                cold.hbp_row(
                    "OBJECTIVECARRIAGE",
                    schema=SCHEMA,
                    body_id=fields["body_id"],
                    family=fields["family"],
                    local_language_slot=fields["language_slot"],
                    language_binding_sha256=binding,
                    objective_slice=objective.ordinal,
                    objective_pid=objective.pid,
                    objective_address_sha256=objective_address(root, objective),
                    objective_source_row_sha256=objective.source.row_sha256,
                    carriage_pointer_sha256=pointer,
                    execution=0,
                )
            )
    return rows, carriage_root, body_roots


def expected_artifacts(
    source_path: Path,
    catalog_path: Path,
    body_map_path: Path,
) -> tuple[list[str], list[str], dict[str, Any]]:
    objectives, source_sha256, source_rows = load_objectives(source_path)
    bodies, body_map_sha256 = load_body_records(catalog_path, body_map_path)
    root = objective_root(objectives, source_sha256)
    algorithm_rows = build_algorithm_rows(
        source_path, objectives, source_sha256, source_rows, root
    )
    carriage_rows, carriage_root, body_roots = build_carriage_rows(
        objectives, bodies, root, body_map_sha256
    )
    return algorithm_rows, carriage_rows, {
        "source_sha256": source_sha256,
        "objective_root_sha256": root,
        "carriage_root_sha256": carriage_root,
        "formula_rows": len(objectives),
        "bodies": len(bodies),
        "pointers": len(objectives) * len(bodies),
        "body_roots": body_roots,
    }


def build(
    source_path: Path,
    catalog_path: Path,
    body_map_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    algorithm_rows, carriage_rows, summary = expected_artifacts(
        source_path, catalog_path, body_map_path
    )
    cold.write_bundle(output_dir, "ALGORITHM-OBJECTIVES", algorithm_rows)
    cold.write_bundle(output_dir, "OBJECTIVE-CARRIAGE", carriage_rows)
    return summary


def artifact_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def verify(
    source_path: Path,
    catalog_path: Path,
    body_map_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    algorithm_rows, carriage_rows, summary = expected_artifacts(
        source_path, catalog_path, body_map_path
    )
    cold.verify_bundle(output_dir, "ALGORITHM-OBJECTIVES")
    cold.verify_bundle(output_dir, "OBJECTIVE-CARRIAGE")
    if artifact_lines(output_dir / "ALGORITHM-OBJECTIVES.hbp") != algorithm_rows:
        raise RuntimeError("ALGORITHM-OBJECTIVES semantic mismatch")
    if artifact_lines(output_dir / "OBJECTIVE-CARRIAGE.hbp") != carriage_rows:
        raise RuntimeError("OBJECTIVE-CARRIAGE semantic mismatch")

    algorithm_parsed = cold.read_hbp_rows(
        output_dir / "ALGORITHM-OBJECTIVES.hbp"
    )
    objective_rows = [
        fields
        for kind, fields, _ in algorithm_parsed
        if kind == "ALGORITHMOBJECTIVE"
    ]
    if (
        len(objective_rows) != FORMULA_COUNT
        or [int(row["objective_slice"]) for row in objective_rows]
        != list(range(1, FORMULA_COUNT + 1))
        or len({row["pid"] for row in objective_rows}) != FORMULA_COUNT
    ):
        raise RuntimeError("algorithm objective coverage is incomplete")

    carriage_parsed = cold.read_hbp_rows(output_dir / "OBJECTIVE-CARRIAGE.hbp")
    body_root_rows = [
        fields
        for kind, fields, _ in carriage_parsed
        if kind == "BODYOBJECTIVEROOT"
    ]
    pointer_rows = [
        fields
        for kind, fields, _ in carriage_parsed
        if kind == "OBJECTIVECARRIAGE"
    ]
    if (
        len(body_root_rows) != BODY_COUNT
        or len(pointer_rows) != POINTER_COUNT
        or len({row["local_language_slot"] for row in body_root_rows})
        != BODY_COUNT
    ):
        raise RuntimeError("objective carriage coverage is incomplete")
    pointers_by_body: dict[str, set[int]] = {}
    for row in pointer_rows:
        pointers_by_body.setdefault(row["body_id"], set()).add(
            int(row["objective_slice"])
        )
        if row["execution"] != "0":
            raise RuntimeError("objective carriage execution must remain held")
    exact_slices = set(range(1, FORMULA_COUNT + 1))
    if set(pointers_by_body) != set(summary["body_roots"]):
        raise RuntimeError("objective carriage body set mismatch")
    if any(slices != exact_slices for slices in pointers_by_body.values()):
        raise RuntimeError("per-body objective slices are incomplete")
    return summary


def self_test(
    source_path: Path, catalog_path: Path, body_map_path: Path
) -> dict[str, Any]:
    algorithm_rows, carriage_rows, summary = expected_artifacts(
        source_path, catalog_path, body_map_path
    )
    if len(algorithm_rows) != FORMULA_COUNT + 1:
        raise AssertionError("objective row invariant failed")
    if len(carriage_rows) != 1 + BODY_COUNT + POINTER_COUNT:
        raise AssertionError("carriage row invariant failed")
    if len(summary["body_roots"]) != BODY_COUNT:
        raise AssertionError("body-root invariant failed")
    return summary


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase", choices=("all", "build", "verify", "self-test"), default="all"
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--body-map", type=Path, default=DEFAULT_BODY_MAP)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.phase == "self-test":
        summary = self_test(args.source, args.catalog, args.body_map)
    elif args.phase == "build":
        summary = build(
            args.source, args.catalog, args.body_map, args.output_dir
        )
    elif args.phase == "verify":
        summary = verify(
            args.source, args.catalog, args.body_map, args.output_dir
        )
    else:
        build(args.source, args.catalog, args.body_map, args.output_dir)
        summary = verify(
            args.source, args.catalog, args.body_map, args.output_dir
        )
    print(
        cold.hbp_row(
            "OBJECTIVEIMPORTDONE",
            schema=SCHEMA,
            phase=args.phase,
            source_sha256=summary["source_sha256"],
            formula_rows=summary["formula_rows"],
            bodies=summary["bodies"],
            pointers=summary["pointers"],
            objective_root_sha256=summary["objective_root_sha256"],
            carriage_root_sha256=summary["carriage_root_sha256"],
            execution=0,
            live_absorption=0,
            promotion=0,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
