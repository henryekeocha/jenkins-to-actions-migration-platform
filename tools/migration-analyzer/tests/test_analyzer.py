from migration_analyzer import Category, analyze, analyze_text


def _rules(report):
    return {f.rule for f in report.findings}


def test_legacy_jenkinsfile_end_to_end(legacy_jenkinsfile):
    report = analyze(legacy_jenkinsfile)

    assert report.stages == [
        "Checkout",
        "Build",
        "Test",
        "Unit",
        "Lint",
        "SAST",
        "Image",
        "Deploy staging",
        "Approve production",
        "Deploy production",
    ]
    assert report.shared_library == "platform-shared"
    assert report.shared_library_steps == ["deployHelm", "smokeTest"]
    assert set(report.credential_ids) == {
        "sonarqube-token",
        "aws-deployer",
        "ghcr-push",
    }

    rules = _rules(report)
    for expected in [
        "shared-library",
        "agent-docker",
        "docker-socket",
        "agent-label",
        "parallel",
        "input-gate",
        "submitter",
        "lock",
        "milestone",
        "cron-trigger",
        "pollscm-trigger",
        "stash",
        "archive-artifacts",
        "junit",
        "post-block",
        "post-unstable",
        "clean-ws",
        "plugin-slack",
        "plugin-email",
        "plugin-sonar",
        "with-credentials",
        "credentials-helper",
        "timeout",
        "disable-concurrent",
        "when-branch",
        "when-expression",
        "jenkins-env-var",
        "checkout-scm",
        "shared-library-step",
    ]:
        assert expected in rules, expected

    assert report.plugin_steps == [
        "ansiColor",
        "cleanWs",
        "emailext",
        "junit",
        "slackSend",
        "timestamps",
        "withSonarQubeEnv",
    ]

    # Every manual item in the guide's "needs a human decision" section shows up as MANUAL.
    manual = {f.rule for f in report.findings if f.category is Category.MANUAL}
    assert {
        "shared-library",
        "docker-socket",
        "input-gate",
        "milestone",
        "shared-library-step",
    } <= manual


def test_findings_are_sorted_by_line():
    report = analyze_text("pipeline {\n stages {\n stage('B') {}\n stage('A') {}\n }\n}")
    lines = [f.line for f in report.findings]
    assert lines == sorted(lines)


def test_once_rules_report_a_single_finding():
    src = "@Library('a') _\n@Library('b') _\npipeline { post { always { } } post { } }"
    report = analyze_text(src)
    assert sum(1 for f in report.findings if f.rule == "shared-library") == 1
    assert sum(1 for f in report.findings if f.rule == "post-block") == 1


def test_stage_names_are_captured_as_detail():
    report = analyze_text("stage('Deploy prod') { }")
    (f,) = [f for f in report.findings if f.rule == "stage"]
    assert f.detail == "Deploy prod"
    assert f.category is Category.AUTO


def test_local_def_is_not_a_library_step():
    src = "def helper(x) { return x }\nnode { helper(1) }"
    report = analyze_text(src)
    assert report.shared_library_steps == []


def test_credentials_helper_detail_and_category():
    report = analyze_text("environment { T = credentials('my-token') }")
    (f,) = [f for f in report.findings if f.rule == "credentials-helper"]
    assert f.detail == "my-token"
    assert f.category is Category.REVIEW
    assert report.credential_ids == ["my-token"]


def test_cron_hash_syntax_flagged_for_review():
    report = analyze_text("triggers { cron('H 2 * * 1-5') }")
    (f,) = [f for f in report.findings if f.rule == "cron-trigger"]
    assert f.detail == "H 2 * * 1-5"
    assert "H" in f.note


def test_summary_counts():
    report = analyze_text("options { timestamps() }\nsteps { input message: 'go?' }")
    assert report.summary["drop"] == 1
    assert report.summary["manual"] == 1
    assert report.summary["auto"] == 0
