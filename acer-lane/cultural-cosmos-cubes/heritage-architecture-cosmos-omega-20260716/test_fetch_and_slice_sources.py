from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import fetch_and_slice_sources as builder


class ColdCorpusBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temp = tempfile.TemporaryDirectory(
            prefix="heritage-cosmos-unittest-"
        )
        cls.root = Path(cls._temp.name)
        cls.raw = builder.create_self_test_fixture(cls.root)
        cls.output_a = cls.root / "output-a"
        cls.output_b = cls.root / "output-b"
        cls.result_a = builder.build_corpus(
            builder.DEFAULT_CONTRACT,
            builder.DEFAULT_CATALOG,
            builder.DEFAULT_BODY_MAP,
            cls.raw,
            cls.output_a,
        )
        cls.result_b = builder.build_corpus(
            builder.DEFAULT_CONTRACT,
            builder.DEFAULT_CATALOG,
            builder.DEFAULT_BODY_MAP,
            cls.raw,
            cls.output_b,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temp.cleanup()

    def test_static_contract_and_exact_pins(self) -> None:
        sources, source_by_id = builder.load_source_catalog(
            builder.DEFAULT_CATALOG
        )
        bodies, bindings = builder.load_body_map(
            builder.DEFAULT_BODY_MAP, source_by_id
        )
        self.assertEqual(47, len(sources))
        self.assertEqual(40, len(bodies))
        self.assertEqual(7, len(bindings))
        self.assertTrue(
            all(len(binding["commit_sha"]) == 40 for binding in bindings)
        )
        self.assertTrue(
            all(len(binding["tree_sha"]) == 40 for binding in bindings)
        )
        self.assertEqual(
            40, len({body["language_slot"] for body in bodies})
        )
        expected_domains = {
            "HERITAGE_8": "HERITAGE_SCRIPT",
            "ARCHITECTURE_12": "ARCHITECTURE",
            "ASTRONOMY_PI_20": "ASTRONOMY_PI",
        }
        for body in bodies:
            for source_id in body["sources"].split(","):
                if source_id in builder.DERIVED_BODY_SOURCES:
                    domain = builder.DERIVED_BODY_SOURCES[source_id]
                else:
                    domain = source_by_id[source_id].domain
                self.assertEqual(expected_domains[body["family"]], domain)

    def test_exact_slice_geometry_and_determinism(self) -> None:
        slices_a = sorted((self.output_a / "slices").glob("slice-*.bin"))
        slices_b = sorted((self.output_b / "slices").glob("slice-*.bin"))
        self.assertEqual(builder.SLICE_COUNT, len(slices_a))
        self.assertEqual(builder.SLICE_COUNT, len(slices_b))
        self.assertTrue(
            all(path.stat().st_size == builder.SLICE_BYTES for path in slices_a)
        )
        self.assertEqual(
            self.result_a["corpus_root_sha256"],
            self.result_b["corpus_root_sha256"],
        )
        self.assertEqual(
            self.result_a["source_stream_sha256"],
            self.result_b["source_stream_sha256"],
        )
        self.assertEqual(
            [builder.sha256_file(path) for path in slices_a],
            [builder.sha256_file(path) for path in slices_b],
        )

    def test_pointer_only_payload_is_ignored(self) -> None:
        path = self.output_a / "receipts" / "SOURCE-USE.hbp"
        held_fields = None
        for line in path.read_text(encoding="utf-8").splitlines():
            kind, fields = builder.parse_hbp_line(line)
            if kind == "SOURCEUSE" and fields.get("source_id") == "HARVARD_CMHI":
                held_fields = fields
                break
        self.assertIsNotNone(held_fields)
        assert held_fields is not None
        self.assertEqual("0", held_fields["used_bytes"])
        self.assertEqual("METADATA_ONLY_POLICY", held_fields["reason"])

    def test_hbp_hbi_hex_sha_and_manifest_verify(self) -> None:
        result = builder.verify_output(self.output_a)
        self.assertEqual(builder.SLICE_COUNT, result["slices"])
        self.assertGreater(result["receipt_rows"], builder.SLICE_COUNT)
        self.assertGreater(result["manifest_entries"], builder.SLICE_COUNT)

    def test_body_source_validation_rejects_unknown_source(self) -> None:
        broken = self.root / "BODY-MAP-BROKEN.hbp"
        text = builder.DEFAULT_BODY_MAP.read_text(encoding="utf-8").replace(
            "sources=UNICODE_UNIKEMET,BBAW_TLA_RAW",
            "sources=UNICODE_UNIKEMET,NOT_A_REAL_SOURCE",
            1,
        )
        builder.write_lf(broken, text)
        _, source_by_id = builder.load_source_catalog(builder.DEFAULT_CATALOG)
        with self.assertRaisesRegex(
            ValueError, "body source missing from catalog"
        ):
            builder.load_body_map(broken, source_by_id)

    def test_semantic_verifier_rejects_resealed_bad_slice_map(self) -> None:
        import shutil

        broken_output = self.root / "semantic-broken"
        shutil.copytree(self.output_a, broken_output)
        receipts = broken_output / "receipts"
        rows = [
            raw
            for _, _, raw in builder.read_hbp_rows(
                receipts / "SLICE-MAP.hbp"
            )
        ]
        rows[1] = rows[1].replace(
            "|sha256=", "|sha256=" + ("0" * 64) + "|original_sha256=", 1
        )
        builder.write_bundle(receipts, "SLICE-MAP", rows)
        builder.write_checksum_manifest(broken_output)
        with self.assertRaisesRegex(RuntimeError, "SLICE-MAP content mismatch"):
            builder.verify_output(broken_output)

    def test_languages_are_unique_and_reversible(self) -> None:
        path = self.output_a / "receipts" / "BODY-LANGUAGES.hbp"
        language_ids = []
        for line in path.read_text(encoding="utf-8").splitlines():
            kind, fields = builder.parse_hbp_line(line)
            if kind != "BODYLANGUAGE":
                continue
            language_ids.append(fields["local_language_id"])
            self.assertEqual("1", fields["roundtrip"])
            self.assertEqual("XOR_SHA256_CTR", fields["codec"])
        self.assertEqual(40, len(language_ids))
        self.assertEqual(40, len(set(language_ids)))

    def test_learning_and_live_ledgers_stay_zero(self) -> None:
        receipts = self.output_a / "receipts"
        expected = {
            "02-MODEL-LOCAL-RELATIONS.hbp": ("relations", "0"),
            "03-RECURRENT-STATE-TRANSITIONS.hbp": ("transitions", "0"),
            "04-UPWARD-LINEAGE-LINKS.hbp": ("links", "0"),
            "05-EXTERNAL-MODEL-CALLS.hbp": ("external_model_calls", "0"),
        }
        for filename, (key, value) in expected.items():
            first = (receipts / filename).read_text(encoding="utf-8").splitlines()[0]
            _, fields = builder.parse_hbp_line(first)
            self.assertEqual(value, fields[key])
        external = (
            receipts / "05-EXTERNAL-MODEL-CALLS.hbp"
        ).read_text(encoding="utf-8")
        _, fields = builder.parse_hbp_line(external.splitlines()[0])
        for key in (
            "provider_calls",
            "external_gnn_calls",
            "gpu_calls",
            "paid_spend_usd",
            "live_gitram_ingestion",
            "live_gnn_training",
            "live_omega_absorption",
            "promotion",
            "minting",
        ):
            self.assertEqual("0", fields[key])

    def test_short_sources_fail_without_padding_or_repetition(self) -> None:
        short_root = self.root / "short"
        raw = short_root / "raw"
        for source_id in (
            "UNICODE_UNIKEMET",
            "PETRIE_GIZEH_1883",
            "JPL_HORIZONS",
        ):
            directory = raw / source_id
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "small.txt").write_text(
                "intentionally short\n", encoding="utf-8"
            )
        builder.write_lf(
            raw / "JPL_HORIZONS" / "SOURCE-AUTHORITY.hbp",
            builder.hbp_row(
                "SOURCEAUTHORITY",
                source_id="JPL_HORIZONS",
                payload_allowed=1,
                payload_class="BOUNDED_QUERY_FIXTURE",
                test_only=1,
            ),
        )
        with self.assertRaisesRegex(RuntimeError, "never padded or repeated"):
            builder.build_corpus(
                builder.DEFAULT_CONTRACT,
                builder.DEFAULT_CATALOG,
                builder.DEFAULT_BODY_MAP,
                raw,
                short_root / "output",
            )

    def test_operator_rows_preserve_scope(self) -> None:
        contract = builder.DEFAULT_CONTRACT.read_text(encoding="utf-8")
        self.assertIn(
            "OPERATORWITNESS|claim_class=OPERATOR_WITNESSED_NO_MEDIA",
            contract,
        )
        self.assertIn("evidence_score_input=0", contract)
        self.assertIn(
            "OPERATORHYPOTHESIS|claim_class=OPERATOR_PROPOSED_PHYSICAL_MECHANISM",
            contract,
        )
        self.assertIn("physical_mechanism=UNVERIFIED", contract)


if __name__ == "__main__":
    unittest.main()
