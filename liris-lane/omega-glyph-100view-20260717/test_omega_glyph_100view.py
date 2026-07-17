from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

import omega_glyph_100view as subject
import verify_receipts


FIXTURE = (
    b"synthetic glyph fixture only\n"
    b"observed tokens: 8 12 20 120\n"
    b"conditional tokens: 120 7 840\n"
    b"product tokens: 8 12 20 7680\n"
    + bytes(range(256)) * 20
)


class OmegaGlyphTests(unittest.TestCase):
    def test_glyph_roundtrip_and_eight_exact_a_views(self) -> None:
        glyphs = subject.b2g(FIXTURE)
        self.assertEqual(subject.g2b(glyphs, len(FIXTURE)), FIXTURE)
        seed = subject.sha256_bytes(subject.pack_glyphs(glyphs))
        for index in range(8):
            viewed = subject.a_apply(index, glyphs, seed)
            self.assertEqual(subject.a_inverse(index, viewed, seed), glyphs)

    def test_frequency_primary_100_composites(self) -> None:
        data = subject.deterministic_canary()
        glyphs = subject.b2g(data)
        seed = subject.sha256_bytes(subject.pack_glyphs(glyphs))
        descriptors = subject.build_descriptors(subject.sha256(data), 100)
        self.assertEqual(len({item.wavelength for item in descriptors}), 100)
        self.assertTrue(all(len(item.pid) == 64 for item in descriptors))
        digests = set()
        for descriptor in descriptors:
            viewed = subject.composite_apply(glyphs, descriptor, seed)
            self.assertEqual(subject.composite_inverse(viewed, descriptor, seed), glyphs)
            digests.add(subject.sha256(subject.pack_glyphs(viewed)))
        self.assertEqual(len(digests), 100)

    def test_numeric_parser_does_not_infer_semantics(self) -> None:
        occurrences, candidates = subject.parse_numeric_evidence(FIXTURE)
        for value in subject.TARGET_NUMBERS:
            self.assertGreaterEqual(len(occurrences[value]), 1)
        self.assertEqual(len(candidates), 3)
        self.assertEqual(candidates[0]["tokens"], "8,12,20,120")

    def test_exact_1e200_address_partition(self) -> None:
        ranges = subject.logical_ranges(100)
        self.assertEqual(len(ranges), 100)
        self.assertEqual(ranges[0][0], 0)
        self.assertEqual(ranges[-1][1] + 1, 10**200)
        self.assertTrue(all(left[1] + 1 == right[0] for left, right in zip(ranges, ranges[1:])))
        self.assertTrue(all(count == 10**198 for _, _, count in ranges))

    def test_gf257_controls_and_joint_recovery(self) -> None:
        result = subject.run_projection(hashlib.sha256(FIXTURE).digest())
        self.assertEqual(result.unique_rank, 60)
        self.assertEqual(result.duplicate_rank, 10)
        self.assertEqual(result.unique_restores, 100)
        self.assertEqual(result.shuffled_restores, 100)
        self.assertEqual(result.binding_restores, 0)
        self.assertEqual(result.misbound_nonabstaining_wrong, 100)
        self.assertEqual(result.case_unique, 100)

    def test_full_receipts_offsets_hashes_and_replay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = Path(__file__).resolve().parent
            glyph = project / "fixtures" / "synthetic-glyph.txt"
            out = root / "out"
            result = subject.run_experiment(glyph, out, "SYNTHETIC_TEST_FIXTURE", 100)
            self.assertEqual(result.view_count, 100)
            self.assertEqual(result.unique_canary, 100)
            self.assertEqual((out / "GLYPH-INPUT.bin").read_bytes(), glyph.read_bytes())
            hbp = (out / "OMEGA-GLYPH-100VIEW.hbp").read_bytes()
            hbi = (out / "OMEGA-GLYPH-100VIEW.hbi").read_text("utf-8")
            self.assertEqual(hashlib.sha256(hbp).hexdigest(), result.hbp_sha)
            self.assertIn(f"target_sha256={result.hbp_sha}", hbi)
            for line in hbi.splitlines()[1:]:
                fields = dict(part.split("=", 1) for part in line.split("|")[1:] if "=" in part)
                offset = int(fields["offset"])
                length = int(fields["length"])
                body = hbp[offset : offset + length]
                self.assertEqual(hashlib.sha256(body).hexdigest(), fields["row_sha256"])
            descriptor = subject.build_descriptors(result.input_sha)[37]
            by_view = subject.replay(glyph, descriptor.view_id)
            by_pid = subject.replay(glyph, descriptor.pid)
            self.assertIn("byte_exact=1", by_view)
            self.assertIn("byte_exact=1", by_pid)
            self.assertIn(f"pid={descriptor.pid}", by_view)
            sums = (out / "SHA256SUMS").read_text("utf-8")
            for name in ("GLYPH-INPUT.bin", "OMEGA-GLYPH-100VIEW.hbp", "OMEGA-GLYPH-100VIEW.hbi", "RESULTS.md"):
                self.assertIn(name, sums)
            verified = verify_receipts.verify_directory(out)
            self.assertEqual(verified["views"], 100)
            golden = project / "synthetic-output"
            for name in (
                "GLYPH-INPUT.bin",
                "OMEGA-GLYPH-100VIEW.hbp",
                "OMEGA-GLYPH-100VIEW.hbi",
                "RESULTS.md",
                "SHA256SUMS",
                "SHA256SUMS.sha256",
            ):
                self.assertEqual((out / name).read_bytes(), (golden / name).read_bytes(), name)

    def test_omega_leaf_order_is_sorted(self) -> None:
        input_sha = subject.sha256(FIXTURE)
        leaves = [subject.sha256(b"b"), subject.sha256(b"a"), subject.sha256(b"c")]
        self.assertEqual(subject.omega_commit(input_sha, leaves), subject.omega_commit(input_sha, reversed(leaves)))

    def test_indexed_rows_bind_order(self) -> None:
        input_sha = subject.sha256(FIXTURE)
        first = subject.omega_commit(input_sha, subject.indexed_row_leaves(["a", "b"]))
        second = subject.omega_commit(input_sha, subject.indexed_row_leaves(["b", "a"]))
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
