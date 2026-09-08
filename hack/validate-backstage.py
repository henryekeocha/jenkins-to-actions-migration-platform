#!/usr/bin/env python3
"""Validate Backstage catalog entities and the software template against upstream JSON schemas.

Downloads the schema files from the backstage/backstage repository (pinned to a ref), registers
them by $id so cross-file $refs resolve, and validates every document in the given YAML files.
Skeleton files containing `${{ values.* }}` are rendered with placeholder values first, since the
template engine substitutes them before Backstage ever sees the file.

Usage: hack/validate-backstage.py [--ref master] backstage/catalog-info.yaml backstage/template/template.yaml ...
Requires: pyyaml, jsonschema (and referencing, a jsonschema dependency).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

import yaml
from jsonschema import Draft7Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

BASE = "https://raw.githubusercontent.com/backstage/backstage/{ref}/"
SCHEMAS = {
    "Entity": "packages/catalog-model/src/schema/Entity.schema.json",
    "EntityMeta": "packages/catalog-model/src/schema/EntityMeta.schema.json",
    "common": "packages/catalog-model/src/schema/shared/common.schema.json",
    "ComponentV1alpha1": "packages/catalog-model/src/schema/kinds/Component.v1alpha1.schema.json",
    "LocationV1alpha1": "packages/catalog-model/src/schema/kinds/Location.v1alpha1.schema.json",
    "TemplateV1beta3": "plugins/scaffolder-common/src/Template.v1beta3.schema.json",
}
KIND_TO_SCHEMA = {
    ("backstage.io/v1alpha1", "Component"): "ComponentV1alpha1",
    ("backstage.io/v1alpha1", "Location"): "LocationV1alpha1",
    ("scaffolder.backstage.io/v1beta3", "Template"): "TemplateV1beta3",
}
PLACEHOLDERS = {
    "name": "example-svc",
    "description": "Example service",
    "owner": "group:default/team-a",
    "destination.owner": "example-org",
    "destination.repo": "example-svc",
}
_TEMPLATE_EXPR = re.compile(r"\$\{\{\s*values\.([a-zA-Z0-9_.]+)\s*\}\}")


def fetch_schemas(ref: str, cache_dir: Path | None) -> Registry:
    registry = Registry()
    for sid, rel in SCHEMAS.items():
        cached = cache_dir / Path(rel).name if cache_dir else None
        if cached and cached.is_file():
            raw = cached.read_text()
        else:
            with urllib.request.urlopen(BASE.format(ref=ref) + rel, timeout=30) as resp:  # noqa: S310
                raw = resp.read().decode()
            if cached:
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_text(raw)
        doc = json.loads(raw)
        resource = Resource.from_contents(doc, default_specification=DRAFT7)
        registry = registry.with_resource(sid, resource)
        # Backstage refs use bare ids like "common#relation"; register the id form too.
        registry = registry.with_resource(doc.get("$id", sid), resource)
    return registry


def render_placeholders(text: str) -> str:
    return _TEMPLATE_EXPR.sub(lambda m: PLACEHOLDERS.get(m.group(1), "placeholder"), text)


def validate_file(path: Path, registry: Registry) -> int:
    errors = 0
    text = render_placeholders(path.read_text())
    for i, doc in enumerate(yaml.safe_load_all(text)):
        if not isinstance(doc, dict):
            continue
        key = (doc.get("apiVersion"), doc.get("kind"))
        schema_id = KIND_TO_SCHEMA.get(key)
        if schema_id is None:
            print(f"{path}[{i}]: no schema for {key}, skipped")
            continue
        schema = registry.contents(schema_id)
        validator = Draft7Validator(schema, registry=registry)
        found = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        if found:
            errors += len(found)
            for e in found:
                loc = "/".join(str(p) for p in e.path) or "<root>"
                print(f"{path}[{i}] {key[1]} {loc}: {e.message}")
        else:
            print(f"{path}[{i}]: {key[1]} valid")
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--ref", default="master", help="backstage/backstage git ref for the schemas")
    ap.add_argument("--cache-dir", type=Path, help="directory to cache downloaded schemas")
    args = ap.parse_args(argv)

    registry = fetch_schemas(args.ref, args.cache_dir)
    total = sum(validate_file(f, registry) for f in args.files)
    if total:
        print(f"{total} schema error(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
