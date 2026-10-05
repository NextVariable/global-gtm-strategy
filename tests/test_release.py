"""Release regressions and seeded invariants; no model-quality scoring."""

import copy
import datetime as dt
import importlib.util
import json
import math
import random
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal, localcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/global-gtm-strategy-skill/scripts"
TODAY = dt.date(2026, 10, 5)


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ledger = load("research_state")
maths = load("opportunity_math")


class ReleaseLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "ledger"
        self.identity = dict(client="release", product="synthetic", project="audit")
        ledger.initialize(self.path, self.identity)
        self.context = json.loads((self.path / "context.json").read_text())
        template = json.loads((SCRIPTS.parent / "templates/records.json").read_text())
        self.evidence = copy.deepcopy(template["evidence"])
        self.evidence.update(identity=self.identity, status="current", acquired_at="2026-10-01")
        self.claim = copy.deepcopy(template["observation"])
        self.claim.update(
            identity=self.identity,
            verification=dict(
                method="synthetic audit", checked_at="2026-10-02", scope="schema only"
            ),
        )

    def write_rows(self, name, rows):
        (self.path / f"{name}.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
        )

    def check(self):
        ledger.dump(self.path / "context.json", self.context)
        return ledger.validate(self.path, self.identity, TODAY)

    def test_verification_covers_all_transitive_source_dates(self):
        recent = {**self.evidence, "id": "E2", "acquired_at": "2026-10-05"}
        first = {**self.claim, "sources": ["E2"]}
        fact = {**self.claim, "id": "C2", "premises": ["C1"]}
        self.write_rows("evidence", [self.evidence, recent])
        self.write_rows("claims", [first, fact])
        self.context["facts"] = ["C2"]
        self.assertEqual(self.check()["structural_check"], "fail")
        fact["verification"] = {**fact["verification"], "checked_at": "2026-10-05"}
        self.write_rows("claims", [first, fact])
        self.assertEqual(self.check()["structural_check"], "pass")

    def test_wrong_context_or_state_identity_stops_before_records(self):
        for name in ("context", "state"):
            with self.subTest(file=name):
                file = self.path / f"{name}.json"
                original = file.read_bytes()
                value = json.loads(original)
                value["identity"]["client"] = "foreign"
                ledger.dump(file, value)
                # Reading this record would crash: preflight must return first.
                (self.path / "evidence.jsonl").write_text("FOREIGN_PRIVATE_RECORD")
                result = ledger.validate(self.path, self.identity, TODAY)
                self.assertEqual(result["structural_check"], "fail")
                self.assertIn("not read", result["limits"])
                self.assertNotIn("FOREIGN_PRIVATE_RECORD", json.dumps(result))
                file.write_bytes(original)

    def test_whitespace_ids_are_not_valid_identifiers(self):
        self.evidence["id"] = "   "
        self.write_rows("evidence", [self.evidence])
        self.assertEqual(self.check()["structural_check"], "fail")

    def test_cli_errors_are_structured_without_tracebacks(self):
        for contents in ("{", "[]", "null", "\ufeff{}", "NaN", '{"bad":1}'):
            with self.subTest(contents=contents):
                target = Path(self.tmp.name) / "invalid.json"
                target.write_text(contents, encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, str(SCRIPTS / "opportunity_math.py"), str(target)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stderr, "")
                self.assertIn("error", json.loads(result.stdout))

    def test_seeded_dependency_graphs_do_not_launder_invalid_basis(self):
        rng = random.Random(61005)
        for n in range(300):
            with self.subTest(case=n):
                depth = rng.randint(1, 35)
                mode = rng.choice(
                    ("current", "historical", "unverified", "conflicted", "expired", "fixture")
                )
                evidence = copy.deepcopy(self.evidence)
                if mode in ("historical", "unverified", "conflicted"):
                    evidence["status"] = mode
                elif mode == "expired":
                    evidence["valid_until"] = "2026-10-04"
                elif mode == "fixture":
                    evidence["source"] = "fixture://test"
                claims = []
                for index in range(depth):
                    claims.append(
                        {
                            **self.claim,
                            "id": f"C{index}",
                            "premises": [f"C{index - 1}"] if index else [],
                        }
                    )
                self.write_rows("evidence", [evidence])
                self.write_rows("claims", claims)
                self.context["facts"] = [claims[-1]["id"]]
                result = self.check()
                self.assertEqual(
                    result["structural_check"], "pass" if mode == "current" else "fail"
                )

    def test_invalid_metadata_matrix_does_not_crash(self):
        bad = (None, True, 7, [], {}, "   ")
        fields = (
            "source",
            "region",
            "source_kind",
            "origin_group",
            "locator",
            "excerpt",
            "status",
            "acquired_at",
        )
        for field in fields:
            for value in bad:
                with self.subTest(field=field, value=value):
                    row = {**self.evidence, field: value}
                    self.write_rows("evidence", [row])
                    self.assertEqual(self.check()["structural_check"], "fail")

    def test_validation_is_read_only(self):
        self.write_rows("evidence", [self.evidence])
        self.write_rows("claims", [self.claim])
        before = {p.name: p.read_bytes() for p in self.path.iterdir()}
        ledger.validate(self.path, self.identity, TODAY)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.path.iterdir()})


class ReleaseMathTests(unittest.TestCase):
    def test_seeded_decimal_oracle_and_permutation_invariance(self):
        rng = random.Random(61105)
        for n in range(1200):
            with self.subTest(case=n):
                data = dict(
                    scope="synthetic",
                    period="month",
                    output_unit="test units",
                    formula="product of factors",
                    assumptions=["synthetic values"],
                    factors=[],
                )
                for index in range(rng.randint(1, 8)):
                    bounds = sorted(
                        rng.randint(0, 100000) / 10 ** rng.randint(0, 4) for _ in range(3)
                    )
                    data["factors"].append(
                        dict(
                            name=str(index),
                            unit="synthetic",
                            hypothesis_id="H-test",
                            **dict(zip(("low", "base", "high"), bounds)),
                        )
                    )
                result = maths.calculate(data)
                with localcontext() as context:
                    context.prec = 1000
                    expected = {
                        key: float(math.prod(Decimal.from_float(f[key]) for f in data["factors"]))
                        for key in ("low", "base", "high")
                    }
                self.assertEqual(result["bounds"], expected)
                self.assertTrue(result["scenario_only"])
                rng.shuffle(data["factors"])
                self.assertEqual(maths.calculate(data)["bounds"], expected)
                for changed in result["sensitivity"]:
                    variant = copy.deepcopy(data)
                    for bound in ("low", "high"):
                        for factor in variant["factors"]:
                            base = next(
                                f["base"] for f in data["factors"] if f["name"] == factor["name"]
                            )
                            chosen = (
                                next(
                                    f[bound] for f in data["factors"] if f["name"] == factor["name"]
                                )
                                if factor["name"] == changed["factor"]
                                else base
                            )
                            factor.update(low=chosen, base=chosen, high=chosen)
                        self.assertEqual(maths.calculate(variant)["bounds"]["base"], changed[bound])

    def test_unrepresentable_final_result_is_rejected(self):
        for value, count in ((1e308, 2), (1e-308, 2)):
            with self.subTest(value=value):
                data = dict(
                    scope="synthetic",
                    period="month",
                    output_unit="test",
                    formula="product",
                    assumptions=["synthetic"],
                    factors=[
                        dict(
                            name=str(i),
                            unit="test",
                            hypothesis_id="H",
                            low=value,
                            base=value,
                            high=value,
                        )
                        for i in range(count)
                    ],
                )
                with self.assertRaises((ValueError, OverflowError)):
                    maths.calculate(data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
