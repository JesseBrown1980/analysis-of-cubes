#!/usr/bin/env python3
"""Bounded, full-input-dependent Omega glyph transform simulation core.

The eight A-views are a literal stdlib Python port of a_ap/a_in from the
published unified_omega.rs source.  The modulo-12 residue permutation,
modulo-20 residue permutation, frequency rotation, disconnected 60D linea
algebra control, and 1e200 address partition are explicitly experimental
simulations.  This is not a causal codec or the integrated four-floor system.
Nothing here spawns agents or touches live state.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import quote


BITS = 10
FIELD = 257
DIMENSIONS = 60
MAX_VIEWS = 100
A_NAMES = (
    "G_ID",
    "G_REV",
    "G_XORD",
    "G_ROT",
    "G_HALF",
    "G_BLKREV",
    "G_EVODD",
    "G_QPRISM",
)
A_VIEW_SOURCE = "unified_omega.rs:a_ap/a_in"
A_VIEW_SOURCE_SHA256 = "308e1dca6d7bc61841f7b56c6524724f4abb12aec505548424b320a1133f68d2"
A_VIEW_SOURCE_REPOSITORY = "https://github.com/JesseBrown1980/asolaria-cube-cloud"
A_VIEW_SOURCE_COMMIT = "dc02a3d9bc3201f794e6e9d3755bfdf7f858b7bd"
A_VIEW_SOURCE_PATH = "unified_omega.rs"
TARGET_NUMBERS = (7, 8, 12, 20, 120, 840, 7680)
CHECKPOINTS = (1, 2, 4, 8, 16, 32, 60, 64, 80, 100)
DOMAIN = b"OMEGA-GLYPH-100VIEW-V2\0"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def enc(value: object) -> str:
    return quote(str(value), safe="-_.~")


def row(kind: str, **fields: object) -> str:
    parts = [kind]
    parts.extend(f"{key}={enc(value)}" for key, value in fields.items())
    parts.extend(("json=0", "fire=0"))
    return "|".join(parts)


def write_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8"))


def shannon_h0(values: Sequence[int]) -> float:
    """Return empirical marginal H0 in bits per symbol for a declared alphabet."""
    if not values:
        return 0.0
    counts: dict[int, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    total = len(values)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def b2g(data: bytes, bits: int = BITS) -> list[int]:
    out: list[int] = []
    acc = 0
    nbits = 0
    mask = (1 << bits) - 1
    for byte in data:
        acc = (acc << 8) | byte
        nbits += 8
        while nbits >= bits:
            nbits -= bits
            out.append((acc >> nbits) & mask)
    if nbits:
        out.append((acc << (bits - nbits)) & mask)
    return out


def g2b(glyphs: Sequence[int], original_length: int, bits: int = BITS) -> bytes:
    out = bytearray()
    acc = 0
    nbits = 0
    for glyph in glyphs:
        acc = (acc << bits) | glyph
        nbits += bits
        while nbits >= 8:
            nbits -= 8
            out.append((acc >> nbits) & 0xFF)
    if nbits:
        out.append((acc << (8 - nbits)) & 0xFF)
    return bytes(out[:original_length])


def pack_glyphs(glyphs: Sequence[int], bits: int = BITS) -> bytes:
    return g2b(glyphs, (len(glyphs) * bits + 7) // 8, bits)


def reverse_bits(value: int, width: int) -> int:
    out = 0
    for index in range(width):
        if value & (1 << index):
            out |= 1 << (width - 1 - index)
    return out


def g_r(data: Sequence[int]) -> list[int]:
    return list(reversed(data))


def g_n(data: Sequence[int], bits: int = BITS) -> list[int]:
    half = bits // 2
    mask = (1 << half) - 1
    return [((glyph & mask) << half) | (glyph >> half) for glyph in data]


def g_q(data: Sequence[int], bits: int = BITS) -> list[int]:
    half = bits // 2
    mask = (1 << half) - 1
    return [
        (reverse_bits(glyph >> half, half) << half) | reverse_bits(glyph & mask, half)
        for glyph in data
    ]


def xor_delta(data: Sequence[int]) -> list[int]:
    if not data:
        return []
    return [data[0], *(data[index] ^ data[index - 1] for index in range(1, len(data)))]


def xor_undelta(data: Sequence[int]) -> list[int]:
    if not data:
        return []
    out = [data[0]]
    for value in data[1:]:
        out.append(value ^ out[-1])
    return out


def rol(value: int, bits: int = BITS) -> int:
    mask = (1 << bits) - 1
    return ((value << 1) | (value >> (bits - 1))) & mask


def ror(value: int, bits: int = BITS) -> int:
    mask = (1 << bits) - 1
    return ((value >> 1) | ((value & 1) << (bits - 1))) & mask


def block_reverse(data: Sequence[int], block: int) -> list[int]:
    out: list[int] = []
    for start in range(0, len(data), block):
        out.extend(reversed(data[start : start + block]))
    return out


def even_odd(data: Sequence[int]) -> list[int]:
    return list(data[::2]) + list(data[1::2])


def undo_even_odd(data: Sequence[int]) -> list[int]:
    even_count = (len(data) + 1) // 2
    out = [0] * len(data)
    for index in range(even_count):
        out[index * 2] = data[index]
    for index in range(even_count, len(data)):
        out[(index - even_count) * 2 + 1] = data[index]
    return out


def qprism_order(block_count: int, seed: bytes) -> list[int]:
    keyed: list[tuple[bytes, int]] = []
    for index in range(block_count):
        preimage = b"QPRISM_GLYPH_V3|257|" + seed + index.to_bytes(8, "little")
        keyed.append((sha256_bytes(preimage), index))
    return [index for _, index in sorted(keyed)]


def qprism_apply(data: Sequence[int], seed: bytes) -> list[int]:
    block = 257
    block_count = len(data) // block
    out: list[int] = []
    for index in qprism_order(block_count, seed):
        out.extend(data[index * block : (index + 1) * block])
    out.extend(data[block_count * block :])
    return out


def qprism_inverse(data: Sequence[int], seed: bytes) -> list[int]:
    block = 257
    block_count = len(data) // block
    out = [0] * len(data)
    for packed_position, original_index in enumerate(qprism_order(block_count, seed)):
        out[original_index * block : (original_index + 1) * block] = data[
            packed_position * block : (packed_position + 1) * block
        ]
    out[block_count * block :] = data[block_count * block :]
    return out


def a_apply(index: int, data: Sequence[int], seed: bytes) -> list[int]:
    if index == 0:
        return list(data)
    if index == 1:
        return g_r(data)
    if index == 2:
        return xor_delta(data)
    if index == 3:
        return [rol(glyph) for glyph in reversed(data)]
    if index == 4:
        return g_n(data)
    if index == 5:
        return block_reverse(data, 256)
    if index == 6:
        return even_odd(data)
    if index == 7:
        return qprism_apply(data, seed)
    raise ValueError(f"invalid A-view {index}")


def a_inverse(index: int, data: Sequence[int], seed: bytes) -> list[int]:
    if index == 0:
        return list(data)
    if index == 1:
        return g_r(data)
    if index == 2:
        return xor_undelta(data)
    if index == 3:
        return list(reversed([ror(glyph) for glyph in data]))
    if index == 4:
        return g_n(data)
    if index == 5:
        return block_reverse(data, 256)
    if index == 6:
        return undo_even_odd(data)
    if index == 7:
        return qprism_inverse(data, seed)
    raise ValueError(f"invalid A-view {index}")


def residue_apply(data: Sequence[int], modulus: int, phase: int, stride: int) -> list[int]:
    if math.gcd(stride, modulus) != 1:
        raise ValueError("residue stride must be coprime with modulus")
    order = [(phase + step * stride) % modulus for step in range(modulus)]
    out: list[int] = []
    for residue in order:
        out.extend(data[residue::modulus])
    return out


def residue_inverse(data: Sequence[int], modulus: int, phase: int, stride: int) -> list[int]:
    order = [(phase + step * stride) % modulus for step in range(modulus)]
    out = [0] * len(data)
    cursor = 0
    for residue in order:
        count = 0 if residue >= len(data) else ((len(data) - 1 - residue) // modulus) + 1
        values = data[cursor : cursor + count]
        cursor += count
        for index, value in enumerate(values):
            out[residue + index * modulus] = value
    if cursor != len(data):
        raise AssertionError("residue inverse length mismatch")
    return out


def frequency_apply(
    data: Sequence[int], wavelength: int, frequency_numerator: int, phase: int
) -> list[int]:
    out: list[int] = []
    for block_index, start in enumerate(range(0, len(data), wavelength)):
        chunk = list(data[start : start + wavelength])
        if chunk:
            shift = (frequency_numerator * (block_index + 1) + phase) % len(chunk)
            out.extend(chunk[shift:] + chunk[:shift])
    return out


def frequency_inverse(
    data: Sequence[int], wavelength: int, frequency_numerator: int, phase: int
) -> list[int]:
    out: list[int] = []
    for block_index, start in enumerate(range(0, len(data), wavelength)):
        chunk = list(data[start : start + wavelength])
        if chunk:
            shift = (frequency_numerator * (block_index + 1) + phase) % len(chunk)
            out.extend(chunk[-shift:] + chunk[:-shift] if shift else chunk)
    return out


@dataclass(frozen=True)
class ViewDescriptor:
    ordinal: int
    view_id: st
    pid: st
    a_index: int
    wavelength: int
    frequency_numerator: int
    sector_phase: int
    lens_phase: int
    lens_stride: int

    @property
    def canonical(self) -> str:
        return (
            f"{self.view_id}|a={self.a_index}|w={self.wavelength}|"
            f"fn={self.frequency_numerator}|s={self.sector_phase}|"
            f"lp={self.lens_phase}|ls={self.lens_stride}"
        )


def build_descriptors(input_sha: str, count: int = MAX_VIEWS) -> list[ViewDescriptor]:
    if not 1 <= count <= MAX_VIEWS:
        raise ValueError("view count must be in 1..100")
    lens_strides = (1, 3, 7, 9, 11, 13, 17, 19)
    out: list[ViewDescriptor] = []
    for ordinal in range(count):
        view_id = f"VIEW-{ordinal:03d}"
        a_index = ordinal % 8
        wavelength = ordinal + 2  # all 100 descriptors have a distinct wavelength
        frequency_numerator = ordinal * 2 + 1
        sector_phase = (ordinal * 5 + 1) % 12
        lens_phase = (ordinal * 7 + 3) % 20
        lens_stride = lens_strides[(ordinal * 3 + 1) % len(lens_strides)]
        preimage = (
            f"OMEGA-GLYPH-VIEW-SIM-ID-V2|{input_sha}|{view_id}|{a_index}|{wavelength}|"
            f"{frequency_numerator}|{sector_phase}|{lens_phase}|"
            f"{lens_stride}"
        ).encode("ascii")
        pid = sha256(preimage)
        out.append(
            ViewDescriptor(
                ordinal,
                view_id,
                pid,
                a_index,
                wavelength,
                frequency_numerator,
                sector_phase,
                lens_phase,
                lens_stride,
            )
        )
    if len({descriptor.pid for descriptor in out}) != count:
        raise AssertionError("view PID collision")
    return out


def composite_apply(data: Sequence[int], descriptor: ViewDescriptor, seed: bytes) -> list[int]:
    viewed = a_apply(descriptor.a_index, data, seed)
    sectored = residue_apply(viewed, 12, descriptor.sector_phase, 1)
    lensed = residue_apply(sectored, 20, descriptor.lens_phase, descriptor.lens_stride)
    return frequency_apply(
        lensed,
        descriptor.wavelength,
        descriptor.frequency_numerator,
        descriptor.sector_phase + descriptor.lens_phase,
    )


def composite_inverse(data: Sequence[int], descriptor: ViewDescriptor, seed: bytes) -> list[int]:
    unfreq = frequency_inverse(
        data,
        descriptor.wavelength,
        descriptor.frequency_numerator,
        descriptor.sector_phase + descriptor.lens_phase,
    )
    unlens = residue_inverse(unfreq, 20, descriptor.lens_phase, descriptor.lens_stride)
    unsector = residue_inverse(unlens, 12, descriptor.sector_phase, 1)
    return a_inverse(descriptor.a_index, unsector, seed)


def deterministic_canary(length: int = 16384) -> bytes:
    out = bytearray()
    state = sha256_bytes(b"OMEGA-GLYPH-100VIEW-CANARY-V1")
    counter = 0
    while len(out) < length:
        state = sha256_bytes(state + counter.to_bytes(8, "little"))
        out.extend(state)
        counter += 1
    return bytes(out[:length])


def parse_numeric_evidence(data: bytes) -> tuple[dict[int, list[int]], list[dict[str, object]]]:
    token_re = re.compile(rb"(?<![0-9])(?:7680|840|120|20|12|8|7)(?![0-9])")
    occurrences: dict[int, list[int]] = {number: [] for number in TARGET_NUMBERS}
    for match in token_re.finditer(data):
        occurrences[int(match.group(0))].append(match.start())
    candidates: list[dict[str, object]] = []
    offset = 0
    for line_number, raw_line in enumerate(data.splitlines(keepends=True), 1):
        body = raw_line.rstrip(b"\r\n")
        matches = list(token_re.finditer(body))
        if len(matches) >= 2:
            candidates.append(
                {
                    "line": line_number,
                    "offset": offset,
                    "tokens": ",".join(match.group(0).decode("ascii") for match in matches),
                    "line_sha256": sha256(body),
                    "exact_text": body.decode("utf-8", errors="replace"),
                }
            )
        offset += len(raw_line)
    return occurrences, candidates


def gf_rank(matrix: Sequence[Sequence[int]], prime: int = FIELD) -> int:
    if not matrix:
        return 0
    work = [[value % prime for value in row_values] for row_values in matrix]
    rows = len(work)
    columns = len(work[0])
    rank = 0
    for column in range(columns):
        pivot = next((index for index in range(rank, rows) if work[index][column]), None)
        if pivot is None:
            continue
        work[rank], work[pivot] = work[pivot], work[rank]
        inverse = pow(work[rank][column], -1, prime)
        work[rank] = [(value * inverse) % prime for value in work[rank]]
        for row_index in range(rows):
            if row_index != rank and work[row_index][column]:
                factor = work[row_index][column]
                work[row_index] = [
                    (left - factor * right) % prime
                    for left, right in zip(work[row_index], work[rank])
                ]
        rank += 1
        if rank == rows:
            break
    return rank


def gf_inverse(matrix: Sequence[Sequence[int]], prime: int = FIELD) -> list[list[int]]:
    size = len(matrix)
    if size == 0 or any(len(row_values) != size for row_values in matrix):
        raise ValueError("inverse requires square matrix")
    work = [
        [value % prime for value in row_values]
        + [1 if row_index == column else 0 for column in range(size)]
        for row_index, row_values in enumerate(matrix)
    ]
    for column in range(size):
        pivot = next((index for index in range(column, size) if work[index][column]), None)
        if pivot is None:
            raise ValueError("singular matrix")
        work[column], work[pivot] = work[pivot], work[column]
        inverse = pow(work[column][column], -1, prime)
        work[column] = [(value * inverse) % prime for value in work[column]]
        for row_index in range(size):
            if row_index != column and work[row_index][column]:
                factor = work[row_index][column]
                work[row_index] = [
                    (left - factor * right) % prime
                    for left, right in zip(work[row_index], work[column])
                ]
    return [row_values[size:] for row_values in work]


def mat_vec(matrix: Sequence[Sequence[int]], vector: Sequence[int]) -> list[int]:
    return [sum(a * b for a, b in zip(row_values, vector)) % FIELD for row_values in matrix]


def projection_rows() -> list[list[int]]:
    # 100 Vandermonde rows at distinct nonero field coordinates.  Every first
    # 60-row prefix is full rank over GF(257).
    return [[pow(row_index + 1, column, FIELD) for column in range(DIMENSIONS)] for row_index in range(100)]


def duplicate_rows(unique_rows: Sequence[Sequence[int]]) -> list[list[int]]:
    return [list(unique_rows[index % 10]) for index in range(100)]


def shuffle_order(seed: bytes, length: int) -> list[int]:
    keyed = []
    for index in range(length):
        keyed.append((sha256_bytes(b"SHUFFLE-ORDER-V1|" + seed + index.to_bytes(4, "little")), index))
    return [index for _, index in sorted(keyed)]


def case_vector(seed: bytes, case_index: int) -> list[int]:
    values: list[int] = []
    counter = 0
    while len(values) < DIMENSIONS:
        digest = sha256_bytes(
            b"GF257-60D-CASE-V1|" + seed + case_index.to_bytes(4, "little") + counter.to_bytes(4, "little")
        )
        for start in range(0, len(digest) - 1, 2):
            values.append(int.from_bytes(digest[start : start + 2], "little") % FIELD)
            if len(values) == DIMENSIONS:
                break
        counter += 1
    return values


def first_independent_indices(matrix: Sequence[Sequence[int]], needed: int = DIMENSIONS) -> list[int]:
    selected: list[int] = []
    rank = 0
    for index, row_values in enumerate(matrix):
        candidate = [matrix[item] for item in selected] + [row_values]
        new_rank = gf_rank(candidate)
        if new_rank > rank:
            selected.append(index)
            rank = new_rank
        if rank == needed:
            break
    if rank != needed:
        return []
    return selected


@dataclass
class ProjectionResult:
    rows: list[str]
    leaves: list[str]
    unique_rank: int
    duplicate_rank: int
    unique_restores: int
    shuffled_restores: int
    binding_restores: int
    misbound_nonabstaining_wrong: int
    case_unique: int


def run_projection(seed: bytes) -> ProjectionResult:
    unique = projection_rows()
    duplicate = duplicate_rows(unique)
    order = shuffle_order(seed, 100)
    shuffled = [unique[index] for index in order]
    controls: dict[str, list[list[int]]] = {
        "UNIQUE": unique,
        "DUP": duplicate,
        "SHUFFLE_ORDER": shuffled,
        "SHUFFLE_BINDING": unique,
        # Capacity-matched 100x60 scalar lane with no measurement direction.
        # All-zero rows represent ledger allocation, not observations.
        "LEDGER_ONLY": [[0] * DIMENSIONS for _ in range(100)],
    }
    rows: list[str] = []
    leaves: list[str] = []
    for control_name, control_matrix in controls.items():
        for checkpoint in CHECKPOINTS:
            matrix_prefix = control_matrix[:checkpoint] if control_matrix else []
            rank = gf_rank(matrix_prefix)
            rank_row = row(
                "RANKCHECK",
                control=control_name,
                rows=checkpoint,
                rank=rank,
                nullity=DIMENSIONS - rank,
                field=FIELD,
                dimensions=DIMENSIONS,
                classification="MEASURED_SIMULATION",
            )
            rows.append(rank_row)
            leaves.append(sha256(rank_row.encode("utf-8")))

    unique_indices = first_independent_indices(unique)
    shuffled_indices = first_independent_indices(shuffled)
    unique_inverse = gf_inverse([unique[index] for index in unique_indices])
    shuffled_inverse = gf_inverse([shuffled[index] for index in shuffled_indices])
    unique_restores = 0
    shuffled_restores = 0
    binding_restores = 0
    misbound_nonabstaining_wrong = 0
    case_digests: set[str] = set()
    for case_index in range(100):
        vector = case_vector(seed, case_index)
        vector_bytes = b"".join(value.to_bytes(2, "little") for value in vector)
        vector_digest = sha256(vector_bytes)
        case_digests.add(vector_digest)
        y_unique = mat_vec(unique, vector)
        recovered_unique = mat_vec(unique_inverse, [y_unique[index] for index in unique_indices])
        unique_ok = recovered_unique == vector
        unique_restores += int(unique_ok)

        y_shuffled = [y_unique[index] for index in order]
        recovered_shuffled = mat_vec(shuffled_inverse, [y_shuffled[index] for index in shuffled_indices])
        shuffled_ok = recovered_shuffled == vector
        shuffled_restores += int(shuffled_ok)

        # Binding control keeps all 100 row vectors and all 100 measurements,
        # but cyclically binds each measurement to the wrong row.
        y_misbound = y_unique[1:] + y_unique[:1]
        recovered_binding = mat_vec(unique_inverse, [y_misbound[index] for index in unique_indices])
        binding_ok = recovered_binding == vector
        binding_restores += int(binding_ok)
        if not binding_ok:
            misbound_nonabstaining_wrong += 1

        case_row = row(
            "PROJECTIONCASE",
            case=f"CASE-{case_index:03d}",
            vector_sha256=vector_digest,
            unique_restore=int(unique_ok),
            shuffle_order_restore=int(shuffled_ok),
            shuffle_binding_restore=int(binding_ok),
            duplicate_restore="NOT_ATTEMPTED_RANK10",
            ledger_only_restore="NOT_ATTEMPTED_RANK0",
            generation="DOMAIN_SEPARATED_DETERMINISTIC",
            linear_independence_claim="NONE_100_CASES_IN_60D",
            classification="MEASURED_SIMULATION",
        )
        rows.append(case_row)
        leaves.append(sha256(case_row.encode("utf-8")))

    if unique_restores != 100 or shuffled_restores != 100:
        raise AssertionError("full-rank recovery gate failed")
    if len(case_digests) != 100:
        raise AssertionError("case generation collision")
    return ProjectionResult(
        rows,
        leaves,
        gf_rank(unique),
        gf_rank(duplicate),
        unique_restores,
        shuffled_restores,
        binding_restores,
        misbound_nonabstaining_wrong,
        len(case_digests),
    )


def logical_ranges(count: int) -> list[tuple[int, int, int]]:
    slot_size = 10**198
    return [(index * slot_size, (index + 1) * slot_size - 1, slot_size) for index in range(count)]


def omega_commit(input_sha: str, leaves: Iterable[str]) -> str:
    message = bytearray(DOMAIN)
    message.extend(bytes.fromhex(input_sha))
    sorted_leaves = sorted(leaves)
    message.extend(len(sorted_leaves).to_bytes(8, "little"))
    for leaf in sorted_leaves:
        leaf_bytes = bytes.fromhex(leaf)
        message.extend(len(leaf_bytes).to_bytes(4, "little"))
        message.extend(leaf_bytes)
    return sha256(bytes(message))


def indexed_row_leaves(rows: Sequence[str]) -> list[str]:
    return [
        sha256(index.to_bytes(8, "little") + body.encode("utf-8"))
        for index, body in enumerate(rows)
    ]


def build_hbi(hbp_bytes: bytes, target_sha: str) -> bytes:
    lines = hbp_bytes.splitlines(keepends=True)
    header = row(
        "HBIHDR",
        schema="OMEGA-GLYPH-100VIEW-OFFSETS-V1",
        target="OMEGA-GLYPH-100VIEW.hbp",
        target_bytes=len(hbp_bytes),
        target_sha256=target_sha,
        rows=len(lines),
    )
    output = [header]
    offset = 0
    for index, line_bytes in enumerate(lines, 1):
        body = line_bytes[:-1] if line_bytes.endswith(b"\n") else line_bytes
        output.append(
            row(
                "HBIOFFSET",
                row=index,
                offset=offset,
                length=len(body),
                lf=int(line_bytes.endswith(b"\n")),
                row_sha256=sha256(body),
            )
        )
        offset += len(line_bytes)
    return ("\n".join(output) + "\n").encode("utf-8")


@dataclass
class ExperimentResult:
    omega: st
    input_sha: st
    view_count: int
    unique_canary: int
    unique_glyph: int
    projection: ProjectionResult
    hbp_sha: st
    hbi_sha: st


def run_experiment(
    glyph_file: Path,
    out_dir: Path,
    provenance_label: str,
    view_count: int = MAX_VIEWS,
) -> ExperimentResult:
    data = glyph_file.read_bytes()
    if not data:
        raise ValueError("glyph input must not be empty")
    input_sha = sha256(data)
    seed = sha256_bytes(pack_glyphs(b2g(data)))
    glyphs = b2g(data)
    byte_h0 = shannon_h0(list(data))
    glyph_h0 = shannon_h0(glyphs)
    packed_glyph_bytes = len(pack_glyphs(glyphs))
    canary_bytes = deterministic_canary()
    canary = b2g(canary_bytes)
    canary_seed = sha256_bytes(pack_glyphs(canary))
    descriptors = build_descriptors(input_sha, view_count)
    occurrences, relation_candidates = parse_numeric_evidence(data)
    output_rows = [
        row(
            "OMEGAGLYPHHDR",
            schema="OMEGA-GLYPH-100VIEW-SIM-V2",
            mode="FULL_INPUT_DEPENDENT_TRANSFORM_SIMULATION",
            claims_gate="LOCAL_NO_LIVE_ACTION",
            source=A_VIEW_SOURCE,
            source_sha256=A_VIEW_SOURCE_SHA256,
            source_repository=A_VIEW_SOURCE_REPOSITORY,
            source_commit=A_VIEW_SOURCE_COMMIT,
            source_path=A_VIEW_SOURCE_PATH,
            source_scope="FUNCTION_PORT_ONLY",
            views=view_count,
            dimensions=DIMENSIONS,
            field=FIELD,
            input_dependency="FULL_INPUT_SHA_AND_FULL_INPUT_GLYPH_SEED",
            causal=0,
            codec_claim=0,
            floor_ladder_64_256_1024_4096="NOT_IMPLEMENTED",
            projection_glyph_view_link=0,
        ),
        row(
            "INPUTFREEZE",
            file=glyph_file.name,
            bytes=len(data),
            sha256=input_sha,
            provenance_label=provenance_label,
            copied_as="GLYPH-INPUT.bin",
            classification="MEASURED_LOCAL_BYTES",
            prediction_test=0,
            target_leakage="SYNTHETIC_FIXTURE_CONTAINS_TARGETS_BY_DESIGN",
        ),
        row(
            "BOUNDARY",
            measured="FUNCTION_PORT_A_VIEW_INVERSES_AND_DISCONNECTED_GF257_CONTROL",
            designed="MOD12_MOD20_FREQUENCY_TRANSFORM_AND_1E200_ADDRESS_PARTITION",
            unverified="INTEGRATED_FLOORS_OMEGA_GNN_OMNIBIT_GLYPH_NULLSPACE_PHYSICAL_COSMOLOGICAL_PREDICTION",
        ),
        row(
            "ENTROPYINPUT",
            byte_alphabet=256,
            byte_symbols=len(data),
            byte_h0_bits_per_byte=f"{byte_h0:.12f}",
            glyph_alphabet=1 << BITS,
            glyph_bits=BITS,
            glyph_symbols=len(glyphs),
            glyph_h0_bits_per_glyph=f"{glyph_h0:.12f}",
            packed_glyph_bytes=packed_glyph_bytes,
            residual_archive_bytes="NOT_IMPLEMENTED",
            decoder_catalog_model_charge="NOT_IMPLEMENTED",
            compression_claim=0,
            classification="MEASURED_SIMULATION",
        ),
    ]
    leaves: list[str] = []
    for number in TARGET_NUMBERS:
        token_row = row(
            "NUMTOKEN",
            value=number,
            count=len(occurrences[number]),
            byte_offsets=",".join(str(offset) for offset in occurrences[number]) or "NONE",
            semantics="NOT_INFERRED",
            classification="MEASURED_LOCAL_PARSE",
        )
        output_rows.append(token_row)
        leaves.append(sha256(token_row.encode("utf-8")))
    for candidate in relation_candidates:
        relation_row = row(
            "RELATIONCANDIDATE",
            line=candidate["line"],
            byte_offset=candidate["offset"],
            tokens=candidate["tokens"],
            line_sha256=candidate["line_sha256"],
            exact_text=candidate["exact_text"],
            semantics="CO_OCCURRENCE_ONLY_NOT_INFERRED",
            classification="MEASURED_LOCAL_PARSE",
        )
        output_rows.append(relation_row)
        leaves.append(sha256(relation_row.encode("utf-8")))

    glyph_digests: set[str] = set()
    canary_digests: set[str] = set()
    glyph_view_h0s: list[float] = []
    descriptor_by_view = {descriptor.view_id: descriptor for descriptor in descriptors}
    descriptor_by_pid = {descriptor.pid: descriptor for descriptor in descriptors}
    for descriptor in descriptors:
        descriptor_row = row(
            "VIEWDESC",
            view_id=descriptor.view_id,
            pid=descriptor.pid,
            pid_semantics="SIMULATION_DERIVED_NOT_REGISTERED",
            a_view=A_NAMES[descriptor.a_index],
            a_index=descriptor.a_index,
            wavelength=descriptor.wavelength,
            frequency_numerator=descriptor.frequency_numerator,
            sector_phase=descriptor.sector_phase,
            lens_phase=descriptor.lens_phase,
            lens_stride=descriptor.lens_stride,
            sector_operator="MOD12_RESIDUE_PERMUTATION_SIM",
            lens_operator="MOD20_RESIDUE_PERMUTATION_SIM",
            frequency_operator="SIMULATED_BLOCK_ROTATION",
            mode="SIMULATION_ONLY",
        )
        output_rows.append(descriptor_row)
        glyph_view = composite_apply(glyphs, descriptor, seed)
        glyph_restore = composite_inverse(glyph_view, descriptor, seed)
        canary_view = composite_apply(canary, descriptor, canary_seed)
        canary_restore = composite_inverse(canary_view, descriptor, canary_seed)
        if glyph_restore != glyphs or g2b(glyph_restore, len(data)) != data:
            raise AssertionError(f"glyph inverse failed for {descriptor.view_id}")
        if canary_restore != canary or g2b(canary_restore, len(canary_bytes)) != canary_bytes:
            raise AssertionError(f"canary inverse failed for {descriptor.view_id}")
        glyph_digest = sha256(pack_glyphs(glyph_view))
        canary_digest = sha256(pack_glyphs(canary_view))
        glyph_view_h0 = shannon_h0(glyph_view)
        glyph_digests.add(glyph_digest)
        canary_digests.add(canary_digest)
        glyph_view_h0s.append(glyph_view_h0)
        result_row = row(
            "VIEWRESULT",
            view_id=descriptor.view_id,
            pid=descriptor.pid,
            glyph_digest=glyph_digest,
            canary_digest=canary_digest,
            glyph_inverse=1,
            canary_inverse=1,
            output_glyphs=len(glyph_view),
            glyph_h0_bits_per_glyph=f"{glyph_view_h0:.12f}",
            classification="MEASURED_SIMULATION",
        )
        output_rows.append(result_row)
        leaves.append(sha256(result_row.encode("utf-8")))
    if len(canary_digests) != view_count:
        raise AssertionError(f"canary transform collision: {len(canary_digests)}/{view_count}")
    entropy_views_row = row(
        "ENTROPYVIEWS",
        glyph_alphabet=1 << BITS,
        units="BITS_PER_10BIT_GLYPH",
        min_marginal_h0=f"{min(glyph_view_h0s):.12f}",
        max_marginal_h0=f"{max(glyph_view_h0s):.12f}",
        bijection_implies_equal_marginal_h0=0,
        compression_claim=0,
        classification="MEASURED_SIMULATION",
    )
    output_rows.append(entropy_views_row)
    leaves.append(sha256(entropy_views_row.encode("utf-8")))
    replay_gate = row(
        "REPLAYGATE",
        view_id_resolved=sum(descriptor_by_view[item.view_id] == item for item in descriptors),
        pid_resolved=sum(descriptor_by_pid[item.pid] == item for item in descriptors),
        unique_pids=len(descriptor_by_pid),
        result="PASS",
        replay_cli="--replay-id_VIEW_OR_PID",
    )
    output_rows.append(replay_gate)
    leaves.append(sha256(replay_gate.encode("utf-8")))
    uniqueness_row = row(
        "VIEWUNIQUENESS",
        descriptors=view_count,
        unique_canary_digests=len(canary_digests),
        unique_glyph_digests=len(glyph_digests),
        canary_gate="PASS",
        glyph_collision_interpretation="INPUT_DEPENDENT_NO_SEMANTICS_INFERRED",
    )
    output_rows.append(uniqueness_row)
    leaves.append(sha256(uniqueness_row.encode("utf-8")))

    address_ranges = logical_ranges(view_count)
    for descriptor, (start, end, count) in zip(descriptors, address_ranges):
        range_row = row(
            "LOGICALRANGE",
            view_id=descriptor.view_id,
            pid=descriptor.pid,
            start=start,
            end=end,
            count=count,
            model="EXACT_INTEGER_ADDRESS_RANGE",
            enumeration=0,
            spawn=0,
            classification="DESIGN_EXACT_ARITHMETIC",
        )
        output_rows.append(range_row)
        leaves.append(sha256(range_row.encode("utf-8")))
    output_rows.append(
        row(
            "LOGICALCASCADE",
            slots=view_count,
            per_slot=10**198,
            union_count=view_count * 10**198,
            target_1e200=int(view_count == 100),
            partition_arithmetic="EXACT",
            enumeration=0,
            agents_enumerated_by_this_experiment=0,
            agents_spawned_by_this_experiment=0,
            physical_claim=0,
            materialized_kernels="OUT_OF_SCOPE_NOT_DENIED",
            interpretation="PARTITION_ARITHMETIC_ONLY_NOT_RUNTIME_OR_PHYSICAL_SCALE",
        )
    )

    projection = run_projection(bytes.fromhex(input_sha))
    output_rows.append(
        row(
            "PROJECTIONHDR",
            mode="SIMULATION_ONLY",
            field=FIELD,
            dimensions=DIMENSIONS,
            rows=100,
            cases=100,
            input_seed_relation="INPUT_SHA_SEEDS_CASES_BUT_NO_GLYPH_VIEW_MEASUREMENTS",
            glyph_embedding="NONE",
            view_measurements_consumed=0,
            unique_generation="VANDERMONDE_DISTINCT_FIELD_COORDINATES",
            case_semantics="100_UNIQUE_DETERMINISTIC_NOT_INDEPENDENT",
            controls="UNIQUE,DUP,SHUFFLE_ORDER,SHUFFLE_BINDING,LEDGER_ONLY",
            equal_measurement_rows_per_control=100,
            scalar_budget_per_control="6000_GF257_ELEMENTS",
            optimization_budget="NONE",
            factorial_claim=0,
            qprism_relation="DISCONNECTED_GF257_CONTROL_NOT_GLYPH_QPRISM",
            glyph_nullspace_claim=0,
        )
    )
    output_rows.extend(
        (
            row("CONTROLDEF", control="UNIQUE", capacity="100x60_GF257", binding="CORRECT", expected_rank=60),
            row("CONTROLDEF", control="DUP", capacity="100x60_GF257", binding="CORRECT_10_ROWS_REPEATED", expected_rank=10),
            row("CONTROLDEF", control="SHUFFLE_ORDER", capacity="100x60_GF257", binding="CORRECT_ROWS_AND_VALUES_SHUFFLED_TOGETHER", expected_rank=60),
            row("CONTROLDEF", control="SHUFFLE_BINDING", capacity="100x60_GF257", binding="INCORRECT_VALUES_CYCLICALLY_MISBOUND", expected_rank=60),
            row("CONTROLDEF", control="LEDGER_ONLY", capacity="100x60_GF257", binding="ALL_ZERO_NO_MEASUREMENT_DIRECTION", expected_rank=0),
        )
    )
    output_rows.extend(projection.rows)
    leaves.extend(projection.leaves)
    projection_gate = row(
        "PROJECTIONGATE",
        unique_rank=projection.unique_rank,
        unique_nullity=DIMENSIONS - projection.unique_rank,
        duplicate_rank=projection.duplicate_rank,
        duplicate_nullity=DIMENSIONS - projection.duplicate_rank,
        unique_restores=projection.unique_restores,
        shuffle_order_restores=projection.shuffled_restores,
        shuffle_binding_restores=projection.binding_restores,
        cases=100,
        unique_case_digests=projection.case_unique,
        result="PASS",
    )
    output_rows.append(projection_gate)
    leaves.append(sha256(projection_gate.encode("utf-8")))
    misbinding_row = row(
        "MISBINDINGCONTROL",
        implementation="SYNTHETIC_GF257_ROW_VALUE_MISBINDING",
        misbound_nonabstaining_wrong=projection.misbound_nonabstaining_wrong,
        false_restore_claims=0,
        insufficient_rank_abstentions=200,
        controls="DUP_PLUS_LEDGER_ONLY_ACROSS_100_CASES",
        semantics="WRONG_RESTORE_COUNTER_NO_CONFIDENCE_SCORE_NO_LIVE_GNN",
    )
    output_rows.append(misbinding_row)
    leaves.append(sha256(misbinding_row.encode("utf-8")))

    indexed_semantic_leaves = indexed_row_leaves(output_rows)
    omega = omega_commit(input_sha, indexed_semantic_leaves)
    output_rows.extend(
        (
            row(
                "OMEGACOMMIT",
                domain="OMEGA-GLYPH-100VIEW-V2",
                input_sha256=input_sha,
                leaves=len(indexed_semantic_leaves),
                leaf_order="SORTED_LEXICOGRAPHIC",
                row_order_binding="ROW_INDEX_IN_LEAF_PREIMAGE",
                commitment_scope="ALL_HBP_ROWS_BEFORE_OMEGACOMMIT",
                committed_rows=len(output_rows),
                descriptor_identity="FULL_SHA256_SIMULATION_DERIVED_NOT_REGISTERED",
                omega_sha256=omega,
                reversible_encoding=0,
                meaning="COMMITMENT_ONLY",
            ),
            row(
                "OMEGAGLYPHFTR",
                status="PASS",
                mode="FULL_INPUT_DEPENDENT_TRANSFORM_SIMULATION",
                views=view_count,
                byte_exact_views=view_count,
                unique_canary_digests=len(canary_digests),
                unique_glyph_digests=len(glyph_digests),
                projection_cases=100,
                omega_sha256=omega,
                live_writes=0,
                causal=0,
                codec_claim=0,
                original_input_required_for_replay=1,
                projection_glyph_view_link=0,
                production_fischer=0,
                physical_claims=0,
            ),
        )
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    frozen = out_dir / "GLYPH-INPUT.bin"
    shutil.copyfile(glyph_file, frozen)
    if sha256(frozen.read_bytes()) != input_sha:
        raise AssertionError("input freeze mismatch")
    hbp_path = out_dir / "OMEGA-GLYPH-100VIEW.hbp"
    hbp_bytes = ("\n".join(output_rows) + "\n").encode("utf-8")
    hbp_path.write_bytes(hbp_bytes)
    hbp_sha = sha256(hbp_bytes)
    hbi_path = out_dir / "OMEGA-GLYPH-100VIEW.hbi"
    hbi_bytes = build_hbi(hbp_bytes, hbp_sha)
    hbi_path.write_bytes(hbi_bytes)
    hbi_sha = sha256(hbi_bytes)
    results_path = out_dir / "RESULTS.md"
    results = f"""# Omega glyph 100-view simulation result

- Status: `MEASURED_SIMULATION` / `PASS`
- Transform class: `FULL_INPUT_DEPENDENT_TRANSFORM`
- Causal codec: `NO`; integrated 64/256/1024/4096 floor ladder: `NOT_IMPLEMENTED`
- Frozen input: `{len(data)}` bytes, SHA-256 `{input_sha}`
- Provenance label: `{provenance_label}`
- Views: `{view_count}`; byte-exact inverses: `{view_count}`
- Unique canary view digests: `{len(canary_digests)}/{view_count}`
- Unique glyph view digests: `{len(glyph_digests)}/{view_count}` (input-dependent)
- Byte H0: `{byte_h0:.12f}` bits/byte over declared alphabet 256
- 10-bit glyph H0: `{glyph_h0:.12f}` bits/glyph over declared alphabet 1024
- View marginal glyph H0 range: `{min(glyph_view_h0s):.12f}..{max(glyph_view_h0s):.12f}` bits/10-bit glyph
- Residual/archive/model/decoder charge: `NOT_IMPLEMENTED`; no compression score claimed
- GF(257) UNIQUE rank/nullity: `{projection.unique_rank}/{DIMENSIONS - projection.unique_rank}`
- GF(257) DUP rank/nullity: `{projection.duplicate_rank}/{DIMENSIONS - projection.duplicate_rank}`
- Joint recovery: UNIQUE `{projection.unique_restores}/100`; SHUFFLE_ORDER `{projection.shuffled_restores}/100`
- SHUFFLE_BINDING original restores: `{projection.binding_restores}/100`
- Misbound non-abstaining wrong restores: `{projection.misbound_nonabstaining_wrong}`
- Indexed-row, sorted-leaf Omega commitment: `{omega}`

## Boundaries

The eight A-views are a function-only port of `{A_VIEW_SOURCE}` from
`{A_VIEW_SOURCE_REPOSITORY}` at commit `{A_VIEW_SOURCE_COMMIT}`, path
`{A_VIEW_SOURCE_PATH}`, source SHA-256 `{A_VIEW_SOURCE_SHA256}`.
The modulo-12, modulo-20, and frequency operators are reversible simulations—not
ports of the Rust 12-sector or 20-lens family training semantics.
The GF(257) rank/recovery lane is a disconnected SHA-seeded linear-algebra control:
it consumes no glyph-view measurements and makes no glyph-nullspace claim.
The transform derives descriptors and seeds from the complete input and requires
the original input for replay; it is not causal and is not a codec.
The `1e200` quantity is an exact address-space partition (`100 * 1e198`).
Partition arithmetic is exact; this experiment enumerates or spawns zero agents,
and the partition is not a physical-scale claim.
This does not deny separately materialized kernels or live processes; those finite
runtime measurements are outside this receipt.
The synthetic fixture contains the numeric targets by design.  Token parsing records
co-occurrence without semantics and is not a prediction test.
This result does not establish the integrated four-floor system, a live
Omega-GNN/OmniBit benefit, physical particles, cosmology, compression, novelty, o
award significance.
Invertibility is not asserted to preserve marginal H0.
"""
    write_lf(results_path, results)
    files = (frozen, hbp_path, hbi_path, results_path)
    sums = "".join(f"{sha256(path.read_bytes())}  {path.name}\n" for path in files)
    sums_path = out_dir / "SHA256SUMS"
    write_lf(sums_path, sums)
    write_lf(out_dir / "SHA256SUMS.sha256", f"{sha256(sums_path.read_bytes())}  SHA256SUMS\n")
    return ExperimentResult(
        omega,
        input_sha,
        view_count,
        len(canary_digests),
        len(glyph_digests),
        projection,
        hbp_sha,
        hbi_sha,
    )


def replay(glyph_file: Path, replay_id: str, view_count: int = MAX_VIEWS) -> str:
    data = glyph_file.read_bytes()
    input_sha = sha256(data)
    descriptors = build_descriptors(input_sha, view_count)
    matches = [item for item in descriptors if item.view_id == replay_id or item.pid == replay_id]
    if len(matches) != 1:
        raise ValueError(f"unknown or ambiguous replay id {replay_id}")
    descriptor = matches[0]
    glyphs = b2g(data)
    seed = sha256_bytes(pack_glyphs(glyphs))
    viewed = composite_apply(glyphs, descriptor, seed)
    restored = composite_inverse(viewed, descriptor, seed)
    exact = restored == glyphs and g2b(restored, len(data)) == data
    return row(
        "VIEWREPLAY",
        requested_id=replay_id,
        view_id=descriptor.view_id,
        pid=descriptor.pid,
        output_sha256=sha256(pack_glyphs(viewed)),
        byte_exact=int(exact),
        mode="SIMULATION_ONLY",
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--glyph-file", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--provenance-label", required=True)
    parser.add_argument("--view-count", type=int, default=MAX_VIEWS)
    parser.add_argument("--replay-id", help="Replay one deterministic view by VIEW-nnn or PID")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.replay_id:
        print(replay(args.glyph_file, args.replay_id, args.view_count))
        return 0
    result = run_experiment(
        args.glyph_file,
        args.out_dir,
        args.provenance_label,
        args.view_count,
    )
    print(
        row(
            "OMEGAGLYPHPASS",
            views=result.view_count,
            unique_canary=result.unique_canary,
            unique_glyph=result.unique_glyph,
            projection_rank=result.projection.unique_rank,
            omega=result.omega,
            hbp_sha256=result.hbp_sha,
            hbi_sha256=result.hbi_sha,
            mode="SIMULATION_ONLY",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
