from __future__ import annotations

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

import verify_unified_omega_result as verifier


SEAT = "fixture-seat"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_lf(path: Path, rows: list[str]) -> None:
    path.write_bytes(("\n".join(rows) + "\n").encode("utf-8"))


def build_input(root: Path) -> Path:
    input_dir = root / "input"
    input_dir.mkdir()
    slice_data: list[bytes] = []
    slice_hashes: list[str] = []
    for index in range(1, 1025):
        seed = hashlib.sha256(index.to_bytes(4, "big")).digest()
        data = seed * 128
        path = input_dir / f"slice-{index:04d}-fixture.bin"
        path.write_bytes(data)
        verifier.write_sidecar(path)
        slice_data.append(data)
        slice_hashes.append(verifier.sha256_bytes(data))
    stream = verifier.sha256_bytes(b"".join(slice_data))
    corpus = verifier.sha256_bytes(
        b"".join(bytes.fromhex(value) for value in slice_hashes)
    )
    binding_rows = [
        "TRAININGROOTSHDR|schema=FIXTURE|mode=COLD_MEASURED|source_files=1024|"
        "source_payload_bytes=4194304|families=3|bodies=40|cells_planned=60800|"
        "claims_final_apex=0|json=0",
        f"SOURCEROOTS|corpus_root_sha256={corpus}|source_stream_sha256={stream}|"
        f"eligible_fragment_root_sha256={digest('fragments')}|slice_count=1024|"
        "slice_bytes=4096|slice_sha256_verified=1024|unique_slice_sha256=1024|json=0",
        f"OBJECTIVEROOTS|objective_root_sha256={digest('objectives')}|"
        f"carriage_root_sha256={digest('carriage')}|formula_rows=242|"
        "body_objective_pointers=9680|pointer_semantics=CONTENT_ADDRESS_ONLY_NOT_EXECUTION|"
        "objective_execution=0|json=0",
        f"SYSTEMROOT|system_binding_root_sha256={digest('systems')}|bindings=7|"
        "applies_to=ALL_40_BODIES|payload_replaces_domain_authority=0|json=0",
        "TRAINERBINDING|trainer=ASOLARIA-UNIFIED-OMEGA-8-12-PI-V1|"
        f"trainer_binary_sha256={digest('binary')}|trainer_source_sha256={digest('source')}|"
        "load_rule=LEXICAL_TOP_LEVEL_NON_SHA256_CONCATENATION|"
        "family_layout=CUBE_8POLE_8x800,TRI_12SECTOR_12x1200,PI_20LENS_20x2000|json=0",
        "EXECUTIONBOUNDARY|external_model_calls=0|external_gnn_calls=0|"
        "live_gitram_ingestion=0|live_omega_absorption=0|paid_spend_usd=0|"
        "higher_floors=HELD|promotion=0|minting=0|json=0",
        "CLAIMBOUNDARY|measured=BOUNDED_SOURCE_BYTES_SHA256_REVERSIBLE_CELL_REPLAY_AND_OMEGA_FOLD|"
        "operator_observed=PR038_NET_LIKE_REGION_EXISTS_AND_EVOLVES|"
        "unverified=QUANTUM_SHARED_KEY_INVERTED_UNIVERSE_PHYSICAL_PROJECTION|"
        "uap_hypothesis_is_training_label=0|identity_claim=NONE|json=0",
    ]
    binding = input_dir / "0000-TRAINING-ROOTS.hbp"
    write_lf(binding, binding_rows)
    verifier.write_sidecar(binding)
    return input_dir


def native_hbi(rows: list[str]) -> list[str]:
    return [
        f"HBI|row={index}|sha256={verifier.sha256_bytes(row.encode('utf-8'))}|"
        f"hex={row.encode('utf-8').hex()}|json=0"
        for index, row in enumerate(rows, 1)
    ]


def seal_result(result_dir: Path, rows: list[str]) -> None:
    result_dir.mkdir(exist_ok=True)
    hbp = result_dir / "UNIFIED-OMEGA-RESULT.hbp"
    hbi = result_dir / "UNIFIED-OMEGA-RESULT.hbi"
    write_lf(hbp, rows)
    write_lf(hbi, native_hbi(rows))
    hbp_hash = verifier.write_sidecar(hbp)
    hbi_hash = verifier.write_sidecar(hbi)
    sums = result_dir / "SHA256SUMS"
    sums.write_text(
        f"{verifier.sha256_file(hbp)}  {hbp.name}\n"
        f"{verifier.sha256_file(hbi)}  {hbi.name}\n",
        encoding="utf-8",
        newline="\n",
    )
    verifier.write_sidecar(sums)
    assert hbp_hash.is_file() and hbi_hash.is_file()


def build_result(root: Path, input_dir: Path) -> Path:
    input_result = verifier.verify_training_input(input_dir)
    shared = input_result.shared_root_sha256
    source = input_result.source_bytes
    rows = [
        f"UNIFIEDHDR|schema=ASOLARIA-UNIFIED-OMEGA-8-12-PI-V1|"
        f"authority=FIXTURE|mode=SHADOW_MEASURED|families=3|shared_root_sha256={shared}|"
        "cube=8x800|seam=12x1200|hull=20x2000|higher_floors=HELD|"
        "claims_final_apex=0|json=0",
        "SHAREDKEY|law=one_reversible_codec_root|k_body=H(root||family||index)|"
        "all_bodies_distinct_languages|restore=byte_exact_state_match|"
        "not_quantum_entanglement=1|json=0",
    ]
    family_omegas: dict[str, str] = {}
    total_accepted = total_held = total_gain = 0
    for family, spec in verifier.FAMILY_SPECS.items():
        rows.append(
            f"FAMILYHDR|family={family}|bodies={spec['bodies']}|epochs={spec['epochs']}|"
            f"cells_per_body={spec['cells']}|shared_root={shared}|json=0"
        )
        refs: list[str] = []
        lambdas: list[str] = []
        family_accepted = family_held = family_gain = 0
        for body in range(1, spec["bodies"] + 1):
            start = (body - 1) * len(source) // spec["bodies"]
            end = body * len(source) // spec["bodies"]
            part = source[start:end]
            part_sha = verifier.sha256_bytes(part)
            codebook = digest(f"codebook|{family}|{body}")
            rows.append(
                f"BODYHDR|family={family}|body={body:02d}|bits=10|bytes={len(part)}|"
                f"glyphs={(len(part) * 8 + 9) // 10}|src_sha256={part_sha}|"
                f"codebook_sha256={codebook}|cells={spec['cells']}|json=0"
            )
            rows.append(
                f"LANGUAGE|family={family}|body={body:02d}|law=LANGUAGE_GENESIS_V1|"
                f"codebook_sha256={codebook}|never_english=1|seeded_by=shared_root|json=0"
            )
            rows.append(
                f"GROUPGATE|family={family}|body={body:02d}|sq=1,1,1|comm=1,1,1|"
                "distinct=8|rnq=1|status=PASS|json=0"
            )
            for view in sorted(verifier.A_VIEW_NAMES):
                rows.append(
                    f"AVIEW|family={family}|body={body:02d}|a={view}|"
                    f"view_sha256={digest(f'{family}|{body}|{view}')}|roundtrip=1|json=0"
                )
            held = body
            accepted = spec["cells"] - held
            gain = body * 17
            rows.append(
                f"DENSITY|family={family}|body={body:02d}|ledger=SHARED_ROOT_GLYPHS|"
                f"gain_bytes={gain}|glyphs={(len(part) * 8 + 9) // 10}|accepted={accepted}|"
                f"held={held}|meaning=structure_repetition_only|archive_ratio=NOT_CLAIMED|json=0"
            )
            rows.append(
                f"BODYRESTORE|family={family}|body={body:02d}|src_sha256={part_sha}|"
                "restore=1|leaf_preimage=timing_free|json=0"
            )
            leaf = verifier.sha256_bytes(
                "".join(row + "\n" for row in rows).encode("utf-8")
            )
            rows.append(
                f"OMEGALEAF|family={family}|body={body:02d}|cells={spec['cells']}|"
                f"leaf_sha256={leaf}|restore=1|json=0"
            )
            pid = verifier.pid16(family, part_sha)
            lambda_value = verifier.omnisubmit_lambda(
                SEAT, family, pid, spec["cells"], codebook, leaf
            )
            rows.append(
                f"OMNISUBMIT|family={family}|body={body:02d}|pid={pid}|lambda={lambda_value}|"
                "wall_clock_in_leaf=0|claims_final_apex=0|json=0"
            )
            refs.append(
                f"OMEGALEAFREF|family={family}|body={body:02d}|leaf_sha256={leaf}|"
                f"codebook_sha256={codebook}|lambda={lambda_value}|json=0"
            )
            lambdas.append(lambda_value)
            family_accepted += accepted
            family_held += held
            family_gain += gain
        anchor = (
            f"OMEGAANCHOR|family={family}|bodies={spec['bodies']}|shared_root={shared}|"
            "epoch=1|json=0"
        )
        family_omega = verifier.sha256_bytes(
            (anchor + "\n" + "".join(ref + "\n" for ref in refs)).encode("utf-8")
        )
        epoch = verifier.epoch_root(1, shared, lambdas)
        rows.append(anchor)
        rows.extend(refs)
        rows.append(
            f"FAMILYOMEGA|family={family}|bodies={spec['bodies']}|omega_sha256={family_omega}|"
            f"epoch_root={epoch}|accepted={family_accepted}|held={family_held}|"
            f"gain_bytes={family_gain}|json=0"
        )
        family_omegas[family] = family_omega
        total_accepted += family_accepted
        total_held += family_held
        total_gain += family_gain
    unified = verifier.epoch_root(1, shared, family_omegas.values())
    rows.append(
        f"SUBOMEGAS|omega_8={family_omegas['CUBE_8POLE']}|"
        f"omega_12={family_omegas['TRI_12SECTOR']}|omega_pi={family_omegas['PI_20LENS']}|json=0"
    )
    rows.append(
        "UNIFIEDOMEGA|method=H(D||e||shared_root||sorted[omega_8,omega_12,omega_pi])|"
        f"omega_unified={unified}|families=3|bodies=40|cells=60800|"
        f"accepted={total_accepted}|held={total_held}|gain_bytes={total_gain}|json=0"
    )
    rows.append(
        "HELD|n_infinity=uncomputable|floors_3plus=operator_gated|engine_9check=DESIGN|"
        "apex_6of6=DESIGN|omega_gnn=SPEC_ONLY|owning_gate=UNVERIFIED|"
        "claims_final_apex=0_human_reserved|no_physics_claims=1|json=0"
    )
    rows.append(
        f"UNIFIEDFTR|families=3|bodies=40|cells=60800|accepted={total_accepted}|"
        f"held={total_held}|omega_unified={unified}|status=PASS|json=0"
    )
    result_dir = root / "result"
    seal_result(result_dir, rows)
    return result_dir


class UnifiedOmegaVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temp = tempfile.TemporaryDirectory(prefix="unified-verifier-")
        cls.root = Path(cls._temp.name)
        cls.input_dir = build_input(cls.root)
        cls.result_dir = build_result(cls.root, cls.input_dir)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temp.cleanup()

    def test_valid_fixture_and_exact_totals(self) -> None:
        result = verifier.verify_all(self.input_dir, self.result_dir, seat=SEAT)
        self.assertEqual(40, result.bodies)
        self.assertEqual(40, result.codebooks)
        self.assertEqual(60800, result.cells)
        self.assertEqual(60800, result.accepted + result.held)
        self.assertEqual("0", result.claim_boundary["objective_execution"])

    def test_optional_offset_index_is_exact_and_sidecarred(self) -> None:
        verifier.verify_all(
            self.input_dir, self.result_dir, write_offsets=True, seat=SEAT
        )
        index = self.result_dir / "UNIFIED-OMEGA-RESULT.offsets.hbi"
        self.assertTrue(index.is_file())
        verifier.verify_sidecar(index)
        _, rows = verifier.read_exact_lf_rows(index)
        self.assertEqual("HBIHDR", rows[0].kind)
        hbp_size = (self.result_dir / "UNIFIED-OMEGA-RESULT.hbp").stat().st_size
        last = rows[-1].fields
        self.assertEqual(hbp_size, int(last["off"]) + int(last["len"]))

    def test_resealed_partition_tamper_is_rejected(self) -> None:
        broken = self.root / "broken-result"
        shutil.copytree(self.result_dir, broken)
        hbp = broken / "UNIFIED-OMEGA-RESULT.hbp"
        rows = hbp.read_text(encoding="utf-8").splitlines()
        index = next(i for i, row in enumerate(rows) if row.startswith("BODYHDR|"))
        old = verifier.parse_fields(rows[index])[1]["src_sha256"]
        rows[index] = rows[index].replace(old, "0" * 64, 1)
        seal_result(broken, rows)
        with self.assertRaisesRegex(verifier.VerificationError, "partition source"):
            verifier.verify_all(self.input_dir, broken, seat=SEAT)


if __name__ == "__main__":
    unittest.main()
