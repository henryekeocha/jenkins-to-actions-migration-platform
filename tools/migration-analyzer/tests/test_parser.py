from migration_analyzer.parser import scan, strip_comments


def test_strip_comments_preserves_line_count():
    src = "a\n/* multi\nline */ b\nc // trailing\n// whole line\nd"
    out = strip_comments(src)
    assert out.count("\n") == src.count("\n")
    assert "multi" not in out
    assert "trailing" not in out
    assert "whole line" not in out
    assert "d" in out.split("\n")[-1]


def test_strip_comments_keeps_urls():
    out = strip_comments("sh 'curl https://example.com/x' // note")
    assert "https://example.com/x" in out
    assert "note" not in out


def test_scan_extracts_structure():
    src = """
    @Library('platform-shared@main') _
    pipeline {
      environment { TOKEN = credentials('sonar-token') }
      stages {
        stage('Build') { steps { sh 'make' } }
        stage('Deploy') {
          steps {
            withCredentials([file(credentialsId: 'kubeconfig-prod', variable: 'KC')]) {
              deployHelm(service: 'x')
            }
          }
        }
      }
    }
    """
    s = scan(src)
    assert s.stages == ["Build", "Deploy"]
    assert s.shared_library == "platform-shared"
    assert s.credential_ids == ["sonar-token", "kubeconfig-prod"]
    assert "deployHelm" in s.step_calls
    assert "sh" in s.step_calls


def test_scan_ignores_commented_out_constructs():
    s = scan("// stage('Ghost')\npipeline { stages { stage('Real') { steps { sh 'x' } } } }")
    assert s.stages == ["Real"]
