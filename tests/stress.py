"""Reproducible boundary probes; failures are findings, not model benchmarks."""

import copy
import datetime
import importlib.util
import json
import math
import random
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run(scripts, output):
    state = module(scripts / "research_state.py")
    calc = module(scripts / "opportunity_math.py")
    results = []

    def record(name, expected, actual, detail=None):
        results.append(
            dict(
                case=name,
                expected=expected,
                actual=actual,
                passed=expected == actual,
                detail=detail,
            )
        )

    template = json.loads(
        (ROOT / "skills/global-gtm-strategy/templates/sizing-input.json").read_text()
    )
    rng = random.Random(1031)
    for i in range(120):
        data = copy.deepcopy(template)
        data["factors"] = []
        for j in range(rng.randint(1, 6)):
            bounds = sorted(rng.sample(range(0, 100), 3))
            data["factors"].append(
                dict(
                    name=str(j),
                    unit="dimensionless",
                    low=bounds[0],
                    base=bounds[1],
                    high=bounds[2],
                    hypothesis_id="H" + str(j),
                )
            )
        actual = calc.calculate(data)
        expected = {k: math.prod(f[k] for f in data["factors"]) for k in ("low", "base", "high")}
        expected_s = [
            dict(
                factor=f["name"],
                low=f["low"]
                * math.prod(v["base"] for j, v in enumerate(data["factors"]) if i != j),
                high=f["high"]
                * math.prod(v["base"] for j, v in enumerate(data["factors"]) if i != j),
            )
            for i, f in enumerate(data["factors"])
        ]
        record(
            "arithmetic-" + str(i),
            True,
            actual["bounds"] == expected and actual["sensitivity"] == expected_s,
        )
    invalids = [
        None,
        [],
        42,
        "bad",
        {},
        {"factors": [None]},
        {"factors": [42]},
        {"factors": ["bad"]},
        {"factors": {"name": "bad"}},
        {"factors": True},
    ]
    for i, value in enumerate(invalids):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "input.json"
            p.write_text(json.dumps(value))
            proc = subprocess.run(
                [sys.executable, str(scripts / "opportunity_math.py"), str(p)],
                capture_output=True,
                text=True,
            )
            try:
                structured = (
                    isinstance(json.loads(proc.stdout), dict)
                    and proc.returncode == 1
                    and not proc.stderr
                )
            except ValueError:
                structured = False
            record(
                "invalid-cli-" + str(i),
                True,
                structured,
                dict(input=value, stdout=proc.stdout, stderr=proc.stderr),
            )
    ident = dict(client="stress", product="ledger", project="test")

    def probe(name, mutations, expected):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "ledger"
            state.initialize(p, ident)
            ctx = json.loads((p / "context.json").read_text())
            ctx.update(goal="choose", product="synthetic")
            ev = [
                dict(
                    identity=ident,
                    id="E1",
                    source="https://example.com/current",
                    acquired_at="2026-10-04",
                    material_date="2026-10-04",
                    region="US",
                    source_kind="original",
                    origin_group="one",
                    locator="test",
                    excerpt="synthetic",
                    limits=["synthetic"],
                    status="current",
                ),
                dict(
                    identity=ident,
                    id="E2",
                    source="https://example.com/old",
                    acquired_at="2026-10-04",
                    material_date="2020-01-01",
                    region="US",
                    source_kind="original",
                    origin_group="two",
                    locator="test",
                    excerpt="synthetic",
                    limits=["synthetic"],
                    status="historical",
                ),
            ]
            claims = [
                dict(
                    identity=ident,
                    id="O1",
                    category="observation",
                    text="old observation",
                    sources=["E2"],
                    premises=[],
                ),
                dict(
                    identity=ident,
                    id="O2",
                    category="observation",
                    text="purported current fact",
                    sources=["E1"],
                    premises=["O1"],
                    verification=dict(method="review", checked_at="2026-10-04", scope="test"),
                ),
            ]
            ctx["facts"] = ["O2"]
            decisions = []
            mutations(ctx, ev, claims, decisions)
            (p / "context.json").write_text(json.dumps(ctx))
            for fname, rows in [("evidence", ev), ("claims", claims), ("decisions", decisions)]:
                (p / (fname + ".jsonl")).write_text("".join(json.dumps(r) + "\n" for r in rows))
            try:
                report = state.validate(p, ident, datetime.date(2026, 10, 5))
                actual = report["structural_check"]
            except Exception as exc:
                actual = "crash"
                report = dict(error=repr(exc))
            record(
                name,
                expected,
                actual,
                dict(report=report, context=ctx, evidence=ev, claims=claims, decisions=decisions),
            )

    probe("historical-premise-into-fact", lambda *x: None, "fail")
    for status in ["unverified", "conflicted"]:
        probe(
            status + "-premise-into-fact",
            lambda c, e, q, d, s=status: e[1].update(status=s),
            "fail",
        )
    probe(
        "expired-premise-into-fact",
        lambda c, e, q, d: e[1].update(status="current", valid_until="2026-10-01"),
        "fail",
    )
    probe(
        "fixture-premise-into-fact",
        lambda c, e, q, d: e[1].update(status="current", source="fixture://synthetic"),
        "fail",
    )
    probe(
        "hypothesis-premise-into-fact",
        lambda c, e, q, d: q[0].update(category="hypothesis", validation="test", sources=[]),
        "fail",
    )
    probe("clean-observation-into-fact", lambda c, e, q, d: q[1].update(premises=[]), "pass")
    probe(
        "verified-before-acquisition",
        lambda c, e, q, d: q[1].update(
            premises=[], verification=dict(method="review", checked_at="2020-01-01", scope="test")
        ),
        "fail",
    )
    probe(
        "nonstring-claim-text",
        lambda c, e, q, d: q[1].update(premises=[], text={"fake": "text"}),
        "fail",
    )
    for depth in range(1, 21):
        for mode in ["historical", "expired", "fixture", "hypothesis", "clean"]:

            def chain(c, e, q, d, n=depth, m=mode):
                if m == "expired":
                    e[1].update(status="current", valid_until="2026-10-01")
                if m == "fixture":
                    e[1].update(status="current", source="fixture://synthetic")
                if m == "clean":
                    e[1].update(status="current")
                if m == "hypothesis":
                    q[0].update(category="hypothesis", sources=[], validation="pending")
                q[1]["premises"] = []
                for k in range(n):
                    q.append(
                        dict(
                            identity=ident,
                            id="CHAIN" + str(k),
                            category="observation",
                            text="synthetic derived observation",
                            sources=["E1"],
                            premises=["O1" if k == 0 else "CHAIN" + str(k - 1)],
                        )
                    )
                q[1]["premises"] = ["CHAIN" + str(n - 1)]
                # Move the leaf after its dependencies, preserving acyclic ledger order.
                q.append(q.pop(1))

            probe(
                "dependency-depth-" + str(depth) + "-" + mode,
                chain,
                "pass" if mode == "clean" else "fail",
            )
    # A completed ledger must reject invalid field types rather than merely truthy values.
    fields = {
        "sources": ["bad", {}, 7],
        "premises": ["bad", {}, 7],
        "text": [True, 7, [], {}],
        "category": [[], {}, "unknown"],
        "supersedes": [[], {}, "missing"],
    }
    for field, values in fields.items():
        for i, value in enumerate(values):
            probe(
                "claim-shape-" + field + "-" + str(i),
                lambda c, e, q, d, f=field, v=value: q[1].update({"premises": [], f: v}),
                "fail",
            )
    for field in ["facts", "observations", "assumptions"]:
        for i, value in enumerate([None, 7, {}, "O2"]):
            probe(
                "context-shape-" + field + "-" + str(i),
                lambda c, e, q, d, f=field, v=value: (q[1].update(premises=[]), c.update(**{f: v})),
                "fail",
            )
    for field in ["acquired_at", "material_date", "valid_until", "status", "limits"]:
        values = [7, {}, []] if field != "limits" else [None, 7, {}]
        for i, value in enumerate(values):
            probe(
                "evidence-shape-" + field + "-" + str(i),
                lambda c, e, q, d, f=field, v=value: (
                    q[1].update(premises=[]),
                    e[0].update(**{f: v}),
                ),
                "fail",
            )
    header = dict(
        total=len(results),
        passed=sum(r["passed"] for r in results),
        failed=sum(not r["passed"] for r in results),
    )
    output.write_text(
        json.dumps(header, ensure_ascii=False)[:-1]
        + ', "results": [\n'
        + ",\n".join(json.dumps(r, ensure_ascii=False) for r in results)
        + "\n]}\n"
    )
    print(
        json.dumps(
            dict(
                total=len(results),
                passed=sum(r["passed"] for r in results),
                failures=[r["case"] for r in results if not r["passed"]],
            ),
            ensure_ascii=False,
        )
    )
    return int(any(not r["passed"] for r in results))


if __name__ == "__main__":
    sys.exit(run(Path(sys.argv[1]), Path(sys.argv[2])))
