#!/usr/bin/env python3
"""Nonnegative interval multiplication and one-driver sensitivity; not a market forecast."""

import argparse
import json
import math
import sys
from fractions import Fraction
from pathlib import Path


def calculate(data):
    """Multiply nonnegative bounds exactly and vary one factor at a time."""

    def text(value):
        return isinstance(value, str) and bool(value.strip())

    def text_list(value, allow_empty=False):
        return (
            isinstance(value, list) and (allow_empty or bool(value)) and all(text(v) for v in value)
        )

    if not isinstance(data, dict):
        raise ValueError("input must be an object")
    factors = data["factors"]
    if not isinstance(factors, list) or not factors:
        raise ValueError("factors must be a nonempty list")
    names = set()
    for f in factors:
        if not isinstance(f, dict):
            raise ValueError("each factor must be an object")
        if not isinstance(f.get("name"), str) or not f["name"].strip() or f["name"] in names:
            raise ValueError("factor names must be nonempty and unique")
        names.add(f["name"])
        for key in ("low", "base", "high"):
            if (
                isinstance(f[key], bool)
                or not isinstance(f[key], (float, int))
                or not math.isfinite(f[key])
            ):
                raise ValueError("finite numeric bounds required")
        if not 0 <= f["low"] <= f["base"] <= f["high"]:
            raise ValueError("require 0 <= low <= base <= high")
        if not text(f.get("unit")) or not (f.get("source_ids") or f.get("hypothesis_id")):
            raise ValueError("each factor needs unit and source_ids or hypothesis_id")
        if "source_ids" in f and not text_list(f["source_ids"], allow_empty=True):
            raise ValueError("source_ids must be a list of IDs")
        if "hypothesis_id" in f and not text(f["hypothesis_id"]):
            raise ValueError("hypothesis_id must be nonempty text")
    for key in ("scope", "period", "output_unit", "formula"):
        if not text(data.get(key)):
            raise ValueError(f"{key} must be nonempty text")
    if not text_list(data.get("assumptions")):
        raise ValueError("assumptions must be a nonempty list of text")

    def product(values):
        # Exact intermediate products avoid overflow/underflow before a cancelling
        # small/large factor or zero. Only the final finite float is returned.
        exact = math.prod(Fraction(v) for v in values)
        result = float(exact)
        if not math.isfinite(result):
            raise ValueError("result overflow")
        if result == 0 and exact:
            raise ValueError("result underflow; rescale units")
        return result

    bounds = {k: product(f[k] for f in factors) for k in ("low", "base", "high")}
    sensitivity = []
    for i, f in enumerate(factors):
        sensitivity.append(
            {
                "factor": f["name"],
                **{
                    key: product(v[key] if j == i else v["base"] for j, v in enumerate(factors))
                    for key in ("low", "high")
                },
            }
        )
    return {
        "scope": data["scope"],
        "period": data["period"],
        "unit": data["output_unit"],
        "formula": data["formula"],
        "bounds": bounds,
        "sensitivity": sensitivity,
        "scenario_only": any(f.get("hypothesis_id") for f in factors),
        "limits": "Endpoint envelope, not confidence interval. Check evidence, unit cancellation, dependencies and feasibility manually.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", help="JSON input; see templates/sizing-input.json")
    a = p.parse_args()
    try:
        print(
            json.dumps(
                calculate(json.loads(Path(a.input).read_text(encoding="utf-8"))),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except (ValueError, OSError, KeyError, TypeError, OverflowError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
