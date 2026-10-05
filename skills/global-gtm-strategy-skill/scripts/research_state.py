#!/usr/bin/env python3
"""Initialize/check one isolated research ledger. No network or semantic validation."""

import argparse
import datetime as dt
import json
from pathlib import Path
import re
import sys

FILES = (
    "identity.json",
    "context.json",
    "state.json",
    "evidence.jsonl",
    "claims.jsonl",
    "decisions.jsonl",
    "handoff.md",
)
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
CATEGORIES = {"observation", "inference", "hypothesis", "recommendation"}


def date(value):
    """Parse a ledger date without accepting numeric or missing values."""
    return dt.date.fromisoformat(value)


def safe_directory(path):
    """Reject skill-local business data, traversal and symlink components."""
    # Do not resolve() first: that would hide symlink components.
    if ".." in Path(path).parts:
        raise ValueError("parent traversal rejected; provide a direct project path")
    path = Path(path).absolute()
    skill_root = Path(__file__).resolve().parents[1]
    if path == skill_root or skill_root in path.parents:
        raise ValueError("business data must be outside the skill package")
    for p in (path, *path.parents):
        if p.is_symlink():
            raise ValueError(f"symlink directory rejected: {p}")
    for name in FILES:
        if (path / name).is_symlink():
            raise ValueError(f"symlink file rejected: {name}")
    return path


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def initialize(path, identity):
    """Create an empty isolated ledger; never overwrite an existing directory."""
    if path.exists():
        raise ValueError("init requires a new directory; existing data is never overwritten")
    path.mkdir(parents=True)
    dump(path / "identity.json", {"schema_version": 1, "identity": identity})
    dump(
        path / "context.json",
        {
            "identity": identity,
            "goal": "",
            "product": "",
            "constraints": {},
            "facts": [],
            "observations": [],
            "assumptions": [],
            "user_statements": [],
        },
    )
    dump(
        path / "state.json",
        {
            "identity": identity,
            "phase": "intake",
            "completed": [],
            "next_action": "read authorized product context",
            "open_questions": [],
            "budget": {},
            "consumption": {},
            "inputs_digest": {},
            "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
    )
    for name in ("evidence.jsonl", "claims.jsonl", "decisions.jsonl"):
        (path / name).write_text("", encoding="utf-8")
    (path / "handoff.md").write_text(
        "尚未形成决策。身份：" + json.dumps(identity, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def validate(path, identity, today, complete=False):
    """Check schema and provenance references; never infer semantic validity."""
    errors, warnings = [], []

    def check(condition, message):
        if not condition:
            errors.append(message)

    def text(value, allow_empty=False):
        return isinstance(value, str) and (bool(value.strip()) or (allow_empty and value == ""))

    def text_list(value):
        return isinstance(value, list) and all(text(item) for item in value)

    def required(obj, keys, label):
        check(isinstance(obj, dict), f"{label}: expected object")
        if not isinstance(obj, dict):
            return False
        for key in keys:
            check(key in obj, f"{label}: missing {key}")
        check(obj.get("identity") == identity, f"{label}: identity mismatch")
        return all(key in obj for key in keys)

    def load(name):
        p = path / name
        if not p.is_file():
            raise ValueError(f"missing file: {name}")
        if name.endswith(".jsonl"):
            return [
                json.loads(line)
                for line in p.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        return json.loads(p.read_text(encoding="utf-8"))

    config = load("identity.json")
    if not isinstance(config, dict):
        raise ValueError("identity must be an object")
    required(config, ("identity", "schema_version"), "identity")
    check(
        type(config.get("schema_version")) is int and config["schema_version"] == 1,
        "unsupported schema version",
    )
    if errors:
        return {
            "structural_check": "fail",
            "errors": errors,
            "warnings": [],
            "limits": "Identity preflight failed; business records were not read.",
        }
    documents = {}
    for name, fields in (
        (
            "context",
            (
                "identity",
                "goal",
                "product",
                "constraints",
                "facts",
                "assumptions",
                "user_statements",
            ),
        ),
        (
            "state",
            (
                "identity",
                "phase",
                "completed",
                "next_action",
                "open_questions",
                "budget",
                "consumption",
                "updated_at",
                "inputs_digest",
            ),
        ),
    ):
        documents[name] = load(name + ".json")
        required(documents[name], fields, name)
        if errors:
            return {
                "structural_check": "fail",
                "errors": errors,
                "warnings": [],
                "limits": "Project preflight failed; subsequent business records were not read.",
            }
    context, state = documents["context"], documents["state"]
    for field in ("goal", "product"):
        check(text(context.get(field), allow_empty=True), f"context: {field} must be text")
    check(isinstance(context.get("constraints"), dict), "context: constraints must be object")
    check(isinstance(context.get("user_statements"), list), "context: user_statements must be list")
    for field in ("phase", "next_action"):
        check(text(state.get(field)), f"state: {field} must be nonempty text")
    for field in ("completed", "open_questions"):
        check(text_list(state.get(field)), f"state: {field} must be list of text")
    for field in ("budget", "consumption", "inputs_digest"):
        check(isinstance(state.get(field), dict), f"state: {field} must be object")
    try:
        dt.datetime.fromisoformat(state.get("updated_at", ""))
    except (ValueError, TypeError):
        errors.append("state: invalid updated_at")
    records = {name: load(name + ".jsonl") for name in ("evidence", "claims", "decisions")}
    indices, seen = {}, set()
    for kind, rows in records.items():
        indices[kind] = {}
        for n, row in enumerate(rows, 1):
            if not required(row, ("id", "identity"), f"{kind}:{n}"):
                continue
            rid = row["id"]
            check(text(rid), f"{kind}:{n}: invalid id")
            if not isinstance(rid, str):
                continue
            check(rid not in seen, f"duplicate id: {rid}")
            seen.add(rid)
            indices[kind][rid] = row
    evidence, claims, decisions = (indices[x] for x in ("evidence", "claims", "decisions"))

    def refs(row, field, index, label):
        values = row.get(field, [])
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
            errors.append(f"{label}: {field} must be list of IDs")
            return []
        for value in values:
            check(value in index, f"{label}: unknown {field} {value}")
        return values

    def supersession(index, label):
        prior = set()
        for rid, row in index.items():
            previous = row.get("supersedes")
            if previous is not None:
                check(
                    isinstance(previous, str) and previous in prior,
                    f"{rid}: supersedes must reference an earlier {label}",
                )
            prior.add(rid)

    supersession(evidence, "evidence")
    supersession(claims, "claim")
    supersession(decisions, "decision")
    replaced_evidence = {
        r.get("supersedes") for r in evidence.values() if isinstance(r.get("supersedes"), str)
    }
    replaced_claims = {
        r.get("supersedes") for r in claims.values() if isinstance(r.get("supersedes"), str)
    }
    replaced_decisions = {
        r.get("supersedes") for r in decisions.values() if isinstance(r.get("supersedes"), str)
    }
    groups = {}
    for rid, row in evidence.items():
        group = row.get("origin_group")
        if isinstance(group, str) and group:
            groups.setdefault(group, []).append(rid)
    for group, ids in groups.items():
        if len(ids) > 1:
            warnings.append(
                f"shared origin {group}: {ids}; do not count as independent corroboration"
            )
    stale = set()
    for rid, row in evidence.items():
        if not required(
            row,
            (
                "source",
                "acquired_at",
                "material_date",
                "region",
                "source_kind",
                "origin_group",
                "locator",
                "excerpt",
                "limits",
                "status",
            ),
            rid,
        ):
            continue
        check(
            isinstance(row["status"], str)
            and row["status"] in {"current", "historical", "unverified", "conflicted"},
            f"{rid}: invalid status",
        )
        for field in ("source", "region", "source_kind", "origin_group", "locator", "excerpt"):
            check(isinstance(row[field], str) and bool(row[field].strip()), f"{rid}: empty {field}")
        check(text_list(row["limits"]), f"{rid}: limits must be a list of text")
        try:
            check(date(row["acquired_at"]) <= today, f"{rid}: future acquired_at")
            if row["material_date"] is None:
                check(
                    text(row.get("material_date_unknown_reason")),
                    f"{rid}: unknown material date needs text reason",
                )
            else:
                check(
                    date(row["material_date"]) <= date(row["acquired_at"]),
                    f"{rid}: material_date after acquired_at",
                )
            if row.get("valid_until") is not None:
                if date(row["valid_until"]) < today:
                    stale.add(rid)
        except (TypeError, ValueError):
            errors.append(f"{rid}: invalid date")
        if row["status"] != "current":
            stale.add(rid)
    prior = set()
    for rid, row in claims.items():
        if not required(row, ("category", "text", "sources", "premises"), rid):
            prior.add(rid)
            continue
        check(
            isinstance(row["category"], str) and row["category"] in CATEGORIES,
            f"{rid}: invalid category",
        )
        sources = refs(row, "sources", evidence, rid)
        premises = refs(row, "premises", claims, rid)
        check(all(p in prior for p in premises), f"{rid}: premises must reference earlier claims")
        check(
            isinstance(row["text"], str) and bool(row["text"].strip()),
            f"{rid}: text must be a nonempty string",
        )
        if row["category"] == "observation":
            check(bool(sources), f"{rid}: observation needs sources")
        if isinstance(row["category"], str) and row["category"] in {"inference", "recommendation"}:
            check(bool(sources or premises), f"{rid}: needs explicit basis")
            check(text(row.get("reasoning")), f"{rid}: needs text reasoning")
        if row["category"] == "recommendation":
            check(bool(premises), f"{rid}: recommendation needs premises")
            check(
                text_list(row.get("withdraw_if")) and bool(row["withdraw_if"]),
                f"{rid}: recommendation needs withdrawal conditions as list of text",
            )
        if row["category"] == "hypothesis":
            check(text(row.get("validation")), f"{rid}: hypothesis needs text validation")
        if set(sources) & stale:
            warnings.append(
                f"{rid}: relies on non-current/expired evidence {sorted(set(sources) & stale)}"
            )
        prior.add(rid)
    for field, category in (
        ("facts", "observation"),
        ("observations", "observation"),
        ("assumptions", "hypothesis"),
    ):
        values = refs(context, field, claims, "context")
        for rid in values:
            if rid in claims:
                check(
                    claims[rid].get("category") == category,
                    f"context.{field}: {rid} is not {category}",
                )
    fact_ids = refs(context, "facts", claims, "context")
    for rid in fact_ids:
        if rid not in claims:
            continue
        claim = claims[rid]
        # Preserve historical rows, but never propagate a superseded basis as a current fact.
        pending, visited = [rid], set()
        fact_sources = set()
        while pending:
            basis_id = pending.pop()
            if basis_id in visited or basis_id not in claims:
                continue
            visited.add(basis_id)
            check(
                basis_id not in replaced_claims,
                f"context.facts: {rid} depends on superseded claim {basis_id}; reverify current basis",
            )
            basis = claims[basis_id]
            check(
                basis.get("category") == "observation",
                f"context.facts: {rid} depends on non-observation {basis_id}; keep it outside verified facts",
            )
            basis_sources = basis.get("sources", [])
            basis_premises = basis.get("premises", [])
            if isinstance(basis_sources, list):
                for eid in basis_sources:
                    if isinstance(eid, str):
                        fact_sources.add(eid)
                        check(
                            eid not in replaced_evidence,
                            f"context.facts: {rid} depends on superseded evidence {eid}; reverify current basis",
                        )
                        if eid in evidence:
                            e = evidence[eid]
                            check(
                                e.get("status") == "current"
                                and eid not in stale
                                and not str(e.get("source", "")).startswith("fixture://"),
                                f"context.facts: {rid} indirectly relies on unverified/historical/synthetic source {eid}",
                            )
            if isinstance(basis_premises, list):
                pending.extend(p for p in basis_premises if isinstance(p, str))
        verification = claim.get("verification", {})
        check(
            isinstance(verification, dict)
            and all(text(verification.get(k)) for k in ("method", "checked_at", "scope")),
            f"context.facts: {rid} needs explicit verification method/date/scope",
        )
        if isinstance(verification, dict) and verification.get("checked_at"):
            try:
                check(
                    date(verification["checked_at"]) <= today,
                    f"context.facts: {rid} verification date is in future",
                )
                for eid in sorted(fact_sources):
                    if eid in evidence:
                        check(
                            date(verification["checked_at"])
                            >= date(evidence[eid].get("acquired_at")),
                            f"context.facts: {rid} verification predates acquired source {eid}",
                        )
            except (ValueError, TypeError):
                errors.append(f"context.facts: {rid} invalid verification date")
        for eid in refs(claim, "sources", evidence, rid):
            if eid in evidence:
                e = evidence[eid]
                check(
                    e.get("status") == "current"
                    and eid not in stale
                    and not str(e.get("source", "")).startswith("fixture://"),
                    f"context.facts: {rid} relies on unverified/historical/synthetic source {eid}",
                )
    for rid, row in decisions.items():
        if not required(
            row,
            (
                "status",
                "claims",
                "counter_evidence",
                "counter_search",
                "unknowns",
                "withdraw_if",
                "next_validation",
            ),
            rid,
        ):
            continue
        check(
            isinstance(row["status"], str)
            and row["status"] in {"recommend", "provisional", "defer"},
            f"{rid}: invalid decision status",
        )
        refs(row, "claims", claims, rid)
        refs(row, "counter_evidence", evidence, rid)
        check(text(row["counter_search"], allow_empty=True), f"{rid}: counter_search must be text")
        check(text_list(row["unknowns"]), f"{rid}: unknowns must be list of text")
        check(text_list(row["withdraw_if"]), f"{rid}: withdraw_if must be list of text")
        check(bool(row["claims"]), f"{rid}: empty decision basis")
        check(
            bool(row["counter_evidence"] or row["counter_search"]),
            f"{rid}: counter search not recorded",
        )
        check(bool(row["withdraw_if"]), f"{rid}: no withdrawal condition")
        if row["status"] in {"provisional", "defer"}:
            check(bool(row["unknowns"]), f"{rid}: conditional/defer needs unknowns")
        task = row["next_validation"]
        check(isinstance(task, dict), f"{rid}: next_validation must be object")
        if isinstance(task, dict):
            for key in (
                "object",
                "action",
                "observable",
                "criterion",
                "resource_limit",
                "branches",
            ):
                check(text(task.get(key)), f"{rid}: next_validation needs nonempty text {key}")
        if rid not in replaced_decisions:
            pending = list(refs(row, "claims", claims, rid))
            visited = set()
            affected = set()
            while pending:
                basis_id = pending.pop()
                if basis_id in visited or basis_id not in claims:
                    continue
                visited.add(basis_id)
                if basis_id in replaced_claims:
                    affected.add(basis_id)
                basis = claims[basis_id]
                for eid in refs(basis, "sources", evidence, basis_id):
                    if eid in stale or eid in replaced_evidence:
                        affected.add(eid)
                pending.extend(refs(basis, "premises", claims, basis_id))
            if affected:
                warnings.append(
                    f"active decision {rid}: basis needs review {sorted(affected)}; historical/non-current sources are not automatically invalid, but do not resume this recommendation without checking their role"
                )
    if complete:
        check(bool(decisions), "complete: no decision")
        check(
            bool(context.get("goal") and context.get("product")), "complete: product/goal missing"
        )
        check(
            (path / "handoff.md").is_file()
            and bool((path / "handoff.md").read_text(encoding="utf-8").strip()),
            "complete: handoff missing or empty (not a quality check)",
        )
    else:
        if not decisions:
            warnings.append("initialized/incomplete: no decision; not a completed research run")
    return {
        "structural_check": "fail" if errors else "pass",
        "execution_readiness": "not_assessed",
        "errors": errors,
        "warnings": warnings,
        "limits": "Does not validate truth, independence, claim support or strategic quality.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("init", "validate"))
    p.add_argument("directory")
    for key in ("client", "product", "project"):
        p.add_argument("--" + key, required=True)
    p.add_argument("--today", default=dt.date.today().isoformat(), help="date for freshness checks")
    p.add_argument("--complete", action="store_true", help="require decision and handoff")
    a = p.parse_args()
    try:
        identity = {key: getattr(a, key) for key in ("client", "product", "project")}
        if not all(SLUG.fullmatch(v) for v in identity.values()):
            raise ValueError("identity IDs must be stable lowercase slugs, max 64 chars")
        path = safe_directory(a.directory)
        if a.command == "init":
            initialize(path, identity)
            print(json.dumps({"initialized": str(path), "identity": identity}, ensure_ascii=False))
            return 0
        result = validate(path, identity, date(a.today), a.complete)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return bool(result["errors"])
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"structural_check": "fail", "errors": [str(exc)]}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
