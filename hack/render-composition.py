#!/usr/bin/env python3
"""Approximate what a Composition would compose for a given XR, for offline schema validation.

This is NOT `crossplane composition render`, which runs the real functions in Docker. It handles
only what the compositions in this repo use from function-patch-and-transform: `base` objects,
`PatchSet`, `FromCompositeFieldPath` and `CombineFromComposite` patches, and the `map` and
`string`/Format transforms. ToCompositeFieldPath patches are ignored (they flow the other way).
The output is one document per composed resource, named and namespaced from the XR, suitable for
kubeconform against the provider CRD schemas from hack/crd-schemas.py.

Usage: hack/render-composition.py COMPOSITION.yaml XR.yaml > composed.yaml
Requires: pyyaml.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

_SEG = re.compile(r"([^.\[\]]+)|\[([^\]]+)\]")


def _segments(path: str) -> list[str | int]:
    out: list[str | int] = []
    for name, bracket in _SEG.findall(path):
        if name:
            out.append(name)
        elif bracket.isdigit():
            out.append(int(bracket))
        else:
            out.append(bracket)
    return out


def get_path(obj, path: str):
    cur = obj
    for seg in _segments(path):
        if isinstance(seg, int):
            if not isinstance(cur, list) or seg >= len(cur):
                return None
            cur = cur[seg]
        else:
            if not isinstance(cur, dict) or seg not in cur:
                return None
            cur = cur[seg]
    return cur


def set_path(obj, path: str, value) -> None:
    segs = _segments(path)
    cur = obj
    for i, seg in enumerate(segs):
        last = i == len(segs) - 1
        nxt = segs[i + 1] if not last else None
        if isinstance(seg, int):
            while len(cur) <= seg:
                cur.append({} if isinstance(nxt, str) else [])
            if last:
                cur[seg] = value
            else:
                cur = cur[seg]
        else:
            if last:
                cur[seg] = value
            else:
                if seg not in cur or cur[seg] is None:
                    cur[seg] = [] if isinstance(nxt, int) else {}
                cur = cur[seg]


_VERB = re.compile(r"%(?:\[(\d+)\])?([sdv])")


def go_format(fmt: str, values: tuple) -> str:
    """Subset of Go's fmt.Sprintf: %s/%d/%v with optional explicit indexes like %[1]s."""
    state = {"next": 0}

    def sub(m: re.Match[str]) -> str:
        if m.group(1):
            idx = int(m.group(1)) - 1
            state["next"] = idx + 1
        else:
            idx = state["next"]
            state["next"] += 1
        return str(values[idx])

    return _VERB.sub(sub, fmt.replace("%%", "\x00")).replace("\x00", "%")


def transform(value, transforms: list[dict]):
    for t in transforms or []:
        kind = t.get("type")
        if kind == "map":
            value = t["map"].get(str(value).lower() if isinstance(value, bool) else str(value), value)
        elif kind == "string" and t["string"].get("type", "Format") == "Format":
            value = go_format(t["string"]["fmt"], (value,))
        else:
            raise SystemExit(f"unsupported transform {t}")
    return value


def apply_patches(xr: dict, target: dict, patches: list[dict], patch_sets: dict[str, list[dict]]) -> None:
    for p in patches or []:
        ptype = p.get("type", "FromCompositeFieldPath")
        if ptype == "PatchSet":
            apply_patches(xr, target, patch_sets[p["patchSetName"]], patch_sets)
        elif ptype == "FromCompositeFieldPath":
            value = get_path(xr, p["fromFieldPath"])
            if value is None:
                continue  # Optional/Required policies both leave the field alone until it exists
            set_path(target, p["toFieldPath"], transform(value, p.get("transforms")))
        elif ptype == "CombineFromComposite":
            values = [get_path(xr, v["fromFieldPath"]) for v in p["combine"]["variables"]]
            if any(v is None for v in values):
                continue
            set_path(target, p["toFieldPath"], go_format(p["combine"]["string"]["fmt"], tuple(values)))
        elif ptype == "ToCompositeFieldPath":
            continue
        else:
            raise SystemExit(f"unsupported patch type {ptype}")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    composition = yaml.safe_load(Path(argv[1]).read_text())
    xr = yaml.safe_load(Path(argv[2]).read_text())
    docs = []
    for step in composition["spec"]["pipeline"]:
        inp = step.get("input") or {}
        if inp.get("kind") != "Resources":
            continue
        patch_sets = {ps["name"]: ps["patches"] for ps in inp.get("patchSets", [])}
        for res in inp["resources"]:
            obj = yaml.safe_load(yaml.safe_dump(res["base"]))
            obj.setdefault("metadata", {})
            obj["metadata"]["name"] = f"{xr['metadata']['name']}-{res['name']}"
            if xr["metadata"].get("namespace"):
                obj["metadata"]["namespace"] = xr["metadata"]["namespace"]
            apply_patches(xr, obj, res.get("patches"), patch_sets)
            docs.append(obj)
    sys.stdout.write(yaml.safe_dump_all(docs, sort_keys=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
