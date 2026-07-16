from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

import build_unified_body_language_bridge as bridge


def digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


class UnifiedBodyLanguageBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.body_map = self.root / "BODY-MAP.hbp"
        self.cold = self.root / "BODY-LANGUAGES.hbp"
        self.unified = self.root / "UNIFIED-OMEGA-RESULT.hbp"
        self.output = self.root / "out"
        self.write_body_map()
        self.write_cold_languages()
        self.write_unified_result()

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def body_specs():
        for named, (prefix, geometric, count, cells) in (
            bridge.FAMILY_BRIDGES.items()
        ):
            for ordinal in range(1, count + 1):
                yield named, prefix, geometric, count, cells, ordinal

    def write_body_map(self) -> None:
        rows = [
            "BODYMAP|schema=TEST|heritage=8|architecture=12|astronomy_pi=20|"
            "total=40|language_id_rule=TEST|codec=XOR_SHA256_CTR|json=0",
            "OBJECTIVECARRIAGEMAP|source_artifact=ALGORITHM-OBJECTIVES.hbp|"
            f"carriage_artifact=OBJECTIVE-CARRIAGE.hbp|source_sha256={digest('obj-source')}|"
            f"formula_rows=242|objective_root_sha256={digest('obj-root')}|"
            f"bodies=40|pointers=9680|carriage_root_sha256={digest('carriage')}|"
            "execution=0|live_absorption=0|promotion=0|json=0",
        ]
        for named, prefix, _geometric, _count, cells, ordinal in self.body_specs():
            body_id = f"{prefix}{ordinal:02d}"
            rows.append(
                f"BODY|family={named}|body_id={body_id}|ordinal={ordinal}|"
                f"name=NAME_{body_id}|sources=TEST|language_slot=LANG_{body_id}|"
                f"passes={cells}|historical_translation_claim=NONE|json=0"
            )
        self.body_map.write_text("\n".join(rows) + "\n", encoding="utf-8")

    def write_cold_languages(self) -> None:
        rows = [
            "BODYLANGUAGES|bodies=40|codec=XOR_SHA256_CTR|"
            "historical_language_is_not_cube_codec=1|roundtrip_required=1|"
            f"system_binding_root={digest('system')}|json=0"
        ]
        for named, prefix, _geometric, _count, cells, ordinal in self.body_specs():
            body_id = f"{prefix}{ordinal:02d}"
            seed = digest(f"cold-seed:{body_id}")
            rows.append(
                f"BODYLANGUAGE|body_id={body_id}|body_name=NAME_{body_id}|"
                f"codec=XOR_SHA256_CTR|family={named}|"
                f"language_seed_sha256={seed}|"
                f"local_language_id=LANG-{body_id}-{seed[:16]}|passes={cells}|"
                "roundtrip=1|historical_translation_claim=NONE|json=0"
            )
        self.cold.write_text("\n".join(rows) + "\n", encoding="utf-8")

    def write_unified_result(
        self, *, footer_status: str = "PASS", pi_extra_byte: int = 0
    ) -> None:
        shared = digest("shared")
        omega = digest("omega")
        rows = [
            "UNIFIEDHDR|schema=ASOLARIA-UNIFIED-OMEGA-8-12-PI-V1|"
            "authority=TEST|mode=SHADOW_MEASURED|families=3|"
            f"shared_root_sha256={shared}|cube=8x800|seam=12x1200|"
            "hull=20x2000|higher_floors=HELD|claims_final_apex=0|json=0"
        ]
        per_body_bytes = {
            "CUBE_8POLE": 15,
            "TRI_12SECTOR": 10,
            "PI_20LENS": 6,
        }
        for named, (_prefix, geometric, count, cells) in (
            bridge.FAMILY_BRIDGES.items()
        ):
            rows.append(
                f"FAMILYHDR|family={geometric}|bodies={count}|epochs=1|"
                f"cells_per_body={cells}|shared_root={shared}|json=0"
            )
            for ordinal in range(1, count + 1):
                codebook = digest(f"codebook:{geometric}:{ordinal}")
                body_bytes = per_body_bytes[geometric]
                if geometric == "PI_20LENS" and ordinal == count:
                    body_bytes += pi_extra_byte
                rows.append(
                    f"BODYHDR|family={geometric}|body={ordinal:02d}|bits=10|"
                    f"bytes={body_bytes}|glyphs=1|"
                    f"src_sha256={digest(f'src:{geometric}:{ordinal}')}|"
                    f"codebook_sha256={codebook}|cells={cells}|json=0"
                )
                rows.append(
                    f"LANGUAGE|family={geometric}|body={ordinal:02d}|"
                    f"law=LANGUAGE_GENESIS_V1|codebook_sha256={codebook}|"
                    "never_english=1|seeded_by=shared_root|json=0"
                )
        rows.extend(
            [
                f"UNIFIEDOMEGA|method=TEST|omega_unified={omega}|families=3|"
                "bodies=40|cells=60800|accepted=0|held=60800|gain_bytes=0|json=0",
                f"UNIFIEDFTR|families=3|bodies=40|cells=60800|accepted=0|"
                f"held=60800|omega_unified={omega}|status={footer_status}|json=0",
            ]
        )
        self.unified.write_text("\n".join(rows) + "\n", encoding="utf-8")

    def test_builds_exact_40_row_two_language_bridge(self) -> None:
        result = bridge.build_bridge(
            self.body_map, self.cold, self.unified, self.output
        )
        self.assertEqual(result["bodies"], 40)
        self.assertEqual(result["geometric_shared_stream_bytes"], 120)
        self.assertEqual(bridge.verify_bundle(self.output, bridge.DEFAULT_STEM), 47)
        rows = [
            bridge.parse_hbp_line(line)
            for line in result["hbp"].read_text(encoding="utf-8").splitlines()
        ]
        mappings = [row for row in rows if row.kind == "BODYLANGUAGEBRIDGE"]
        self.assertEqual(len(mappings), 40)
        h01 = next(row for row in mappings if row.fields["body_id"] == "H01")
        a12 = next(row for row in mappings if row.fields["body_id"] == "A12")
        p20 = next(row for row in mappings if row.fields["body_id"] == "P20")
        self.assertEqual(h01.fields["geometric_family"], "CUBE_8POLE")
        self.assertEqual(h01.fields["geometric_body"], "01")
        self.assertEqual(a12.fields["geometric_family"], "TRI_12SECTOR")
        self.assertEqual(a12.fields["geometric_body"], "12")
        self.assertEqual(p20.fields["geometric_family"], "PI_20LENS")
        self.assertEqual(p20.fields["geometric_body"], "20")
        for row in mappings:
            self.assertEqual(row.fields["domain_exclusive_training"], "0")
            self.assertEqual(row.fields["historical_translation"], "0")
            self.assertEqual(row.fields["historical_decipherment"], "0")
            self.assertEqual(row.fields["objectives_executed"], "0")
            self.assertEqual(row.fields["language_layers_distinct"], "1")
            self.assertEqual(row.fields["cold_codec"], "XOR_SHA256_CTR")
            self.assertEqual(
                row.fields["geometric_language_law"], "LANGUAGE_GENESIS_V1"
            )

    def test_rejects_non_pass_unified_result_without_output(self) -> None:
        self.write_unified_result(footer_status="HELD")
        with self.assertRaises(RuntimeError):
            bridge.build_bridge(
                self.body_map, self.cold, self.unified, self.output
            )
        self.assertFalse(
            (self.output / f"{bridge.DEFAULT_STEM}.hbp").exists()
        )

    def test_rejects_unequal_family_partition_bytes_without_output(self) -> None:
        self.write_unified_result(pi_extra_byte=1)
        with self.assertRaisesRegex(RuntimeError, "byte totals differ"):
            bridge.build_bridge(
                self.body_map, self.cold, self.unified, self.output
            )
        self.assertFalse(
            (self.output / f"{bridge.DEFAULT_STEM}.hbp").exists()
        )

    def test_rejects_missing_cold_language_without_output(self) -> None:
        lines = self.cold.read_text(encoding="utf-8").splitlines()
        self.cold.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "40 BODYLANGUAGE"):
            bridge.build_bridge(
                self.body_map, self.cold, self.unified, self.output
            )
        self.assertFalse(
            (self.output / f"{bridge.DEFAULT_STEM}.hbp").exists()
        )


if __name__ == "__main__":
    unittest.main()
