"""Behavioral invariants of deterministic helpers, not market-quality tests."""

import copy
import datetime as dt
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/global-gtm-strategy-skill"


def module(name):
    spec = importlib.util.spec_from_file_location(name, SKILL / "scripts" / f"{name}.py")
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


state = module("research_state")
maths = module("opportunity_math")


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = Path(self.tmp.name) / "project"
        self.identity = {
            "client": "example-client",
            "product": "example-product",
            "project": "example-project",
        }
        state.initialize(self.p, self.identity)
        self.rows = json.loads((SKILL / "templates/records.json").read_text())

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, rows):
        (self.p / (name + ".jsonl")).write_text("".join(json.dumps(r) + "\n" for r in rows))

    def check(self):
        return state.validate(self.p, self.identity, dt.date(2026, 10, 4))

    def populated(self):
        self.write("evidence", [self.rows["evidence"]])
        self.write(
            "claims", [self.rows[k] for k in ("observation", "hypothesis", "recommendation")]
        )
        self.write("decisions", [self.rows["decision"]])

    def test_existing_init_never_overwrites(self):
        original = (self.p / "context.json").read_bytes()
        with self.assertRaises(ValueError):
            state.initialize(self.p, self.identity)
        self.assertEqual(original, (self.p / "context.json").read_bytes())

    def test_wrong_project_rejected(self):
        result = state.validate(self.p, {**self.identity, "project": "other"}, dt.date(2026, 10, 4))
        self.assertTrue(result["errors"])

    def test_identity_preflight_does_not_read_foreign_records(self):
        (self.p / "context.json").write_text("INVALID PRIVATE DATA")
        r = state.validate(self.p, {**self.identity, "client": "foreign"}, dt.date(2026, 10, 4))
        self.assertIn("not read", r["limits"])

    def test_reposts_warn_shared_origin(self):
        self.populated()
        e = copy.deepcopy(self.rows["evidence"])
        e["id"] = "E2"
        self.write("evidence", [self.rows["evidence"], e])
        self.assertTrue(any("shared origin" in w for w in self.check()["warnings"]))

    def test_symlink_directory_and_file_rejected(self):
        link = Path(self.tmp.name) / "linked"
        link.symlink_to(self.p, target_is_directory=True)
        with self.assertRaises(ValueError):
            state.safe_directory(link)
        (self.p / "evidence.jsonl").unlink()
        (self.p / "evidence.jsonl").symlink_to(self.p / "context.json")
        with self.assertRaises(ValueError):
            state.safe_directory(self.p)

    def test_no_business_data_inside_skill(self):
        with self.assertRaises(ValueError):
            state.safe_directory(SKILL / "business-data")

    def test_valid_chain_warns_unverified_source(self):
        self.populated()
        r = self.check()
        self.assertFalse(r["errors"])
        self.assertTrue(r["warnings"])

    def test_unknown_source_and_duplicate_id_rejected(self):
        self.populated()
        c = copy.deepcopy(self.rows["observation"])
        c["sources"] = ["E-missing"]
        self.write("claims", [c, c])
        self.assertTrue(self.check()["errors"])

    def test_forward_reference_and_cycles_rejected(self):
        self.populated()
        c = copy.deepcopy(self.rows["observation"])
        c["premises"] = ["C3"]
        self.write("claims", [c, self.rows["recommendation"]])
        self.assertTrue(self.check()["errors"])

    def test_hypothesis_cannot_promote_to_shared_fact(self):
        self.populated()
        ctx = json.loads((self.p / "context.json").read_text())
        ctx["facts"] = ["C2"]
        state.dump(self.p / "context.json", ctx)
        self.assertTrue(self.check()["errors"])

    def test_unverified_observation_cannot_be_shared_fact(self):
        self.populated()
        ctx = json.loads((self.p / "context.json").read_text())
        ctx["facts"] = ["C1"]
        state.dump(self.p / "context.json", ctx)
        self.assertTrue(self.check()["errors"])
        ctx["facts"] = []
        ctx["observations"] = ["C1"]
        state.dump(self.p / "context.json", ctx)
        self.assertFalse(self.check()["errors"])

    def test_verified_observation_scope_can_be_shared(self):
        self.populated()
        e = copy.deepcopy(self.rows["evidence"])
        e["status"] = "current"
        self.write("evidence", [e])
        c = copy.deepcopy(self.rows["observation"])
        c["verification"] = {
            "method": "direct document check",
            "checked_at": "2026-10-04",
            "scope": "document states restriction only",
        }
        self.write("claims", [c, self.rows["hypothesis"], self.rows["recommendation"]])
        ctx = json.loads((self.p / "context.json").read_text())
        ctx["facts"] = ["C1"]
        state.dump(self.p / "context.json", ctx)
        self.assertFalse(self.check()["errors"])

    def test_expired_evidence_cannot_be_shared_fact(self):
        self.populated()
        e = copy.deepcopy(self.rows["evidence"])
        e.update(status="current", valid_until="2026-09-01")
        self.write("evidence", [e])
        c = copy.deepcopy(self.rows["observation"])
        c["verification"] = {
            "method": "source read",
            "checked_at": "2026-10-04",
            "scope": "current price",
        }
        self.write("claims", [c, self.rows["hypothesis"], self.rows["recommendation"]])
        ctx = json.loads((self.p / "context.json").read_text())
        ctx["facts"] = ["C1"]
        state.dump(self.p / "context.json", ctx)
        self.assertTrue(self.check()["errors"])

    def test_invalid_verification_date_rejected(self):
        self.populated()
        e = copy.deepcopy(self.rows["evidence"])
        e["status"] = "current"
        self.write("evidence", [e])
        c = copy.deepcopy(self.rows["observation"])
        c["verification"] = {
            "method": "source read",
            "checked_at": "tomorrow",
            "scope": "source statement",
        }
        self.write("claims", [c, self.rows["hypothesis"], self.rows["recommendation"]])
        ctx = json.loads((self.p / "context.json").read_text())
        ctx["facts"] = ["C1"]
        state.dump(self.p / "context.json", ctx)
        self.assertTrue(self.check()["errors"])

    def test_expired_price_warning_and_future_date_rejected(self):
        self.populated()
        e = copy.deepcopy(self.rows["evidence"])
        e["status"] = "current"
        e["valid_until"] = "2026-09-01"
        self.write("evidence", [e])
        self.assertTrue(self.check()["warnings"])
        e["acquired_at"] = "2027-01-01"
        self.write("evidence", [e])
        self.assertTrue(self.check()["errors"])

    def test_complete_requires_decision(self):
        r = state.validate(self.p, self.identity, dt.date(2026, 10, 4), complete=True)
        self.assertTrue(r["errors"])

    def test_decision_revision_preserves_prior_and_requires_earlier(self):
        self.populated()
        d = copy.deepcopy(self.rows["decision"])
        d.update(id="D2", supersedes="D1")
        self.write("decisions", [self.rows["decision"], d])
        self.assertFalse(self.check()["errors"])
        self.write("decisions", [d, self.rows["decision"]])
        self.assertTrue(self.check()["errors"])

    def verified_fact(self):
        self.populated()
        e = copy.deepcopy(self.rows["evidence"])
        e["status"] = "current"
        c = copy.deepcopy(self.rows["observation"])
        c["verification"] = {
            "method": "document read",
            "checked_at": "2026-10-04",
            "scope": "document statement",
        }
        self.write("evidence", [e])
        self.write("claims", [c, self.rows["hypothesis"], self.rows["recommendation"]])
        ctx = json.loads((self.p / "context.json").read_text())
        ctx["facts"] = ["C1"]
        state.dump(self.p / "context.json", ctx)
        return e, c, ctx

    def test_superseded_fact_rejected_history_preserved(self):
        e, c, ctx = self.verified_fact()
        replacement = copy.deepcopy(c)
        replacement.update(id="C4", supersedes="C1", text="corrected observation")
        self.write("claims", [c, self.rows["hypothesis"], self.rows["recommendation"], replacement])
        self.assertTrue(any("superseded claim" in x for x in self.check()["errors"]))
        ctx["facts"] = ["C4"]
        state.dump(self.p / "context.json", ctx)
        self.assertFalse(self.check()["errors"])
        self.assertEqual(len((self.p / "claims.jsonl").read_text().splitlines()), 4)

    def test_superseded_source_requires_new_fact_basis(self):
        e, c, ctx = self.verified_fact()
        replacement = copy.deepcopy(e)
        replacement.update(id="E2", supersedes="E1")
        self.write("evidence", [e, replacement])
        self.assertTrue(any("superseded evidence" in x for x in self.check()["errors"]))
        fresh = copy.deepcopy(c)
        fresh.update(id="C4", sources=["E2"], supersedes="C1")
        self.write("claims", [c, self.rows["hypothesis"], self.rows["recommendation"], fresh])
        ctx["facts"] = ["C4"]
        state.dump(self.p / "context.json", ctx)
        self.assertFalse(self.check()["errors"])

    def test_hypothesis_not_observation(self):
        self.populated()
        ctx = json.loads((self.p / "context.json").read_text())
        ctx["observations"] = ["C2"]
        state.dump(self.p / "context.json", ctx)
        self.assertTrue(any("context.observations" in x for x in self.check()["errors"]))

    def test_superseded_premise_not_current_fact(self):
        e, c, ctx = self.verified_fact()
        new = copy.deepcopy(c)
        new.update(id="C4", supersedes="C1")
        dependent = copy.deepcopy(c)
        dependent.update(id="C5", premises=["C1"])
        self.write(
            "claims", [c, self.rows["hypothesis"], self.rows["recommendation"], new, dependent]
        )
        ctx["facts"] = ["C5"]
        state.dump(self.p / "context.json", ctx)
        self.assertTrue(any("superseded claim" in x for x in self.check()["errors"]))

    def test_readiness_never_inferred_from_structure(self):
        self.populated()
        d = copy.deepcopy(self.rows["decision"])
        d["next_validation"] = {
            k: "TBD"
            for k in ("object", "action", "observable", "criterion", "resource_limit", "branches")
        }
        self.write("decisions", [d])
        result = self.check()
        self.assertEqual(result["execution_readiness"], "not_assessed")

    def test_active_decision_warns_transitive_expired_basis(self):
        self.populated()
        r = self.check()
        self.assertTrue(any("active decision D1" in w for w in r["warnings"]))
        # The decision refers to C3, whose earlier premises include C1/E1.
        self.assertTrue(any("active decision D1" in w and "E1" in w for w in r["warnings"]))

    def test_active_decision_warns_replaced_evidence(self):
        self.populated()
        e = copy.deepcopy(self.rows["evidence"])
        e["status"] = "current"
        new = copy.deepcopy(e)
        new.update(id="E2", supersedes="E1")
        self.write("evidence", [e, new])
        self.assertTrue(
            any("active decision D1" in w and "E1" in w for w in self.check()["warnings"])
        )

    def test_inactive_decision_not_flagged_as_current(self):
        self.populated()
        fresh = copy.deepcopy(self.rows["decision"])
        fresh.update(id="D2", claims=["C2"], supersedes="D1")
        self.write("decisions", [self.rows["decision"], fresh])
        self.assertFalse(any("active decision D1" in w for w in self.check()["warnings"]))
        self.assertFalse(any("active decision D2" in w for w in self.check()["warnings"]))


class MathTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((SKILL / "templates/sizing-input.json").read_text())

    def test_units_and_envelope_and_sensitivity(self):
        r = maths.calculate(self.data)
        self.assertEqual(r["bounds"], {"low": 1000, "base": 2250, "high": 4000})
        self.assertEqual(
            r["sensitivity"][0], {"factor": "reachable-accounts", "low": 1500, "high": 3000}
        )
        self.assertTrue(r["scenario_only"])

    def test_invalid_bounds_and_no_basis_rejected(self):
        for value in (-1, float("nan"), True):
            d = copy.deepcopy(self.data)
            d["factors"][0]["low"] = value
            with self.assertRaises(ValueError):
                maths.calculate(d)
        d = copy.deepcopy(self.data)
        del d["factors"][0]["hypothesis_id"]
        with self.assertRaises(ValueError):
            maths.calculate(d)

    def test_zero_factor_sensitivity_without_dividing_by_zero(self):
        d = copy.deepcopy(self.data)
        d["factors"][0].update(low=0, base=0, high=2)
        r = maths.calculate(d)
        self.assertEqual(r["bounds"]["base"], 0)
        self.assertEqual(r["sensitivity"][0]["high"], 300)


if __name__ == "__main__":
    unittest.main(verbosity=2)
