#!/usr/bin/env python3
"""Build a bounded cold heritage/architecture/astronomy source corpus.

The default build is offline. Source payloads must already be staged beneath
``artifacts/raw/<source_id>``. Pointer-only and held source rows can never
contribute bytes. The optional fetch phase is explicit, source-scoped, capped,
and restricted to catalog entries that already carry an allow policy.

This program prepares source slices and receipts. It does not train a model,
call a provider or GNN, absorb into GitRAM/Omega, promote, or mint.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import tarfile
import tempfile
import unicodedata
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence


SCHEMA = "ASOLARIA-HERITAGE-ARCHITECTURE-COSMOS-COLD-V1"
PROJECT = Path(__file__).resolve().parent
DEFAULT_CONTRACT = PROJECT / "HERITAGE-COSMOS-CONTRACT.hbp"
DEFAULT_CATALOG = PROJECT / "SOURCE-CATALOG.hbp"
DEFAULT_BODY_MAP = PROJECT / "BODY-MAP.hbp"
DEFAULT_RAW = PROJECT / "artifacts" / "raw"
DEFAULT_OUTPUT = PROJECT / "artifacts" / "cold-corpus"

SLICE_COUNT = 1024
SLICE_BYTES = 4096
DOMAIN_SLICE_TARGETS = {
    "HERITAGE_SCRIPT": 205,
    "ARCHITECTURE": 307,
    "ASTRONOMY_PI": 512,
}
PAYLOAD_ALLOW_POLICIES = {
    "ALLOW_COLD",
    "ALLOW_COLD_FILTERED",
    "ALLOW_COLD_METADATA",
    "ALLOW_COLD_RESEARCH_ONLY",
    "OWNER_AUTHORIZED_LOCAL",
}
METADATA_ONLY_POLICIES = {"POINTER_ONLY", "HELD_LICENSE", "HELD_COMMUNITY"}
TEXT_EXTENSIONS = {
    ".atf",
    ".csv",
    ".hbi",
    ".hbp",
    ".html",
    ".json",
    ".jsonl",
    ".js",
    ".mjs",
    ".cjs",
    ".md",
    ".nt",
    ".py",
    ".rdf",
    ".rst",
    ".rs",
    ".tei",
    ".tsv",
    ".ttl",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
ARCHIVE_EXTENSIONS = {".zip", ".tar", ".tgz", ".gz"}
MAX_NORMALIZED_PER_SOURCE = 24 * 1024 * 1024
MAX_FILE_SAMPLE_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_MEMBER_BYTES = 8 * 1024 * 1024
BLOCK_BYTES = 16 * 1024
MIX_SEED = b"ASOLARIA-HERITAGE-ARCHITECTURE-COSMOS-MIX-V1"
DERIVED_BODY_SOURCES = {
    "DERIVED_FROM_ALLOWED_ARCHITECTURE_SLICES": "ARCHITECTURE",
}
BODY_FAMILY_DOMAINS = {
    "HERITAGE_8": "HERITAGE_SCRIPT",
    "ARCHITECTURE_12": "ARCHITECTURE",
    "ASTRONOMY_PI_20": "ASTRONOMY_PI",
}

RECEIPT_STEMS = (
    "CONTRACT-SNAPSHOT",
    "SOURCE-CATALOG-SNAPSHOT",
    "BODY-MAP-SNAPSHOT",
    "SOURCE-USE",
    "SYSTEM-BINDINGS",
    "SLICE-MAP",
    "BODY-LANGUAGES",
    "01-INFORMATION-EXPOSURES",
    "02-MODEL-LOCAL-RELATIONS",
    "03-RECURRENT-STATE-TRANSITIONS",
    "04-UPWARD-LINEAGE-LINKS",
    "05-EXTERNAL-MODEL-CALLS",
    "06-RIGHTS-COMMUNITY",
    "COLD-CORPUS-ROOT",
)


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
    if isinstance(value, (tuple, list, set)):
        value = ",".join(str(item) for item in value)
    return urllib.parse.quote(str(value), safe="-._~,:;+/@[]")


def hbp_row(kind: str, **fields: Any) -> str:
    parts = [safe(kind)]
    for key in sorted(fields):
        parts.append(f"{safe(key)}={safe(fields[key])}")
    if "json" not in fields:
        parts.append("json=0")
    return "|".join(parts)


def parse_hbp_line(line: str) -> tuple[str, dict[str, str]]:
    parts = line.rstrip("\r\n").split("|")
    kind = urllib.parse.unquote(parts[0])
    fields: dict[str, str] = {}
    for part in parts[1:]:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        fields[urllib.parse.unquote(key)] = urllib.parse.unquote(value)
    return kind, fields


def read_hbp_rows(path: Path) -> list[tuple[str, dict[str, str], str]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        kind, fields = parse_hbp_line(line)
        rows.append((kind, fields, line))
    return rows


def write_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if normalized and not normalized.endswith("\n"):
        normalized += "\n"
    path.write_bytes(normalized.encode("utf-8"))


def write_sidecar(path: Path) -> Path:
    sidecar = path.with_name(path.name + ".sha256")
    write_lf(sidecar, f"{sha256_file(path)}  {path.name}")
    return sidecar


def verify_sidecar(path: Path) -> None:
    sidecar = path.with_name(path.name + ".sha256")
    if not sidecar.is_file():
        raise RuntimeError(f"missing SHA-256 sidecar: {sidecar}")
    expected = sidecar.read_text(encoding="utf-8").split()[0].lower()
    actual = sha256_file(path)
    if expected != actual:
        raise RuntimeError(f"SHA-256 mismatch: {path}")


def write_bundle(output: Path, stem: str, rows: Iterable[str]) -> tuple[Path, Path, Path]:
    output.mkdir(parents=True, exist_ok=True)
    hbp = output / f"{stem}.hbp"
    hbi = output / f"{stem}.hbi"
    whole_hex = output / f"{stem}.hbp.hex"
    encoded_rows = [(row.rstrip("\r\n") + "\n").encode("utf-8") for row in rows]
    hbp.write_bytes(b"".join(encoded_rows))
    index_rows = [
        hbp_row(
            "HBIHDR",
            schema=SCHEMA,
            target=hbp.name,
            rows=len(encoded_rows),
            target_bytes=hbp.stat().st_size,
            target_sha256=sha256_file(hbp),
            encoding="UTF8_NO_BOM",
            line_endings="LF",
        )
    ]
    offset = 0
    for row_number, encoded in enumerate(encoded_rows, 1):
        index_rows.append(
            hbp_row(
                "HBIROW",
                row=row_number,
                off=offset,
                len=len(encoded),
                row_sha256=sha256_bytes(encoded),
                row_hex=encoded.hex(),
            )
        )
        offset += len(encoded)
    write_lf(hbi, "\n".join(index_rows))
    write_lf(whole_hex, hbp.read_bytes().hex())
    for path in (hbp, hbi, whole_hex):
        write_sidecar(path)
    return hbp, hbi, whole_hex


def verify_bundle(receipts: Path, stem: str) -> int:
    hbp = receipts / f"{stem}.hbp"
    hbi = receipts / f"{stem}.hbi"
    whole_hex = receipts / f"{stem}.hbp.hex"
    for path in (hbp, hbi, whole_hex):
        if not path.is_file():
            raise RuntimeError(f"missing receipt artifact: {path}")
        verify_sidecar(path)
    body = hbp.read_bytes()
    if bytes.fromhex(whole_hex.read_text(encoding="utf-8").strip()) != body:
        raise RuntimeError(f"whole-file hex mismatch: {whole_hex}")
    indexed: list[tuple[int, bytes]] = []
    header_rows = None
    header_target = None
    for line in hbi.read_text(encoding="utf-8").splitlines():
        kind, fields = parse_hbp_line(line)
        if kind == "HBIHDR":
            header_rows = int(fields["rows"])
            header_target = fields["target_sha256"].lower()
            continue
        if kind != "HBIROW":
            continue
        offset = int(fields["off"])
        length = int(fields["len"])
        chunk = body[offset : offset + length]
        if len(chunk) != length:
            raise RuntimeError(f"HBI row length mismatch: {hbi}")
        if sha256_bytes(chunk) != fields["row_sha256"].lower():
            raise RuntimeError(f"HBI row hash mismatch: {hbi}")
        if chunk.hex() != fields["row_hex"].lower():
            raise RuntimeError(f"HBI row hex mismatch: {hbi}")
        indexed.append((offset, chunk))
    indexed.sort(key=lambda item: item[0])
    if header_target != sha256_bytes(body):
        raise RuntimeError(f"HBI target hash mismatch: {hbi}")
    if header_rows != len(indexed):
        raise RuntimeError(f"HBI row count mismatch: {hbi}")
    cursor = 0
    for offset, chunk in indexed:
        if offset != cursor:
            raise RuntimeError(f"HBI byte gap or overlap: {hbi}")
        cursor += len(chunk)
    if cursor != len(body):
        raise RuntimeError(f"HBI does not cover target: {hbi}")
    return len(indexed)


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    domain: str
    authority: str
    url: str
    license: str
    payload_policy: str
    fetch_kind: str
    license_filter: str
    redistribution: str
    community_review: str
    status: str
    branch: str = ""
    commit_sha: str = ""
    tree_sha: str = ""

    @classmethod
    def from_fields(cls, fields: dict[str, str]) -> "SourceSpec":
        required = (
            "source_id",
            "domain",
            "authority",
            "url",
            "license",
            "payload_policy",
            "fetch_kind",
            "license_filter",
            "redistribution",
            "community_review",
            "status",
        )
        missing = [name for name in required if name not in fields]
        if missing:
            raise ValueError(f"source row missing fields {missing}")
        return cls(
            source_id=fields["source_id"],
            domain=fields["domain"],
            authority=fields["authority"],
            url=fields["url"],
            license=fields["license"],
            payload_policy=fields["payload_policy"],
            fetch_kind=fields["fetch_kind"],
            license_filter=fields["license_filter"],
            redistribution=fields["redistribution"],
            community_review=fields["community_review"],
            status=fields["status"],
            branch=fields.get("branch", ""),
            commit_sha=fields.get("commit_sha", ""),
            tree_sha=fields.get("tree_sha", ""),
        )


@dataclass(frozen=True)
class Fragment:
    source_id: str
    domain: str
    relative_path: str
    source_file_sha256: str
    normalized_sha256: str
    normalized: bytes
    source_complete: bool
    selection: str


@dataclass(frozen=True)
class Segment:
    source_id: str
    relative_path: str
    normalized_offset: int
    data: bytes


def load_source_catalog(path: Path) -> tuple[list[SourceSpec], dict[str, SourceSpec]]:
    rows = read_hbp_rows(path)
    header = next((fields for kind, fields, _ in rows if kind == "SOURCECATALOG"), None)
    if header is None:
        raise ValueError("SOURCECATALOG header missing")
    sources = [
        SourceSpec.from_fields(fields)
        for kind, fields, _ in rows
        if kind == "SOURCE"
    ]
    if int(header["source_rows"]) != len(sources):
        raise ValueError(
            f"catalog source_rows={header['source_rows']} but found {len(sources)}"
        )
    by_id: dict[str, SourceSpec] = {}
    for source in sources:
        if source.source_id in by_id:
            raise ValueError(f"duplicate source_id: {source.source_id}")
        if source.payload_policy not in PAYLOAD_ALLOW_POLICIES | METADATA_ONLY_POLICIES:
            raise ValueError(
                f"unknown payload policy {source.payload_policy}: {source.source_id}"
            )
        if source.domain not in set(DOMAIN_SLICE_TARGETS) | {"SYSTEM_BINDING"}:
            raise ValueError(f"unknown source domain: {source.domain}")
        if source.license_filter == "COMMIT_AND_TREE_PIN_REQUIRED":
            if len(source.commit_sha) != 40 or len(source.tree_sha) != 40:
                raise ValueError(f"unpinned system source: {source.source_id}")
            int(source.commit_sha, 16)
            int(source.tree_sha, 16)
        by_id[source.source_id] = source
    return sources, by_id


def load_body_map(
    path: Path, source_by_id: dict[str, SourceSpec]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rows = read_hbp_rows(path)
    bodies = [fields for kind, fields, _ in rows if kind == "BODY"]
    bindings = [fields for kind, fields, _ in rows if kind == "SYSTEMBINDING"]
    expected = {"HERITAGE_8": 8, "ARCHITECTURE_12": 12, "ASTRONOMY_PI_20": 20}
    actual = {
        family: sum(body.get("family") == family for body in bodies)
        for family in expected
    }
    if actual != expected or len(bodies) != 40:
        raise ValueError(f"body family count mismatch: {actual}")
    required_body_fields = {
        "body_id",
        "family",
        "ordinal",
        "name",
        "sources",
        "language_slot",
        "passes",
    }
    for body in bodies:
        missing = required_body_fields.difference(body)
        if missing:
            raise ValueError(
                f"body {body.get('body_id', '<unknown>')} missing fields: "
                f"{sorted(missing)}"
            )
    body_ids = [body["body_id"] for body in bodies]
    if len(set(body_ids)) != len(body_ids):
        raise ValueError("duplicate body_id")
    language_slots = [body["language_slot"] for body in bodies]
    if len(set(language_slots)) != len(language_slots):
        raise ValueError("duplicate body language_slot")
    family_prefixes = {
        "HERITAGE_8": "H",
        "ARCHITECTURE_12": "A",
        "ASTRONOMY_PI_20": "P",
    }
    for family, count in expected.items():
        family_bodies = [body for body in bodies if body["family"] == family]
        ordinals = sorted(int(body["ordinal"]) for body in family_bodies)
        if ordinals != list(range(1, count + 1)):
            raise ValueError(
                f"body ordinal mismatch for {family}: {ordinals}"
            )
        prefix = family_prefixes[family]
        expected_ids = {f"{prefix}{ordinal:02d}" for ordinal in range(1, count + 1)}
        actual_ids = {body["body_id"] for body in family_bodies}
        if actual_ids != expected_ids:
            raise ValueError(
                f"body ID mismatch for {family}: {sorted(actual_ids)}"
            )
    for body in bodies:
        expected_domain = BODY_FAMILY_DOMAINS[body["family"]]
        source_ids = [
            source_id.strip()
            for source_id in body["sources"].split(",")
            if source_id.strip()
        ]
        if not source_ids:
            raise ValueError(f"body has no sources: {body['body_id']}")
        for source_id in source_ids:
            if source_id in DERIVED_BODY_SOURCES:
                source_domain = DERIVED_BODY_SOURCES[source_id]
            elif source_id in source_by_id:
                source_domain = source_by_id[source_id].domain
            else:
                raise ValueError(
                    f"body source missing from catalog: "
                    f"{body['body_id']} -> {source_id}"
                )
            if source_domain != expected_domain:
                raise ValueError(
                    f"body source domain mismatch: {body['body_id']} -> "
                    f"{source_id} ({source_domain} != {expected_domain})"
                )
    if len(bindings) != 7:
        raise ValueError(f"expected 7 system bindings, found {len(bindings)}")
    for binding in bindings:
        source_id = binding["source_id"]
        if source_id not in source_by_id:
            raise ValueError(f"binding source missing from catalog: {source_id}")
        source = source_by_id[source_id]
        if source.domain != "SYSTEM_BINDING":
            raise ValueError(f"binding source has wrong domain: {source_id}")
        if binding["commit_sha"] != source.commit_sha:
            raise ValueError(f"binding commit mismatch: {source_id}")
        if binding["tree_sha"] != source.tree_sha:
            raise ValueError(f"binding tree mismatch: {source_id}")
    return bodies, bindings


def is_text_path(name: str) -> bool:
    return Path(name).suffix.lower() in TEXT_EXTENSIONS


def normalize_text(data: bytes) -> bytes:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    return text.encode("utf-8")


def source_authority_receipt_allows(source: SourceSpec, directory: Path) -> bool:
    if source.license_filter in {
        "NONE",
        "TEI_CC_HEADER",
        "FILE_CC_BY_SA",
        "COMMIT_AND_TREE_PIN_REQUIRED",
    }:
        return True
    receipt = directory / "SOURCE-AUTHORITY.hbp"
    if not receipt.is_file():
        return False
    for kind, fields, _ in read_hbp_rows(receipt):
        if (
            kind == "SOURCEAUTHORITY"
            and fields.get("source_id") == source.source_id
            and fields.get("payload_allowed") == "1"
        ):
            if source.payload_policy == "ALLOW_COLD_METADATA":
                return fields.get("payload_class") == "METADATA"
            return True
    return False


def per_file_filter_allows(source: SourceSpec, data: bytes) -> bool:
    if source.license_filter not in {"TEI_CC_HEADER", "FILE_CC_BY_SA"}:
        return True
    sample = data[:256 * 1024].decode("utf-8", errors="ignore").lower()
    markers = (
        "creativecommons.org/licenses/by",
        "cc by-sa",
        "cc-by-sa",
        "creative commons attribution-sharealike",
    )
    return any(marker in sample for marker in markers)


def bounded_file_bytes(path: Path) -> tuple[bytes, str, bool, str]:
    size = path.stat().st_size
    full_sha = sha256_file(path)
    if size <= MAX_FILE_SAMPLE_BYTES:
        return path.read_bytes(), full_sha, True, "FULL_FILE"
    window = MAX_FILE_SAMPLE_BYTES // 4
    max_start = size - window
    offsets = (0, max_start // 3, (2 * max_start) // 3, max_start)
    parts = []
    with path.open("rb") as stream:
        for offset in offsets:
            stream.seek(offset)
            parts.append(stream.read(window))
    return b"".join(parts), full_sha, False, "FOUR_EVEN_WINDOWS"


def iter_zip_members(path: Path) -> Iterator[tuple[str, bytes, str, bool, str]]:
    with zipfile.ZipFile(path) as archive:
        for info in sorted(archive.infolist(), key=lambda item: item.filename):
            if info.is_dir() or not is_text_path(info.filename):
                continue
            if info.file_size > MAX_ARCHIVE_MEMBER_BYTES:
                continue
            data = archive.read(info)
            yield info.filename, data, sha256_bytes(data), True, "FULL_ZIP_MEMBER"


def iter_tar_members(path: Path) -> Iterator[tuple[str, bytes, str, bool, str]]:
    with tarfile.open(path, "r:*") as archive:
        members = sorted(archive.getmembers(), key=lambda item: item.name)
        for member in members:
            if not member.isfile() or not is_text_path(member.name):
                continue
            if member.size > MAX_ARCHIVE_MEMBER_BYTES:
                continue
            stream = archive.extractfile(member)
            if stream is None:
                continue
            data = stream.read(MAX_ARCHIVE_MEMBER_BYTES + 1)
            if len(data) > MAX_ARCHIVE_MEMBER_BYTES:
                continue
            yield member.name, data, sha256_bytes(data), True, "FULL_TAR_MEMBER"


def iter_source_payloads(
    source: SourceSpec, directory: Path
) -> Iterator[tuple[str, bytes, str, bool, str]]:
    for path in sorted(directory.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() or path.is_symlink():
            continue
        if (
            path.name.startswith("SOURCE-AUTHORITY.")
            or path.name.startswith("RIGHTS.")
        ):
            continue
        relative = path.relative_to(directory).as_posix()
        lowered = path.name.lower()
        try:
            if lowered.endswith(".zip"):
                for member, data, digest, complete, selection in iter_zip_members(
                    path
                ):
                    yield (
                        f"{relative}!/{member}",
                        data,
                        digest,
                        complete,
                        selection,
                    )
            elif lowered.endswith((".tar", ".tar.gz", ".tgz")):
                for member, data, digest, complete, selection in iter_tar_members(
                    path
                ):
                    yield (
                        f"{relative}!/{member}",
                        data,
                        digest,
                        complete,
                        selection,
                    )
            elif is_text_path(relative):
                data, digest, complete, selection = bounded_file_bytes(path)
                yield relative, data, digest, complete, selection
        except (OSError, tarfile.TarError, zipfile.BadZipFile):
            continue


def collect_fragments(
    sources: Sequence[SourceSpec], raw_root: Path
) -> tuple[list[Fragment], dict[str, dict[str, Any]]]:
    fragments: list[Fragment] = []
    usage: dict[str, dict[str, Any]] = {}
    for source in sources:
        directory = raw_root / source.source_id
        staged = directory.is_dir()
        usage[source.source_id] = {
            "staged": int(staged),
            "payload_allowed": int(source.payload_policy in PAYLOAD_ALLOW_POLICIES),
            "fragment_count": 0,
            "normalized_available_bytes": 0,
            "used_bytes": 0,
            "reason": "NOT_STAGED",
        }
        if source.payload_policy not in PAYLOAD_ALLOW_POLICIES:
            usage[source.source_id]["reason"] = "METADATA_ONLY_POLICY"
            continue
        if source.domain == "SYSTEM_BINDING":
            usage[source.source_id]["reason"] = "SYSTEM_BINDING_POINTER_NOT_DOMAIN_PAYLOAD"
            continue
        if not staged:
            continue
        if not source_authority_receipt_allows(source, directory):
            usage[source.source_id]["reason"] = "SOURCE_AUTHORITY_RECEIPT_REQUIRED"
            continue
        total = 0
        for relative, raw, source_sha, complete, selection in iter_source_payloads(
            source, directory
        ):
            if not per_file_filter_allows(source, raw):
                continue
            normalized = normalize_text(raw)
            if not normalized:
                continue
            remaining = MAX_NORMALIZED_PER_SOURCE - total
            if remaining <= 0:
                break
            if len(normalized) > remaining:
                normalized = normalized[:remaining]
                complete = False
                selection += "_SOURCE_CAP"
            fragment = Fragment(
                source_id=source.source_id,
                domain=source.domain,
                relative_path=relative,
                source_file_sha256=source_sha,
                normalized_sha256=sha256_bytes(normalized),
                normalized=normalized,
                source_complete=complete,
                selection=selection,
            )
            fragments.append(fragment)
            total += len(normalized)
        usage[source.source_id]["fragment_count"] = sum(
            fragment.source_id == source.source_id for fragment in fragments
        )
        usage[source.source_id]["normalized_available_bytes"] = total
        usage[source.source_id]["reason"] = (
            "ELIGIBLE_FRAGMENTS_READY" if total else "NO_ELIGIBLE_TEXT_PAYLOAD"
        )
    return fragments, usage


def fragment_blocks(fragments: Sequence[Fragment]) -> dict[str, deque[Segment]]:
    by_source: dict[str, deque[Segment]] = {}
    grouped: dict[str, list[Segment]] = defaultdict(list)
    for fragment in sorted(
        fragments, key=lambda item: (item.source_id, item.relative_path)
    ):
        for offset in range(0, len(fragment.normalized), BLOCK_BYTES):
            grouped[fragment.source_id].append(
                Segment(
                    source_id=fragment.source_id,
                    relative_path=fragment.relative_path,
                    normalized_offset=offset,
                    data=fragment.normalized[offset : offset + BLOCK_BYTES],
                )
            )
    for source_id, segments in grouped.items():
        by_source[source_id] = deque(segments)
    return by_source


def select_domain_segments(
    fragments: Sequence[Fragment], domain: str, required_bytes: int
) -> list[Segment]:
    domain_fragments = [item for item in fragments if item.domain == domain]
    available = sum(len(item.normalized) for item in domain_fragments)
    if available < required_bytes:
        raise RuntimeError(
            f"{domain} has {available} eligible normalized bytes; "
            f"{required_bytes} required. Source bytes are never padded or repeated."
        )
    queues = fragment_blocks(domain_fragments)
    order = sorted(
        queues,
        key=lambda source_id: sha256_bytes(
            MIX_SEED + b"|" + domain.encode("ascii") + b"|" + source_id.encode("utf-8")
        ),
    )
    selected: list[Segment] = []
    remaining = required_bytes
    while remaining:
        progressed = False
        for source_id in order:
            queue = queues[source_id]
            if not queue:
                continue
            progressed = True
            segment = queue.popleft()
            take = min(remaining, len(segment.data))
            selected.append(
                Segment(
                    source_id=segment.source_id,
                    relative_path=segment.relative_path,
                    normalized_offset=segment.normalized_offset,
                    data=segment.data[:take],
                )
            )
            remaining -= take
            if remaining == 0:
                break
        if not progressed:
            raise RuntimeError(f"{domain} selection exhausted unexpectedly")
    return selected


def contributions_for_range(
    segments: Sequence[Segment], start: int, end: int
) -> tuple[str, str]:
    cursor = 0
    by_source: dict[str, int] = defaultdict(int)
    records = []
    for segment in segments:
        seg_start = cursor
        seg_end = cursor + len(segment.data)
        cursor = seg_end
        overlap_start = max(start, seg_start)
        overlap_end = min(end, seg_end)
        if overlap_start >= overlap_end:
            continue
        length = overlap_end - overlap_start
        local_offset = segment.normalized_offset + overlap_start - seg_start
        by_source[segment.source_id] += length
        records.append(
            f"{segment.source_id}|{segment.relative_path}|{local_offset}|{length}"
        )
        if seg_start >= end:
            break
    summary = ",".join(f"{key}:{by_source[key]}" for key in sorted(by_source))
    return summary, sha256_bytes("\n".join(records).encode("utf-8"))


def build_slices(
    fragments: Sequence[Fragment],
    slices_dir: Path,
    usage: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], str, str]:
    slices_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    ordered_hashes: list[str] = []
    stream_digest = hashlib.sha256()
    global_slice = 0
    for domain, target_slices in DOMAIN_SLICE_TARGETS.items():
        required = target_slices * SLICE_BYTES
        segments = select_domain_segments(fragments, domain, required)
        blob = b"".join(segment.data for segment in segments)
        if len(blob) != required:
            raise AssertionError(f"domain byte count invariant failed: {domain}")
        for segment in segments:
            usage[segment.source_id]["used_bytes"] += len(segment.data)
        for domain_slice in range(target_slices):
            global_slice += 1
            start = domain_slice * SLICE_BYTES
            end = start + SLICE_BYTES
            data = blob[start:end]
            digest = sha256_bytes(data)
            filename = (
                f"slice-{global_slice:04d}-"
                f"{domain.lower().replace('_', '-')}.bin"
            )
            path = slices_dir / filename
            path.write_bytes(data)
            write_sidecar(path)
            contributors, contribution_sha = contributions_for_range(
                segments, start, end
            )
            records.append(
                {
                    "slice": global_slice,
                    "domain": domain,
                    "domain_slice": domain_slice + 1,
                    "path": f"slices/{filename}",
                    "bytes": len(data),
                    "sha256": digest,
                    "contributors": contributors,
                    "contribution_sha256": contribution_sha,
                }
            )
            ordered_hashes.append(digest)
            stream_digest.update(data)
    if global_slice != SLICE_COUNT:
        raise AssertionError(f"expected {SLICE_COUNT} slices, got {global_slice}")
    root = sha256_bytes(b"".join(bytes.fromhex(value) for value in ordered_hashes))
    return records, root, stream_digest.hexdigest()


def xor_sha256_ctr(data: bytes, seed: bytes) -> bytes:
    output = bytearray(len(data))
    cursor = 0
    counter = 0
    while cursor < len(data):
        mask = hashlib.sha256(seed + counter.to_bytes(8, "big")).digest()
        take = min(len(mask), len(data) - cursor)
        for index in range(take):
            output[cursor + index] = data[cursor + index] ^ mask[index]
        cursor += take
        counter += 1
    return bytes(output)


def binding_root(bindings: Sequence[dict[str, str]]) -> str:
    material = "\n".join(
        "|".join(
            (
                binding["binding_id"],
                binding["source_id"],
                binding["commit_sha"],
                binding["tree_sha"],
            )
        )
        for binding in sorted(bindings, key=lambda item: item["binding_id"])
    )
    return sha256_bytes((material + "\n").encode("utf-8"))


def body_language_rows(
    bodies: Sequence[dict[str, str]],
    corpus_root: str,
    probe: bytes,
    system_binding_root: str,
) -> list[str]:
    rows = [
        hbp_row(
            "BODYLANGUAGES",
            schema=SCHEMA,
            bodies=len(bodies),
            codec="XOR_SHA256_CTR",
            historical_language_is_not_cube_codec=1,
            system_binding_root=system_binding_root,
            roundtrip_required=1,
        )
    ]
    language_ids = set()
    for body in sorted(bodies, key=lambda item: item["body_id"]):
        seed = hashlib.sha256(
            bytes.fromhex(corpus_root)
            + b"|"
            + body["family"].encode("ascii")
            + b"|"
            + body["body_id"].encode("ascii")
        ).digest()
        language_id = f"LANG-{body['body_id']}-{seed.hex()[:16]}"
        if language_id in language_ids:
            raise RuntimeError(f"duplicate local language ID: {language_id}")
        language_ids.add(language_id)
        encoded = xor_sha256_ctr(probe, seed)
        restored = xor_sha256_ctr(encoded, seed)
        if restored != probe:
            raise RuntimeError(f"local language roundtrip failed: {body['body_id']}")
        rows.append(
            hbp_row(
                "BODYLANGUAGE",
                schema=SCHEMA,
                family=body["family"],
                body_id=body["body_id"],
                body_name=body["name"],
                passes=body["passes"],
                local_language_id=language_id,
                language_seed_sha256=seed.hex(),
                codec="XOR_SHA256_CTR",
                probe_bytes=len(probe),
                probe_sha256=sha256_bytes(probe),
                encoded_probe_sha256=sha256_bytes(encoded),
                roundtrip=1,
                historical_translation_claim=body.get(
                    "historical_translation_claim", "NOT_APPLICABLE"
                ),
            )
        )
    if len(language_ids) != 40:
        raise RuntimeError("expected 40 distinct local languages")
    return rows


def write_checksum_manifest(output: Path) -> Path:
    manifest = output / "SHA256SUMS"
    sidecar = output / "SHA256SUMS.sha256"
    rows = []
    for path in sorted(output.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() or path in {manifest, sidecar}:
            continue
        rows.append(f"{sha256_file(path)}  {path.relative_to(output).as_posix()}")
    write_lf(manifest, "\n".join(rows))
    write_sidecar(manifest)
    return manifest


def verify_checksum_manifest(output: Path) -> int:
    manifest = output / "SHA256SUMS"
    verify_sidecar(manifest)
    count = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split(None, 1)
        target = output / relative.strip()
        if not target.is_file() or sha256_file(target) != expected.lower():
            raise RuntimeError(f"SHA256SUMS mismatch: {target}")
        count += 1
    return count


def ensure_new_output(output: Path) -> None:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(
            f"output exists and is not empty: {output}; use a new output path"
        )
    output.mkdir(parents=True, exist_ok=True)


def build_corpus(
    contract_path: Path,
    catalog_path: Path,
    body_map_path: Path,
    raw_root: Path,
    output: Path,
) -> dict[str, Any]:
    ensure_new_output(output)
    receipts = output / "receipts"
    slices_dir = output / "slices"
    sources, source_by_id = load_source_catalog(catalog_path)
    bodies, bindings = load_body_map(body_map_path, source_by_id)
    fragments, usage = collect_fragments(sources, raw_root)
    slice_records, corpus_root, stream_sha = build_slices(
        fragments, slices_dir, usage
    )
    probe = (slices_dir / Path(slice_records[0]["path"]).name).read_bytes()
    system_root = binding_root(bindings)

    write_bundle(
        receipts,
        "CONTRACT-SNAPSHOT",
        [raw for _, _, raw in read_hbp_rows(contract_path)],
    )
    write_bundle(
        receipts,
        "SOURCE-CATALOG-SNAPSHOT",
        [raw for _, _, raw in read_hbp_rows(catalog_path)],
    )
    write_bundle(
        receipts,
        "BODY-MAP-SNAPSHOT",
        [raw for _, _, raw in read_hbp_rows(body_map_path)],
    )

    source_rows = [
        hbp_row(
            "SOURCEUSEHDR",
            schema=SCHEMA,
            sources=len(sources),
            fragments=len(fragments),
            source_payload_bytes=sum(len(item.normalized) for item in fragments),
            selected_bytes=SLICE_COUNT * SLICE_BYTES,
            system_binding_payload_in_domain_slices=0,
        )
    ]
    for source in sources:
        state = usage[source.source_id]
        source_rows.append(
            hbp_row(
                "SOURCEUSE",
                schema=SCHEMA,
                source_id=source.source_id,
                domain=source.domain,
                payload_policy=source.payload_policy,
                license=source.license,
                redistribution=source.redistribution,
                staged=state["staged"],
                fragment_count=state["fragment_count"],
                normalized_available_bytes=state["normalized_available_bytes"],
                used_bytes=state["used_bytes"],
                contributes_domain_slices=int(state["used_bytes"] > 0),
                reason=state["reason"],
            )
        )
    for fragment in fragments:
        source_rows.append(
            hbp_row(
                "SOURCEFRAGMENT",
                schema=SCHEMA,
                source_id=fragment.source_id,
                domain=fragment.domain,
                path=fragment.relative_path,
                source_file_sha256=fragment.source_file_sha256,
                normalized_sha256=fragment.normalized_sha256,
                normalized_bytes=len(fragment.normalized),
                source_complete=int(fragment.source_complete),
                selection=fragment.selection,
            )
        )
    write_bundle(receipts, "SOURCE-USE", source_rows)

    binding_rows = [
        hbp_row(
            "SYSTEMBINDINGHDR",
            schema=SCHEMA,
            bindings=len(bindings),
            binding_root_sha256=system_root,
            payload_replaces_domain_authority=0,
            applies_to="ALL_40_BODIES",
        )
    ]
    for binding in sorted(bindings, key=lambda item: item["binding_id"]):
        binding_rows.append(
            hbp_row(
                "SYSTEMBINDING",
                schema=SCHEMA,
                **{key: value for key, value in binding.items() if key != "json"},
            )
        )
    write_bundle(receipts, "SYSTEM-BINDINGS", binding_rows)

    slice_rows = [
        hbp_row(
            "SLICEMAPHDR",
            schema=SCHEMA,
            slices=SLICE_COUNT,
            slice_bytes=SLICE_BYTES,
            total_bytes=SLICE_COUNT * SLICE_BYTES,
            heritage_slices=DOMAIN_SLICE_TARGETS["HERITAGE_SCRIPT"],
            architecture_slices=DOMAIN_SLICE_TARGETS["ARCHITECTURE"],
            astronomy_slices=DOMAIN_SLICE_TARGETS["ASTRONOMY_PI"],
            corpus_root_sha256=corpus_root,
            source_stream_sha256=stream_sha,
        )
    ]
    slice_rows.extend(
        hbp_row("SLICE", schema=SCHEMA, **record) for record in slice_records
    )
    write_bundle(receipts, "SLICE-MAP", slice_rows)

    write_bundle(
        receipts,
        "BODY-LANGUAGES",
        body_language_rows(bodies, corpus_root, probe, system_root),
    )

    exposure_rows = [
        hbp_row(
            "INFORMATIONEXPOSUREHDR",
            schema=SCHEMA,
            exposures=SLICE_COUNT,
            semantics="SOURCE_NORMALIZATION_AND_BOUNDED_SELECTION",
            learned_relation=0,
            training=0,
        )
    ]
    exposure_rows.extend(
        hbp_row(
            "INFORMATIONEXPOSURE",
            schema=SCHEMA,
            exposure=record["slice"],
            slice=record["slice"],
            domain=record["domain"],
            bytes=record["bytes"],
            slice_sha256=record["sha256"],
            learned_relation=0,
            external_model_call=0,
        )
        for record in slice_records
    )
    write_bundle(receipts, "01-INFORMATION-EXPOSURES", exposure_rows)
    write_bundle(
        receipts,
        "02-MODEL-LOCAL-RELATIONS",
        [
            hbp_row(
                "MODELLOCALRELATIONHDR",
                schema=SCHEMA,
                relations=0,
                status="HELD_UNTIL_TRAINER",
                source_builder_cannot_claim_learning=1,
            )
        ],
    )
    write_bundle(
        receipts,
        "03-RECURRENT-STATE-TRANSITIONS",
        [
            hbp_row(
                "RECURRENTTRANSITIONHDR",
                schema=SCHEMA,
                transitions=0,
                status="HELD_UNTIL_TRAINER",
            )
        ],
    )
    write_bundle(
        receipts,
        "04-UPWARD-LINEAGE-LINKS",
        [
            hbp_row(
                "UPWARDLINEAGEHDR",
                schema=SCHEMA,
                links=0,
                status="HELD_UNTIL_FAMILY_ROOTS_EXIST",
                local_centers_preserved=1,
                directed_ancestry_preserved=1,
            )
        ],
    )
    write_bundle(
        receipts,
        "05-EXTERNAL-MODEL-CALLS",
        [
            hbp_row(
                "EXTERNALCALLHDR",
                schema=SCHEMA,
                provider_calls=0,
                external_model_calls=0,
                external_gnn_calls=0,
                gpu_calls=0,
                paid_spend_usd=0,
                live_gitram_ingestion=0,
                live_gnn_training=0,
                live_omega_absorption=0,
                promotion=0,
                minting=0,
            )
        ],
    )
    rights_rows = [
        hbp_row(
            "RIGHTSCOMMUNITYHDR",
            schema=SCHEMA,
            sources=len(sources),
            ledger=6,
            separate_from_learning_ledgers=1,
        )
    ]
    rights_rows.extend(
        hbp_row(
            "RIGHTSCOMMUNITY",
            schema=SCHEMA,
            source_id=source.source_id,
            domain=source.domain,
            authority=source.authority,
            license=source.license,
            payload_policy=source.payload_policy,
            redistribution=source.redistribution,
            community_review=source.community_review,
            payload_used_bytes=usage[source.source_id]["used_bytes"],
            held_payload=int(source.payload_policy in METADATA_ONLY_POLICIES),
        )
        for source in sources
    )
    write_bundle(receipts, "06-RIGHTS-COMMUNITY", rights_rows)

    fragment_root = sha256_bytes(
        b"".join(
            bytes.fromhex(fragment.normalized_sha256)
            for fragment in sorted(
                fragments, key=lambda item: (item.source_id, item.relative_path)
            )
        )
    )
    root_rows = [
        hbp_row(
            "COLDCORPUSROOT",
            schema=SCHEMA,
            slice_count=SLICE_COUNT,
            slice_bytes=SLICE_BYTES,
            total_bytes=SLICE_COUNT * SLICE_BYTES,
            corpus_root_sha256=corpus_root,
            source_stream_sha256=stream_sha,
            eligible_fragment_root_sha256=fragment_root,
            system_binding_root_sha256=system_root,
            bodies=40,
            local_languages=40,
            language_roundtrips=40,
            learned_model_local_relations=0,
            recurrent_transitions=0,
            upward_lineage_links=0,
            external_model_calls=0,
            live_absorption=0,
            claims_final_apex=0,
        ),
        hbp_row(
            "CLAIMBOUNDARY",
            schema=SCHEMA,
            measured="BOUNDED_SOURCE_SLICES_SHA256_AND_REVERSIBLE_LANGUAGE_PROBES",
            operator_observed="PR038_NET_LIKE_REGION_EXISTS_AND_EVOLVES",
            unverified="QUANTUM_KEY_INVERTED_UNIVERSE_PHYSICAL_PROJECTION",
            identity_claim="NONE",
        ),
    ]
    write_bundle(receipts, "COLD-CORPUS-ROOT", root_rows)
    write_checksum_manifest(output)
    verified = verify_output(output)
    return {
        "corpus_root_sha256": corpus_root,
        "source_stream_sha256": stream_sha,
        "system_binding_root_sha256": system_root,
        "slices": SLICE_COUNT,
        "slice_bytes": SLICE_BYTES,
        "manifest_entries": verified["manifest_entries"],
    }


def verify_output(output: Path) -> dict[str, int]:
    receipts = output / "receipts"
    slices = sorted((output / "slices").glob("slice-*.bin"))
    if len(slices) != SLICE_COUNT:
        raise RuntimeError(f"expected {SLICE_COUNT} slices, found {len(slices)}")
    for path in slices:
        if path.stat().st_size != SLICE_BYTES:
            raise RuntimeError(f"slice size mismatch: {path}")
        verify_sidecar(path)
    rows = 0
    for stem in RECEIPT_STEMS:
        rows += verify_bundle(receipts, stem)

    slice_map_rows = read_hbp_rows(receipts / "SLICE-MAP.hbp")
    slice_headers = [
        fields for kind, fields, _ in slice_map_rows if kind == "SLICEMAPHDR"
    ]
    slice_records = [
        fields for kind, fields, _ in slice_map_rows if kind == "SLICE"
    ]
    if len(slice_headers) != 1 or len(slice_records) != SLICE_COUNT:
        raise RuntimeError("SLICE-MAP semantic row count mismatch")
    slice_header = slice_headers[0]
    ordered_records = sorted(
        slice_records, key=lambda fields: int(fields["slice"])
    )
    if [int(fields["slice"]) for fields in ordered_records] != list(
        range(1, SLICE_COUNT + 1)
    ):
        raise RuntimeError("SLICE-MAP slice ordinals are not exact")
    ordered_hashes: list[str] = []
    stream_digest = hashlib.sha256()
    domain_counts: dict[str, int] = defaultdict(int)
    for record, path in zip(ordered_records, slices):
        expected_path = Path(record["path"]).name
        if path.name != expected_path:
            raise RuntimeError(
                f"SLICE-MAP path mismatch: {path.name} != {expected_path}"
            )
        data = path.read_bytes()
        digest = sha256_bytes(data)
        if int(record["bytes"]) != len(data) or record["sha256"] != digest:
            raise RuntimeError(f"SLICE-MAP content mismatch: {path}")
        domain = record["domain"]
        if domain not in DOMAIN_SLICE_TARGETS:
            raise RuntimeError(f"SLICE-MAP unknown domain: {domain}")
        domain_counts[domain] += 1
        ordered_hashes.append(digest)
        stream_digest.update(data)
    if domain_counts != DOMAIN_SLICE_TARGETS:
        raise RuntimeError(
            f"SLICE-MAP domain count mismatch: {dict(domain_counts)}"
        )
    corpus_root = sha256_bytes(
        b"".join(bytes.fromhex(value) for value in ordered_hashes)
    )
    if (
        slice_header["corpus_root_sha256"] != corpus_root
        or slice_header["source_stream_sha256"] != stream_digest.hexdigest()
    ):
        raise RuntimeError("SLICE-MAP root semantic mismatch")

    source_snapshot = receipts / "SOURCE-CATALOG-SNAPSHOT.hbp"
    body_snapshot = receipts / "BODY-MAP-SNAPSHOT.hbp"
    _, source_by_id = load_source_catalog(source_snapshot)
    bodies, bindings = load_body_map(body_snapshot, source_by_id)
    expected_language_rows = body_language_rows(
        bodies,
        corpus_root,
        slices[0].read_bytes(),
        binding_root(bindings),
    )
    actual_language_rows = [
        raw for _, _, raw in read_hbp_rows(receipts / "BODY-LANGUAGES.hbp")
    ]
    if actual_language_rows != expected_language_rows:
        raise RuntimeError("BODY-LANGUAGES semantic mismatch")

    exposure_rows = read_hbp_rows(receipts / "01-INFORMATION-EXPOSURES.hbp")
    exposure_headers = [
        fields
        for kind, fields, _ in exposure_rows
        if kind == "INFORMATIONEXPOSUREHDR"
    ]
    exposures = [
        fields
        for kind, fields, _ in exposure_rows
        if kind == "INFORMATIONEXPOSURE"
    ]
    if (
        len(exposure_headers) != 1
        or int(exposure_headers[0]["exposures"]) != SLICE_COUNT
        or len(exposures) != SLICE_COUNT
    ):
        raise RuntimeError("information-exposure semantic count mismatch")
    for exposure, record in zip(
        sorted(exposures, key=lambda fields: int(fields["slice"])),
        ordered_records,
    ):
        if (
            exposure["slice"] != record["slice"]
            or exposure["slice_sha256"] != record["sha256"]
            or exposure["domain"] != record["domain"]
            or exposure["learned_relation"] != "0"
            or exposure["external_model_call"] != "0"
        ):
            raise RuntimeError("information-exposure semantic mismatch")

    zero_ledgers = {
        "02-MODEL-LOCAL-RELATIONS.hbp": ("MODELLOCALRELATIONHDR", "relations"),
        "03-RECURRENT-STATE-TRANSITIONS.hbp": (
            "RECURRENTTRANSITIONHDR",
            "transitions",
        ),
        "04-UPWARD-LINEAGE-LINKS.hbp": ("UPWARDLINEAGEHDR", "links"),
        "05-EXTERNAL-MODEL-CALLS.hbp": (
            "EXTERNALCALLHDR",
            "external_model_calls",
        ),
    }
    for filename, (expected_kind, count_field) in zero_ledgers.items():
        ledger_rows = read_hbp_rows(receipts / filename)
        if len(ledger_rows) != 1:
            raise RuntimeError(f"zero-ledger row count mismatch: {filename}")
        kind, fields, _ = ledger_rows[0]
        if kind != expected_kind or fields.get(count_field) != "0":
            raise RuntimeError(f"zero-ledger semantic mismatch: {filename}")

    root_rows = read_hbp_rows(receipts / "COLD-CORPUS-ROOT.hbp")
    roots = [
        fields for kind, fields, _ in root_rows if kind == "COLDCORPUSROOT"
    ]
    if len(roots) != 1:
        raise RuntimeError("COLD-CORPUS-ROOT semantic header mismatch")
    root = roots[0]
    if (
        root["corpus_root_sha256"] != corpus_root
        or root["source_stream_sha256"] != stream_digest.hexdigest()
        or root["system_binding_root_sha256"] != binding_root(bindings)
        or root["bodies"] != "40"
        or root["local_languages"] != "40"
        or root["external_model_calls"] != "0"
        or root["live_absorption"] != "0"
        or root["claims_final_apex"] != "0"
    ):
        raise RuntimeError("COLD-CORPUS-ROOT semantic mismatch")

    manifest_entries = verify_checksum_manifest(output)
    return {
        "slices": len(slices),
        "receipt_rows": rows,
        "manifest_entries": manifest_entries,
    }


def download_source(
    source: SourceSpec, raw_root: Path, max_download_bytes: int
) -> dict[str, Any]:
    if source.payload_policy not in PAYLOAD_ALLOW_POLICIES:
        raise PermissionError(f"source policy forbids payload fetch: {source.source_id}")
    if source.fetch_kind == "URL_FILE":
        download_url = source.url
    elif source.fetch_kind == "GITHUB_ARCHIVE":
        if len(source.commit_sha) != 40:
            raise ValueError(f"GitHub source is not commit-pinned: {source.source_id}")
        download_url = f"{source.url}/archive/{source.commit_sha}.zip"
    else:
        raise ValueError(
            f"{source.source_id} requires manual/API-specific acquisition "
            f"({source.fetch_kind})"
        )
    destination = raw_root / source.source_id
    destination.mkdir(parents=True, exist_ok=True)
    name = Path(urllib.parse.urlparse(download_url).path).name or "payload.bin"
    output = destination / name
    if output.exists():
        raise FileExistsError(f"refusing to overwrite staged source: {output}")
    request = urllib.request.Request(
        download_url,
        headers={"User-Agent": "AsolariaColdSourceBuilder/1.0"},
    )
    digest = hashlib.sha256()
    written = 0
    try:
        with urllib.request.urlopen(request, timeout=60) as response, output.open(
            "wb"
        ) as stream:
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_download_bytes:
                raise RuntimeError(
                    f"source exceeds download cap: {content_length} > "
                    f"{max_download_bytes}"
                )
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_download_bytes:
                    raise RuntimeError("source exceeded download cap while streaming")
                stream.write(chunk)
                digest.update(chunk)
    except Exception:
        if output.exists():
            output.unlink()
        raise
    write_sidecar(output)
    return {
        "source_id": source.source_id,
        "url": download_url,
        "path": output.as_posix(),
        "bytes": written,
        "sha256": digest.hexdigest(),
        "commit_sha": source.commit_sha,
        "tree_sha": source.tree_sha,
    }


def fetch_phase(
    catalog_path: Path,
    raw_root: Path,
    source_ids: Sequence[str],
    max_download_bytes: int,
) -> list[dict[str, Any]]:
    if not source_ids:
        raise ValueError("--phase fetch requires at least one --source-id")
    _, source_by_id = load_source_catalog(catalog_path)
    records = []
    for source_id in source_ids:
        if source_id not in source_by_id:
            raise KeyError(f"unknown source_id: {source_id}")
        records.append(
            download_source(source_by_id[source_id], raw_root, max_download_bytes)
        )
    receipt_dir = PROJECT / "artifacts" / "fetch-receipts"
    rows = [
        hbp_row(
            "FETCHHDR",
            schema=SCHEMA,
            sources=len(records),
            max_download_bytes=max_download_bytes,
            paid_spend_usd=0,
            provider_calls=0,
        )
    ]
    rows.extend(hbp_row("FETCH", schema=SCHEMA, **record) for record in records)
    write_bundle(receipt_dir, "SOURCE-FETCH", rows)
    return records


def deterministic_fixture_bytes(label: str, size: int) -> bytes:
    output = bytearray()
    counter = 0
    while len(output) < size:
        token = sha256_bytes(f"{label}|{counter}".encode("utf-8"))
        output.extend(f"{label}|{counter:08d}|{token}\n".encode("utf-8"))
        counter += 1
    return bytes(output[:size])


def create_self_test_fixture(root: Path) -> Path:
    raw = root / "raw"
    requirements = {
        "UNICODE_UNIKEMET": DOMAIN_SLICE_TARGETS["HERITAGE_SCRIPT"] * SLICE_BYTES,
        "PETRIE_GIZEH_1883": DOMAIN_SLICE_TARGETS["ARCHITECTURE"] * SLICE_BYTES,
        "JPL_HORIZONS": DOMAIN_SLICE_TARGETS["ASTRONOMY_PI"] * SLICE_BYTES,
    }
    for source_id, size in requirements.items():
        directory = raw / source_id
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{source_id.lower()}.txt").write_bytes(
            deterministic_fixture_bytes(source_id, size + 65536)
        )
    write_lf(
        raw / "JPL_HORIZONS" / "SOURCE-AUTHORITY.hbp",
        hbp_row(
            "SOURCEAUTHORITY",
            source_id="JPL_HORIZONS",
            payload_allowed=1,
            payload_class="BOUNDED_QUERY_FIXTURE",
            query_sha256=sha256_bytes(b"SELF_TEST_QUERY"),
            test_only=1,
        ),
    )
    held = raw / "HARVARD_CMHI"
    held.mkdir(parents=True, exist_ok=True)
    (held / "must-never-enter.txt").write_bytes(
        deterministic_fixture_bytes("HELD_POINTER_ONLY", 2 * 1024 * 1024)
    )
    return raw


def self_test() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="heritage-cosmos-selftest-") as temp:
        root = Path(temp)
        raw = create_self_test_fixture(root)
        first = build_corpus(
            DEFAULT_CONTRACT,
            DEFAULT_CATALOG,
            DEFAULT_BODY_MAP,
            raw,
            root / "out-a",
        )
        second = build_corpus(
            DEFAULT_CONTRACT,
            DEFAULT_CATALOG,
            DEFAULT_BODY_MAP,
            raw,
            root / "out-b",
        )
        if first["corpus_root_sha256"] != second["corpus_root_sha256"]:
            raise AssertionError("deterministic corpus root mismatch")
        if first["source_stream_sha256"] != second["source_stream_sha256"]:
            raise AssertionError("deterministic source stream mismatch")
        source_use = (
            root / "out-a" / "receipts" / "SOURCE-USE.hbp"
        ).read_text(encoding="utf-8")
        held_row = next(
            line
            for line in source_use.splitlines()
            if "source_id=HARVARD_CMHI" in line
        )
        _, held_fields = parse_hbp_line(held_row)
        if held_fields["used_bytes"] != "0":
            raise AssertionError("pointer-only source contributed payload")
        language_hbp = (
            root / "out-a" / "receipts" / "BODY-LANGUAGES.hbp"
        ).read_text(encoding="utf-8")
        language_ids = []
        for line in language_hbp.splitlines():
            kind, fields = parse_hbp_line(line)
            if kind == "BODYLANGUAGE":
                if fields.get("roundtrip") != "1":
                    raise AssertionError("local language roundtrip missing")
                language_ids.append(fields["local_language_id"])
        if len(language_ids) != 40 or len(set(language_ids)) != 40:
            raise AssertionError("local language uniqueness invariant failed")
        return first


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument(
        "--phase", choices=["build", "verify", "fetch"], default="build"
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--body-map", type=Path, default=DEFAULT_BODY_MAP)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source-id", action="append", default=[])
    parser.add_argument("--max-download-mib", type=int, default=32)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(os.sys.argv[1:] if argv is None else argv)
    if args.self_test:
        result = self_test()
        print(
            hbp_row(
                "SELFTEST",
                ok=1,
                slices=result["slices"],
                slice_bytes=result["slice_bytes"],
                corpus_root_sha256=result["corpus_root_sha256"],
                system_binding_root_sha256=result["system_binding_root_sha256"],
                local_languages=40,
                external_model_calls=0,
            )
        )
        return 0
    if args.phase == "fetch":
        records = fetch_phase(
            args.catalog.resolve(),
            args.raw_root.resolve(),
            args.source_id,
            args.max_download_mib * 1024 * 1024,
        )
        print(hbp_row("FETCHDONE", sources=len(records), paid_spend_usd=0))
        return 0
    if args.phase == "verify":
        result = verify_output(args.output.resolve())
        print(hbp_row("VERIFYDONE", ok=1, **result))
        return 0
    result = build_corpus(
        args.contract.resolve(),
        args.catalog.resolve(),
        args.body_map.resolve(),
        args.raw_root.resolve(),
        args.output.resolve(),
    )
    print(hbp_row("BUILDDONE", ok=1, **result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
