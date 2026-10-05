"""Reproducible helper boundary checks. These are not market judgments."""

import copy
import datetime as dt
import importlib.util
import json
import math
import random
import subprocess
import sys
import tempfile
from decimal import Decimal, localcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/global-gtm-strategy-skill"
SCRIPTS = Path(sys.argv[1]) if len(sys.argv) > 1 else SKILL / "scripts"
OUTPUT = (
    Path(sys.argv[2])
    if len(sys.argv) > 2
    else Path(tempfile.gettempdir()) / "gtm-expanded-results.json"
)


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ledger = load_module("research_state")
calc = load_module("opportunity_math").calculate
results = []


def test(id, group, run):
    try:
        run()
        results.append(dict(id=id, group=group, pass_check=True))
    except Exception as e:
        results.append(dict(id=id, group=group, pass_check=False, error=str(e)))


def ensure(condition, message):
    if not condition:
        raise AssertionError(message)


base = json.loads((SKILL / "templates/sizing-input.json").read_text())
rng = random.Random(20261005)
for n in range(400):
    data = copy.deepcopy(base)
    data["factors"] = []
    for i in range(rng.randint(1, 6)):
        vals = sorted(
            Decimal(rng.randint(0, 100000)) / Decimal(10 ** rng.randint(0, 4)) for _ in range(3)
        )
        data["factors"].append(
            dict(
                name=f"f{i}",
                unit="illustration",
                hypothesis_id="H-test",
                **dict(zip(("low", "base", "high"), map(float, vals))),
            )
        )

    def run(data=data):
        actual = calc(data)

        def product(values):
            with localcontext() as ctx:
                ctx.prec = 100
                out = Decimal(1)
                for v in values:
                    out *= Decimal(str(v))
                return float(out)

        for key in ("low", "base", "high"):
            ensure(
                math.isclose(
                    actual["bounds"][key],
                    product(f[key] for f in data["factors"]),
                    rel_tol=1e-12,
                    abs_tol=1e-14,
                ),
                "endpoint differs from Decimal oracle",
            )
        for i, row in enumerate(actual["sensitivity"]):
            for key in ("low", "high"):
                expected = product(
                    f[key] if j == i else f["base"] for j, f in enumerate(data["factors"])
                )
                ensure(
                    math.isclose(row[key], expected, rel_tol=1e-12, abs_tol=1e-14),
                    "sensitivity differs from Decimal oracle",
                )

    test(f"numeric-{n:03}", "numeric_decimal_oracle", run)
for name, vals, expected in [
    ("zero", [0, 1e200, 1e200], 0),
    ("balanced", [1e-200, 1e200, 1e200], 1e200),
    ("tiny", [1e200, 1e-200, 1e-200], 1e-200),
]:
    d = copy.deepcopy(base)
    d["factors"] = [
        dict(name=f"f{i}", unit="illustration", hypothesis_id="H-test", low=v, base=v, high=v)
        for i, v in enumerate(vals)
    ]

    def run(d=d, expected=expected):
        result = calc(d)
        ensure(
            math.isclose(result["bounds"]["base"], expected, rel_tol=1e-12, abs_tol=0),
            "order-dependent product",
        )
        ensure(
            all(
                math.isclose(x[k], expected, rel_tol=1e-12, abs_tol=0)
                for x in result["sensitivity"]
                for k in ("low", "high")
            ),
            "order-dependent sensitivity",
        )

    test("numeric-" + name, "numeric_extremes", run)
for field in (
    "scope",
    "period",
    "output_unit",
    "formula",
    "assumptions",
    "unit",
    "source_ids",
    "hypothesis_id",
):
    badvalues = [True, 42, {"x": "y"}, " "]
    if field in ("scope", "period", "output_unit", "formula", "unit", "hypothesis_id"):
        badvalues.append(["text"])
    if field == "source_ids":
        badvalues += [[""], [True], [" "]]
    if field == "assumptions":
        badvalues += [[""], [True], [" "]]
    for i, bad in enumerate(badvalues):
        d = copy.deepcopy(base)
        if field in ("unit", "source_ids", "hypothesis_id"):
            d["factors"][0].pop("hypothesis_id", None)
            d["factors"][0][field] = bad
            if field == "unit":
                d["factors"][0]["hypothesis_id"] = "H-test"
        else:
            d[field] = bad

        def run(d=d):
            try:
                calc(d)
            except (ValueError, TypeError, KeyError, OverflowError):
                return
            raise AssertionError("malformed metadata accepted")

        test(f"math-type-{field}-{i}", "math_metadata_types", run)
rows = json.loads((SKILL / "templates/records.json").read_text())
identity = rows["evidence"]["identity"]


def hypothesis_with_empty_source_list():
    data = copy.deepcopy(base)
    data["factors"][0]["source_ids"] = []
    ensure(calc(data)["scenario_only"], "hypothesis-only factor must remain a scenario")


test("math-hypothesis-empty-sources", "valid_optional_fields", hypothesis_with_empty_source_list)


def valid_files():
    e = copy.deepcopy(rows["evidence"])
    e["status"] = "current"
    c = copy.deepcopy(rows["observation"])
    c["verification"] = {
        "method": "read authorized source",
        "checked_at": "2026-10-05",
        "scope": "source statement only",
    }
    return {
        "evidence": [e],
        "claims": [c, copy.deepcopy(rows["hypothesis"]), copy.deepcopy(rows["recommendation"])],
        "decisions": [copy.deepcopy(rows["decision"])],
    }


mutations = [
    ("identity", "schema_version"),
    ("context", "goal"),
    ("context", "product"),
    ("context", "constraints"),
    ("state", "phase"),
    ("state", "next_action"),
    ("state", "budget"),
    ("state", "consumption"),
    ("state", "inputs_digest"),
    ("state", "completed"),
    ("state", "open_questions"),
    ("evidence", "material_date_unknown_reason"),
    ("evidence", "limits"),
    ("observation", "verification.method"),
    ("observation", "verification.scope"),
    ("hypothesis", "validation"),
    ("recommendation", "reasoning"),
    ("recommendation", "withdraw_if"),
    ("decision", "counter_search"),
    ("decision", "withdraw_if"),
    ("decision", "unknowns"),
] + [
    ("decision", "next_validation." + k)
    for k in ("object", "action", "observable", "criterion", "resource_limit", "branches")
]
for target, field in mutations:
    badvalues = [True, 42, {"x": "y"}, " "]
    if field in ("constraints", "budget", "consumption", "inputs_digest"):
        badvalues = [True, 42, [], " "]
    if target == "context" and field in ("goal", "product"):
        badvalues = [True, 42, {"x": "y"}, ["text"]]
    for i, bad in enumerate(badvalues):

        def run(target=target, field=field, bad=bad):
            with tempfile.TemporaryDirectory() as td:
                p = Path(td) / "project"
                ledger.initialize(p, identity)
                files = valid_files()
                ctx = json.loads((p / "context.json").read_text())
                ctx.update(goal="choose market", product="synthetic test", facts=["C1"])
                checkpoint = json.loads((p / "state.json").read_text())
                config = json.loads((p / "identity.json").read_text())
                obj = {
                    "identity": config,
                    "context": ctx,
                    "state": checkpoint,
                    "evidence": files["evidence"][0],
                    "observation": files["claims"][0],
                    "hypothesis": files["claims"][1],
                    "recommendation": files["claims"][2],
                    "decision": files["decisions"][0],
                }[target]
                parts = field.split(".")
                for part in parts[:-1]:
                    obj = obj[part]
                obj[parts[-1]] = bad
                for name, data in [("identity", config), ("context", ctx), ("state", checkpoint)]:
                    ledger.dump(p / (name + ".json"), data)
                for name, data in files.items():
                    (p / (name + ".jsonl")).write_text("".join(json.dumps(x) + "\n" for x in data))
                try:
                    result = ledger.validate(p, identity, dt.date(2026, 10, 5))
                except (ValueError, TypeError, KeyError):
                    return
                ensure(bool(result["errors"]), "malformed ledger field accepted")

        test(f"ledger-type-{target}-{field}-{i}", "ledger_metadata_types", run)
# Full CLI verifies controlled output on malformed JSON, UTF-8, and foreign identity.
for i, (filename, payload) in enumerate(
    [
        ("identity.json", b"{"),
        ("identity.json", b"[]"),
        ("identity.json", b"\xff"),
        ("context.json", b"{"),
        ("context.json", b"[]"),
        ("state.json", b"null"),
        ("evidence.jsonl", b"{\n"),
        ("claims.jsonl", b"42\n"),
        ("decisions.jsonl", b"false\n"),
    ]
):

    def run(filename=filename, payload=payload):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "project"
            ledger.initialize(p, identity)
            (p / filename).write_bytes(payload)
            args = [sys.executable, str(SCRIPTS / "research_state.py"), "validate", str(p)]
            for k, v in identity.items():
                args += ["--" + k, v]
            r = subprocess.run(args, capture_output=True, text=True)
            parsed = json.loads(r.stdout)
            ensure(
                r.returncode != 0 and parsed["structural_check"] == "fail" and not r.stderr,
                "CLI failed without controlled JSON",
            )

    test(f"cli-malformed-{i}", "cli_error_contract", run)
summary = {
    "total": len(results),
    "passed": sum(x["pass_check"] for x in results),
    "failed": sum(not x["pass_check"] for x in results),
    "groups": {
        g: {
            "total": sum(x["group"] == g for x in results),
            "failed": sum(x["group"] == g and not x["pass_check"] for x in results),
        }
        for g in sorted({x["group"] for x in results})
    },
}
OUTPUT.write_text(
    '{\n  "summary": '
    + json.dumps(summary, ensure_ascii=False)
    + ',\n  "cases": [\n'
    + ",\n".join("    " + json.dumps(row, ensure_ascii=False) for row in results)
    + "\n  ]\n}\n"
)
print(json.dumps(summary))
sys.exit(bool(summary["failed"]))
