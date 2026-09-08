from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LEGACY_JENKINSFILE = REPO_ROOT / "legacy" / "jenkins" / "Jenkinsfile"


@pytest.fixture
def legacy_jenkinsfile() -> Path:
    assert LEGACY_JENKINSFILE.is_file(), LEGACY_JENKINSFILE
    return LEGACY_JENKINSFILE
