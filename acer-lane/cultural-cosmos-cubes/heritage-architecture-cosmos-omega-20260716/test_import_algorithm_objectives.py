from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import fetch_and_slice_sources as cold
import import_algorithm_objectives as importer


class AlgorithmObjectiveImporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not importer.DEFAULT_SOURCE.is_file():
            raise unittest.SkipTest(
                "pinned Algorithms authority is not redistributed; set "
                "ASOLARIA_ALGORITHMS_SOURCE to its verified local path"
            )
        cls._temp = tempfile.TemporaryDirectory(
            prefix="algorithm-objective-unittest-"
        )
        cls.output = Path(cls._temp.name)
        cls.summary = importer.build(
            importer.DEFAULT_SOURCE,
            importer.DEFAULT_CATALOG,
            importer.DEFAULT_BODY_MAP,
            cls.output,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temp.cleanup()

    def test_source_authority_and_formula_coverage(self) -> None:
        self.assertEqual(
            importer.EXPECTED_SOURCE_SHA256,
            self.summary["source_sha256"],
        )
        self.assertEqual(importer.FORMULA_COUNT, self.summary["formula_rows"])
        rows = cold.read_hbp_rows(self.output / "ALGORITHM-OBJECTIVES.hbp")
        objectives = [
            fields
            for kind, fields, _ in rows
            if kind == "ALGORITHMOBJECTIVE"
        ]
        self.assertEqual(importer.FORMULA_COUNT, len(objectives))
        self.assertEqual(
            importer.FORMULA_COUNT,
            len({fields["pid"] for fields in objectives}),
        )
        self.assertTrue(
            all(len(fields["source_row_sha256"]) == 64 for fields in objectives)
        )

    def test_every_body_carries_every_objective_slice(self) -> None:
        rows = cold.read_hbp_rows(self.output / "OBJECTIVE-CARRIAGE.hbp")
        bodies = [
            fields for kind, fields, _ in rows if kind == "BODYOBJECTIVEROOT"
        ]
        pointers = [
            fields for kind, fields, _ in rows if kind == "OBJECTIVECARRIAGE"
        ]
        self.assertEqual(importer.BODY_COUNT, len(bodies))
        self.assertEqual(importer.POINTER_COUNT, len(pointers))
        self.assertEqual(
            importer.BODY_COUNT,
            len({fields["local_language_slot"] for fields in bodies}),
        )
        by_body: dict[str, set[int]] = {}
        for pointer in pointers:
            by_body.setdefault(pointer["body_id"], set()).add(
                int(pointer["objective_slice"])
            )
            self.assertEqual("0", pointer["execution"])
        expected = set(range(1, importer.FORMULA_COUNT + 1))
        self.assertEqual(importer.BODY_COUNT, len(by_body))
        self.assertTrue(all(slices == expected for slices in by_body.values()))

    def test_bundle_and_semantic_verification(self) -> None:
        verified = importer.verify(
            importer.DEFAULT_SOURCE,
            importer.DEFAULT_CATALOG,
            importer.DEFAULT_BODY_MAP,
            self.output,
        )
        self.assertEqual(
            self.summary["objective_root_sha256"],
            verified["objective_root_sha256"],
        )
        self.assertEqual(
            self.summary["carriage_root_sha256"],
            verified["carriage_root_sha256"],
        )

    def test_source_hash_mismatch_is_rejected(self) -> None:
        altered = self.output / "altered-source.hbp"
        altered.write_bytes(importer.DEFAULT_SOURCE.read_bytes() + b"\n")
        with self.assertRaisesRegex(RuntimeError, "source SHA-256 mismatch"):
            importer.load_objectives(altered)


if __name__ == "__main__":
    unittest.main()
