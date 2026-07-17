#!/usr/bin/env python3
"""Independent verifier for the Omega glyph 100-view simulation receipts."""

from __future__ import annotations

import argparse
import hashlib
import math
from pathlib import Path
from urllib.parse import unquote


EXPECTED_SUM_FILES = (
    "GLYPH-INPUT.bin",
    "OMEGA-GLYPH-100VIEW.hbp",
    "OMEGA-GLYPH-100VIEW.hbi",
    "RESULTS.md",
)
TEXT_FILES = (
    "OMEGA-GLYPH-100VIEW.hbp",
    "OMEGA-GLYPH-100VIEW.hbi",
    "RESULTS.md",
    "SHA256SUMS",
    "SHA256SUMS.sha256",
)
DOMAIN = b"OMEGA-GLYPH-100VIEW-V2\0"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def shannon_h0(values: list[int]) -> float:
    if not values:
        return 0.0
    counts: dict[int, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    total = len(values)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def bytes_to_symbols(data: bytes, bits: int) -> list[int]:
    out: list[int] = []
    accumulator = 0
    available = 0
    mask = (1 << bits) - 1
    for byte in data:
        accumulator = (accumulator << 8) | byte
        available += 8
        while available >= bits:
            available -= bits
            out.append((accumulator >> available) & mask)
    if available:
        out.append((accumulator << (bits - available)) & mask)
    return out


def parse_row(line: str) -> tuple[str, dict[str, str]]:
    parts = line.split("|")
    fields: dict[str, str] = {}
    for part in parts[1:]:
        if "=" in part:
            key, value = part.split("=", 1)
            fields[key] = unquote(value)
    return parts[0], fields


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify_directory(root: Path) -> dict[str, object]:
    for name in TEXT_FILES:
        payload = (root / name).read_bytes()
        require(b"\r" not in payload, "{} is not LF-only".format(name))
        require(payload.endswith(b"\n"), "{} lacks terminal LF".format(name))

    sums_lines = (root / "SHA256SUMS").read_text("utf-8").splitlines()
    require(len(sums_lines) == len(EXPECTED_SUM_FILES), "unexpected SHA256SUMS row count")
    sums: dict[str, str] = {}
    for line in sums_lines:
        digest, name = line.split("  ", 1)
        require(len(digest) == 64, "invalid digest width for {}".format(name))
        require(name not in sums, "duplicate sum entry {}".format(name))
        sums[name] = digest
    require(tuple(sums) == EXPECTED_SUM_FILES, "unexpected SHA256SUMS ordering or names")
    for name, digest in sums.items():
        require(sha256((root / name).read_bytes()) == digest, "checksum mismatch {}".format(name))

    sidecar = (root / "SHA256SUMS.sha256").read_text("utf-8").strip()
    sidecar_digest, sidecar_name = sidecar.split("  ", 1)
    require(sidecar_name == "SHA256SUMS", "sidecar target mismatch")
    require(sidecar_digest == sha256((root / "SHA256SUMS").read_bytes()), "sidecar mismatch")

    hbp = (root / "OMEGA-GLYPH-100VIEW.hbp").read_bytes()
    hbi = (root / "OMEGA-GLYPH-100VIEW.hbi").read_bytes()
    hbp_lines = hbp.splitlines(keepends=True)
    require(hbp_lines and all(line.endswith(b"\n") for line in hbp_lines), "HBP LF coverage failure")
    hbi_lines = hbi.decode("utf-8").splitlines()
    header_kind, header = parse_row(hbi_lines[0])
    require(header_kind == "HBIHDR", "missing HBI header")
    require(header["target"] == "OMEGA-GLYPH-100VIEW.hbp", "HBI target mismatch")
    require(int(header["target_bytes"]) == len(hbp), "HBI target byte count mismatch")
    require(header["target_sha256"] == sha256(hbp), "HBI target SHA mismatch")
    require(int(header["rows"]) == len(hbp_lines), "HBI target row count mismatch")
    require(len(hbi_lines) == len(hbp_lines) + 1, "HBI offset row count mismatch")

    offset = 0
    for expected_row, (hbp_line, hbi_line) in enumerate(zip(hbp_lines, hbi_lines[1:]), 1):
        kind, fields = parse_row(hbi_line)
        require(kind == "HBIOFFSET", "unexpected HBI row kind")
        body = hbp_line[:-1]
        require(int(fields["row"]) == expected_row, "HBI row number mismatch")
        require(int(fields["offset"]) == offset, "HBI non-contiguous offset")
        require(int(fields["length"]) == len(body), "HBI row length mismatch")
        require(fields["lf"] == "1", "HBI row missing LF marker")
        require(fields["row_sha256"] == sha256(body), "HBI row SHA mismatch")
        offset += len(hbp_line)
    require(offset == len(hbp), "HBI does not cover all HBP bytes")

    decoded_rows = [line[:-1].decode("utf-8") for line in hbp_lines]
    parsed_rows = [parse_row(line) for line in decoded_rows]
    commit_indexes = [index for index, (kind, _) in enumerate(parsed_rows) if kind == "OMEGACOMMIT"]
    require(len(commit_indexes) == 1, "expected one Omega commitment")
    commit_index = commit_indexes[0]
    commit = parsed_rows[commit_index][1]
    require(commit["domain"] == "OMEGA-GLYPH-100VIEW-V2", "Omega domain mismatch")
    require(commit["commitment_scope"] == "ALL_HBP_ROWS_BEFORE_OMEGACOMMIT", "Omega scope mismatch")
    require(int(commit["committed_rows"]) == commit_index, "Omega committed row count mismatch")
    require(int(commit["leaves"]) == commit_index, "Omega leaf count mismatch")
    require(commit["descriptor_identity"] == "FULL_SHA256_SIMULATION_DERIVED_NOT_REGISTERED", "descriptor identity mismatch")

    leaves = [
        sha256(index.to_bytes(8, "little") + body.encode("utf-8"))
        for index, body in enumerate(decoded_rows[:commit_index])
    ]
    message = bytearray(DOMAIN)
    message.extend(bytes.fromhex(commit["input_sha256"]))
    message.extend(len(leaves).to_bytes(8, "little"))
    for leaf in sorted(leaves):
        leaf_bytes = bytes.fromhex(leaf)
        message.extend(len(leaf_bytes).to_bytes(4, "little"))
        message.extend(leaf_bytes)
    require(sha256(bytes(message)) == commit["omega_sha256"], "Omega recomputation mismatch")

    view_rows = [fields for kind, fields in parsed_rows if kind == "VIEWDESC"]
    require(len(view_rows) == 100, "VIEWDESC count mismatch")
    require(all(len(fields["pid"]) == 64 for fields in view_rows), "descriptor digest is not full SHA-256")
    require(
        all(fields["pid_semantics"] == "SIMULATION_DERIVED_NOT_REGISTERED" for fields in view_rows),
        "descriptor PID semantics missing",
    )

    cascade_rows = [fields for kind, fields in parsed_rows if kind == "LOGICALCASCADE"]
    require(len(cascade_rows) == 1, "LOGICALCASCADE count mismatch")
    cascade = cascade_rows[0]
    require(cascade["partition_arithmetic"] == "EXACT", "partition arithmetic tag missing")
    require(cascade["agents_enumerated_by_this_experiment"] == "0", "experiment enumeration must be zero")
    require(cascade["agents_spawned_by_this_experiment"] == "0", "experiment spawn count must be zero")
    require(cascade["physical_claim"] == "0", "physical claim must be zero")
    require(
        cascade["interpretation"] == "PARTITION_ARITHMETIC_ONLY_NOT_RUNTIME_OR_PHYSICAL_SCALE",
        "partition interpretation mismatch",
    )

    projection_rows = [fields for kind, fields in parsed_rows if kind == "PROJECTIONHDR"]
    require(len(projection_rows) == 1, "PROJECTIONHDR count mismatch")
    projection = projection_rows[0]
    require(projection["glyph_embedding"] == "NONE", "projection glyph embedding must be none")
    require(cascade["materialized_kernels"] == "OUT_OF_SCOPE_NOT_DENIED", "kernel scope tag missing")
    require(projection["view_measurements_consumed"] == "0", "projection consumed glyph views")
    require(projection["glyph_nullspace_claim"] == "0", "glyph nullspace claim must be zero")

    entropy_input = [fields for kind, fields in parsed_rows if kind == "ENTROPYINPUT"]
    entropy_views = [fields for kind, fields in parsed_rows if kind == "ENTROPYVIEWS"]
    require(len(entropy_input) == 1 and len(entropy_views) == 1, "entropy ledger missing")
    entropy_row = entropy_input[0]
    require(entropy_row["byte_alphabet"] == "256", "byte alphabet missing")
    require(entropy_row["glyph_alphabet"] == "1024", "glyph alphabet missing")
    frozen_input = (root / "GLYPH-INPUT.bin").read_bytes()
    glyph_symbols = bytes_to_symbols(frozen_input, 10)
    require(int(entropy_row["byte_symbols"]) == len(frozen_input), "byte symbol count mismatch")
    require(int(entropy_row["glyph_symbols"]) == len(glyph_symbols), "glyph symbol count mismatch")
    require(entropy_row["byte_h0_bits_per_byte"] == "{:.12f}".format(shannon_h0(list(frozen_input))), "byte H0 mismatch")
    require(entropy_row["glyph_h0_bits_per_glyph"] == "{:.12f}".format(shannon_h0(glyph_symbols)), "glyph H0 mismatch")
    require(int(entropy_row["packed_glyph_bytes"]) == (len(glyph_symbols) * 10 + 7) // 8, "packed glyph byte count mismatch")
    require(entropy_row["compression_claim"] == "0", "compression claim must be zero")
    require(entropy_views[0]["bijection_implies_equal_marginal_h0"] == "0", "H0 rigor tag missing")

    footer_kind, footer = parsed_rows[-1]
    require(footer_kind == "OMEGAGLYPHFTR", "missing HBP footer")
    require(footer["status"] == "PASS", "HBP footer not PASS")
    require(footer["mode"] == "FULL_INPUT_DEPENDENT_TRANSFORM_SIMULATION", "footer mode mismatch")
    require(footer["codec_claim"] == "0", "codec claim must be zero")
    require(footer["physical_claims"] == "0", "physical claims must be zero")

    public_text = b"\n".join((root / name).read_bytes() for name in TEXT_FILES)
    for forbidden in (b"C:\\Users\\", b"C:/Users/", b"/mnt/c/Users/", b"AppData"):
        require(forbidden not in public_text, "local path leak {}".format(forbidden.decode("ascii")))

    return {
        "rows": len(hbp_lines),
        "hbp_bytes": len(hbp),
        "hbp_sha256": sha256(hbp),
        "hbi_sha256": sha256(hbi),
        "omega_sha256": commit["omega_sha256"],
        "views": len(view_rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, nargs="?", default=Path("synthetic-output"))
    args = parser.parse_args()
    try:
        result = verify_directory(args.root)
    except Exception as exc:
        print("VERIFY|status=FAIL|error={}|json=0|fire=0".format(str(exc).replace("|", "%7C")))
        return 1
    print(
        "VERIFY|status=PASS|rows={rows}|hbp_bytes={hbp_bytes}|views={views}|"
        "hbp_sha256={hbp_sha256}|hbi_sha256={hbi_sha256}|omega_sha256={omega_sha256}|"
        "partition_arithmetic=EXACT|agents_enumerated_by_this_experiment=0|"
        "agents_spawned_by_this_experiment=0|physical_claim=0|json=0|fire=0".format(**result)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
