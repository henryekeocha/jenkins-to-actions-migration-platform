# migration-analyzer

Scans a Jenkinsfile and produces a checklist of everything that needs attention when moving the
pipeline to GitHub Actions. Stdlib only, Python 3.11+.

```
pip install -e tools/migration-analyzer
migration-analyzer legacy/jenkins/Jenkinsfile                # markdown checklist
migration-analyzer legacy/jenkins/Jenkinsfile -f json         # machine-readable
migration-analyzer legacy/jenkins/Jenkinsfile --fail-on manual  # exit 2 if any manual item
```

Or without installing: `PYTHONPATH=tools/migration-analyzer/src python -m migration_analyzer.cli <file>`.

## What it reports

Each finding has a category:

| Category | Meaning |
|---|---|
| `manual` | No GitHub Actions equivalent. Someone has to decide: `input` gates, `milestone`, docker socket mounts, shared-library classes. |
| `review` | An equivalent exists but needs something outside the workflow file: a secret, an environment, a marketplace action, or the semantics differ (`lock`, `junit`, `cron` with `H`). |
| `auto` | Mechanical mapping: `stage`, `parallel`, `stash`, `checkout scm`, `timeout`, Jenkins env vars. |
| `drop` | Jenkins plumbing with no purpose in Actions: `pollSCM`, `cleanWs`, `timestamps`, `buildDiscarder`. |

It also extracts the stage list, the shared library name and every step it appears to provide
(each one is a composite action to write), every credential ID (each one is a secret to create,
with a suggested name), and plugin steps in use.

## How it works

It is a rule table of regexes (`rules.py`) applied line by line after comments are stripped
(`parser.py`). That is a deliberate choice over a Groovy parser: the constructs that matter for
migration all have a distinctive keyword, and the output is a checklist for a person, not a
transpiled workflow. Known limitations:

- A construct split across lines in an unusual way can be missed; a keyword inside a string
  literal can produce a false positive.
- Shared-library step detection is "a call that is not a known step and not defined in this
  file", so an unusual plugin step will be reported as a library step. `KNOWN_STEPS` in
  `rules.py` is the list to extend.
- Scripted (non-declarative) pipelines are scanned with the same rules; results are less
  complete because so much more is arbitrary Groovy.

## Tests

```
cd tools/migration-analyzer && pip install -e '.[dev]' && pytest
```

The end-to-end test runs against `legacy/jenkins/Jenkinsfile` in this repo.
