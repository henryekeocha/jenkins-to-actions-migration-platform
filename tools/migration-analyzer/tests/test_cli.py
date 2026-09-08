import json

import pytest

from migration_analyzer.cli import main


def test_markdown_to_stdout(legacy_jenkinsfile, capsys):
    rc = main([str(legacy_jenkinsfile)])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.startswith("# Migration checklist:")
    assert "## Needs a decision" in out
    assert "## Secrets to create" in out
    assert "`GHCR_PUSH`" in out


def test_json_output(legacy_jenkinsfile, capsys):
    rc = main([str(legacy_jenkinsfile), "--format", "json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["shared_library"] == "platform-shared"
    assert data["summary"]["manual"] >= 5
    assert {"rule", "category", "line", "snippet", "title", "actions_equivalent"} <= set(
        data["findings"][0]
    )


def test_text_output(legacy_jenkinsfile, capsys):
    assert main([str(legacy_jenkinsfile), "-f", "text"]) == 0
    out = capsys.readouterr().out
    assert "input-gate" in out


def test_output_file(legacy_jenkinsfile, tmp_path):
    target = tmp_path / "checklist.md"
    assert main([str(legacy_jenkinsfile), "-o", str(target)]) == 0
    assert target.read_text().startswith("# Migration checklist:")


def test_stdin(capsys, monkeypatch):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("steps { input message: 'ok?' }"))
    assert main(["-", "-f", "text"]) == 0
    assert "input-gate" in capsys.readouterr().out


def test_fail_on_threshold(tmp_path):
    f = tmp_path / "Jenkinsfile"
    f.write_text("options { timestamps() }\nsteps { junit 'x.xml' }")
    assert main([str(f), "--fail-on", "manual", "-o", str(tmp_path / "o.md")]) == 0
    assert main([str(f), "--fail-on", "review", "-o", str(tmp_path / "o.md")]) == 2
    assert main([str(f), "--fail-on", "drop", "-o", str(tmp_path / "o.md")]) == 2


def test_missing_file(capsys):
    assert main(["/nonexistent/Jenkinsfile"]) == 1
    assert "no such file" in capsys.readouterr().err


def test_version(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert "migration-analyzer" in capsys.readouterr().out
