#!/usr/bin/env python3
"""Prepare a content-free, path-redacted publication receipt set.

The measured roots and source hashes remain unchanged. Only host-local path
fields are replaced with stable repository or held-local pointers, after which
the affected HBP/HBI/hex bundles and their SHA-256 sidecars are regenerated.
"""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from typing import Iterable

import fetch_and_slice_sources as cold


PROJECT = Path(__file__).resolve().parent
SCHEMA = "ASOLARIA-HERITAGE-COSMOS-PUBLICATION-V1"
ALGORITHM_POINTER = (
    "Algorithms-of-Asolaria/acer/"
    "ALGORITHMS-PID-REGISTRATION-ACER-2026-06-19.hbp"
)
PUBLICATION_STEM = "PUBLICATION-MANIFEST"
UNIFIED_OMEGA = (
    "106ed6dd85d2795a93880bb21ae187b6e14f3941a453766c7d0a7f4f69f2c3ba"
)

ORIGINAL_HBP_SHA256 = {
    "ALGORITHM-OBJECTIVES.hbp": (
        "19c59eb389610b5255709b3bdaa92001a5d5c07716fd8be1b223fde428e7adca"
    ),
    "HERITAGE-COSMOS-CONTRACT.hbp": (
        "af4eed7b85dce1c66a0e3921e91f40fafbd9379f202e3e3b8016ac7b31cc75a1"
    ),
    "receipts/cold-corpus-v2/CONTRACT-SNAPSHOT.hbp": (
        "af4eed7b85dce1c66a0e3921e91f40fafbd9379f202e3e3b8016ac7b31cc75a1"
    ),
    "receipts/fetch/SOURCE-FETCH.hbp": (
        "808cec81c9bfb8ffdda42916b90c44de85efc493937e8e623e84a74c76567fd9"
    ),
}
ORIGINAL_COLD_SHA256SUMS_SHA256 = (
    "7e11dfaf7bf6d24a4dbc4492838893457b13b830054db10f6203b2db64d6ee40"
)


def replace_field(line: str, field: str, value: str) -> str:
    parts = line.split("|")
    prefix = f"{field}="
    replaced = False
    for index, part in enumerate(parts):
        if part.startswith(prefix):
            parts[index] = prefix + value
            replaced = True
            break
    if not replaced:
        raise RuntimeError(f"missing {field} field in row: {line[:80]}")
    return "|".join(parts)


def sanitize_algorithm_rows(path: Path) -> list[str]:
    rows = path.read_text(encoding="utf-8").splitlines()
    if not rows or not rows[0].startswith("ALGORITHMOBJECTIVESHDR|"):
        raise RuntimeError(f"unexpected algorithm packet: {path}")
    rows[0] = replace_field(rows[0], "source_path", ALGORITHM_POINTER)
    return rows


def sanitize_contract_rows(path: Path) -> list[str]:
    rows = path.read_text(encoding="utf-8").splitlines()
    found = False
    for index, row in enumerate(rows):
        if row.startswith("OBJECTIVECONTRACT|"):
            rows[index] = replace_field(row, "source", ALGORITHM_POINTER)
            found = True
    if not found:
        raise RuntimeError(f"OBJECTIVECONTRACT row missing: {path}")
    return rows


def sanitize_fetch_rows(path: Path) -> list[str]:
    rows = path.read_text(encoding="utf-8").splitlines()
    output: list[str] = []
    fetch_count = 0
    for row in rows:
        if not row.startswith("FETCH|"):
            output.append(row)
            continue
        _, fields = cold.parse_hbp_line(row)
        source_id = fields["source_id"]
        filename = PurePosixPath(fields["path"]).name
        output.append(
            replace_field(row, "path", f"LOCAL_RAW_HELD/{source_id}/{filename}")
        )
        fetch_count += 1
    if fetch_count != 5:
        raise RuntimeError(f"expected 5 FETCH rows, found {fetch_count}")
    return output


def write_rows(path: Path, rows: Iterable[str]) -> None:
    cold.write_lf(path, "\n".join(rows))


def reseal_bundle(path: Path, rows: list[str]) -> None:
    cold.write_bundle(path.parent, path.stem, rows)
    cold.verify_bundle(path.parent, path.stem)


def update_cold_checksum_manifest(receipts: Path) -> tuple[str, str]:
    manifest = receipts / "UPSTREAM-SHA256SUMS"
    before = cold.sha256_file(manifest)
    updated: list[str] = []
    affected_prefix = "receipts/CONTRACT-SNAPSHOT."
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        _, relative = line.split(None, 1)
        if relative.startswith(affected_prefix):
            local = receipts / relative.removeprefix("receipts/")
            if not local.is_file():
                raise RuntimeError(f"missing redacted contract artifact: {local}")
            line = f"{cold.sha256_file(local)}  {relative}"
        updated.append(line)
    cold.write_lf(manifest, "\n".join(updated))
    cold.write_sidecar(manifest)
    return before, cold.sha256_file(manifest)


def publication_files() -> list[Path]:
    excluded_names = {
        f"{PUBLICATION_STEM}.hbp",
        f"{PUBLICATION_STEM}.hbi",
        f"{PUBLICATION_STEM}.hbp.hex",
        f"{PUBLICATION_STEM}.hbp.sha256",
        f"{PUBLICATION_STEM}.hbi.sha256",
        f"{PUBLICATION_STEM}.hbp.hex.sha256",
    }
    files = []
    for path in PROJECT.rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.name in excluded_names and path.parent == PROJECT:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(PROJECT).as_posix())


def artifact_root(files: list[Path]) -> str:
    digest = hashlib.sha256()
    digest.update(b"ASOLARIA-PUBLICATION-ARTIFACT-ROOT-V1\x00")
    for path in files:
        relative = path.relative_to(PROJECT).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(path.stat().st_size.to_bytes(8, "big"))
        digest.update(bytes.fromhex(cold.sha256_file(path)))
    return digest.hexdigest()


def verify_no_host_paths(files: list[Path]) -> None:
    needles = (
        b"C:/" + b"Users/",
        b"C:" + b"\\Users\\",
        b"/mnt/c/" + b"Users/",
        b"C:/" + b"tmp/",
    )
    for path in files:
        data = path.read_bytes()
        if any(needle.lower() in data.lower() for needle in needles):
            raise RuntimeError(f"host-local path remains in publication file: {path}")


def write_publication_manifest(
    files: list[Path],
    cold_manifest_before: str,
    cold_manifest_after: str,
) -> dict[str, str | int]:
    root = artifact_root(files)
    total_bytes = sum(path.stat().st_size for path in files)
    rows = [
        cold.hbp_row(
            "PUBLICATIONHDR",
            schema=SCHEMA,
            artifact_count=len(files),
            artifact_bytes=total_bytes,
            artifact_root_sha256=root,
            unified_omega_sha256=UNIFIED_OMEGA,
            content_free_receipts=1,
            raw_payload_files=0,
            slice_payload_files=0,
            media_files=0,
            secrets=0,
            local_paths_redacted=1,
            claims_final_apex=0,
        ),
        cold.hbp_row(
            "PUBLICATIONBOUNDARY",
            schema=SCHEMA,
            raw_corpus="HELD_LOCAL_NOT_REDISTRIBUTED",
            slice_payloads="HELD_LOCAL_NOT_REDISTRIBUTED",
            download_archives="HELD_LOCAL_NOT_REDISTRIBUTED",
            algorithm_authority="POINTER_PLUS_PINNED_SHA256",
            objective_execution=0,
            live_gitram_ingestion=0,
            live_gnn_training=0,
            physical_projection="UNVERIFIED",
            archive_ratio="NOT_CLAIMED",
            upstream_manifests="PROVENANCE_ONLY_NOT_PUBLICATION_COMPLETENESS",
        ),
    ]
    for relative, original in sorted(ORIGINAL_HBP_SHA256.items()):
        path = PROJECT / relative
        rows.append(
            cold.hbp_row(
                "PUBLICATIONTRANSFORM",
                schema=SCHEMA,
                path=relative,
                change="HOST_PATH_TO_STABLE_POINTER",
                source_native_sha256=original,
                published_sha256=cold.sha256_file(path),
                measured_roots_changed=0,
            )
        )
    rows.append(
        cold.hbp_row(
            "PUBLICATIONTRANSFORM",
            schema=SCHEMA,
            path="receipts/cold-corpus-v2/UPSTREAM-SHA256SUMS",
            change="RESEALED_FOR_REDACTED_CONTRACT_BUNDLE",
            source_native_sha256=ORIGINAL_COLD_SHA256SUMS_SHA256,
            observed_preparation_sha256=cold_manifest_before,
            published_sha256=cold_manifest_after,
            measured_roots_changed=0,
        )
    )
    for path in files:
        rows.append(
            cold.hbp_row(
                "PUBLICATIONARTIFACT",
                schema=SCHEMA,
                path=path.relative_to(PROJECT).as_posix(),
                bytes=path.stat().st_size,
                sha256=cold.sha256_file(path),
            )
        )
    cold.write_bundle(PROJECT, PUBLICATION_STEM, rows)
    count = cold.verify_bundle(PROJECT, PUBLICATION_STEM)
    return {
        "artifact_count": len(files),
        "artifact_bytes": total_bytes,
        "artifact_root_sha256": root,
        "manifest_rows": count,
        "manifest_hbp_sha256": cold.sha256_file(
            PROJECT / f"{PUBLICATION_STEM}.hbp"
        ),
    }


def main() -> int:
    algorithm = PROJECT / "ALGORITHM-OBJECTIVES.hbp"
    root_contract = PROJECT / "HERITAGE-COSMOS-CONTRACT.hbp"
    cold_contract = (
        PROJECT / "receipts" / "cold-corpus-v2" / "CONTRACT-SNAPSHOT.hbp"
    )
    fetch = PROJECT / "receipts" / "fetch" / "SOURCE-FETCH.hbp"

    reseal_bundle(algorithm, sanitize_algorithm_rows(algorithm))
    contract_rows = sanitize_contract_rows(root_contract)
    write_rows(root_contract, contract_rows)
    cold.write_sidecar(root_contract)
    reseal_bundle(cold_contract, contract_rows)
    reseal_bundle(fetch, sanitize_fetch_rows(fetch))

    cold.write_sidecar(
        PROJECT / "receipts" / "heritage-source" / "UPSTREAM-SHA256SUMS"
    )

    cold_before, cold_after = update_cold_checksum_manifest(
        PROJECT / "receipts" / "cold-corpus-v2"
    )
    files = publication_files()
    verify_no_host_paths(files)
    summary = write_publication_manifest(files, cold_before, cold_after)
    print(
        cold.hbp_row(
            "PUBLICATIONDONE",
            schema=SCHEMA,
            **summary,
            unified_omega_sha256=UNIFIED_OMEGA,
            raw_payload_files=0,
            slice_payload_files=0,
            local_paths_redacted=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
