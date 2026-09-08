#!/usr/bin/env python3
"""Convert CustomResourceDefinitions into JSON schemas that kubeconform can use.

Reads CRDs from local files or URLs (multi-document YAML is fine; non-CRD documents are
ignored) and writes one strict JSON schema per served version to
<out-dir>/<kind-lowercase>_<group>_<version>.json. Point kubeconform at it with:

    kubeconform -schema-location '<out-dir>/{{.ResourceKind}}_{{.Group}}_{{.ResourceAPIVersion}}.json'

"Strict" means objects that declare properties reject unknown keys, unless the CRD marks them
with x-kubernetes-preserve-unknown-fields. This is a small, dependency-free replacement for
kubeconform's openapi2jsonschema.py, which mis-handles a property literally named
"properties" (as Tekton's ParamSpec has).

Usage: hack/crd-schemas.py OUT_DIR SOURCE...
Requires: pyyaml.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import yaml


def load(source: str) -> str:
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source, timeout=60) as resp:  # noqa: S310
            return resp.read().decode()
    return Path(source).read_text()


def to_json_schema(node):
    if isinstance(node, list):
        return [to_json_schema(n) for n in node]
    if not isinstance(node, dict):
        return node
    out = {}
    preserve = node.get("x-kubernetes-preserve-unknown-fields", False)
    for key, value in node.items():
        if key.startswith("x-kubernetes-"):
            continue
        if key == "properties" and isinstance(value, dict):
            out[key] = {name: to_json_schema(sub) for name, sub in value.items()}
        elif key in ("items", "additionalProperties", "not") and isinstance(value, dict):
            out[key] = to_json_schema(value)
        elif key in ("allOf", "anyOf", "oneOf") and isinstance(value, list):
            out[key] = [to_json_schema(v) for v in value]
        else:
            out[key] = value
    if node.get("x-kubernetes-int-or-string"):
        out.pop("type", None)
        out["oneOf"] = [{"type": "string"}, {"type": "integer"}]
    if out.get("type") == "object" and "properties" in out and "additionalProperties" not in out and not preserve:
        out["additionalProperties"] = False
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    out_dir = Path(argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for source in argv[2:]:
        for doc in yaml.safe_load_all(load(source)):
            if not isinstance(doc, dict) or doc.get("kind") != "CustomResourceDefinition":
                continue
            spec = doc["spec"]
            group, kind = spec["group"], spec["names"]["kind"]
            for version in spec.get("versions", []):
                schema = version.get("schema", {}).get("openAPIV3Schema")
                if not schema:
                    continue
                js = to_json_schema(schema)
                # The API server validates metadata itself and ignores the CRD's metadata schema
                # beyond name/generateName, so do not let a strict conversion reject namespace etc.
                if isinstance(js.get("properties", {}).get("metadata"), dict):
                    js["properties"]["metadata"] = {"type": "object"}
                js["$schema"] = "http://json-schema.org/draft-07/schema#"
                path = out_dir / f"{kind.lower()}_{group}_{version['name']}.json"
                path.write_text(json.dumps(js))
                written += 1
    print(f"wrote {written} schema(s) to {out_dir}")
    return 0 if written else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
