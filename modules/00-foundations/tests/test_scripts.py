import importlib.util
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


check_release_tag = _load("check_release_tag")
new_module = _load("new_module")


@pytest.fixture
def fake_repo(tmp_path):
    (tmp_path / "modules" / "00-foundations").mkdir(parents=True)
    shutil.copytree(ROOT / "modules" / "_template", tmp_path / "modules" / "_template")
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## foundations-v1.0 — 2026-11-20\n\n- First release\n", encoding="utf-8"
    )
    return tmp_path


def test_valid_tag(fake_repo):
    assert check_release_tag.check("foundations-v1.0", fake_repo) == []


@pytest.mark.parametrize(
    "tag", ["foundations-1.0", "foundations-v1", "Foundations-v1.0", "foundations-v01.0", "v1.0"]
)
def test_bad_tag_format(fake_repo, tag):
    assert check_release_tag.check(tag, fake_repo)


def test_tag_needs_module_folder(fake_repo):
    (fake_repo / "CHANGELOG.md").write_text("## ingestion-v1.0 — 2026-12-01\n", encoding="utf-8")
    problems = check_release_tag.check("ingestion-v1.0", fake_repo)
    assert any("No module folder" in p for p in problems)


def test_tag_needs_changelog_entry(fake_repo):
    problems = check_release_tag.check("foundations-v1.1", fake_repo)
    assert any("CHANGELOG" in p for p in problems)


def test_new_module_from_template(fake_repo):
    target = new_module.create("01", "ingestion", fake_repo)
    assert (target / "spec.md").read_text(encoding="utf-8").startswith("# Module 1 — ingestion")
    assert (target / "contract" / "README.md").exists()
    assert (target / "src" / "ingestion" / "__init__.py").exists()
    assert "import ingestion" in (target / "tests" / "test_module.py").read_text(encoding="utf-8")


def test_new_module_refuses_duplicates(fake_repo):
    with pytest.raises(FileExistsError):
        new_module.create("00", "other", fake_repo)
    with pytest.raises(ValueError):
        new_module.create("1", "x", fake_repo)


smoke_test = _load("smoke_test")


def test_smoke_check_passes():
    payload = {"status": "ok", "env": "live", "version": "foundations-v1.0", "commit": "abc1234"}
    assert smoke_test.check(payload, "live", "foundations-v1.0") == []


def test_smoke_check_catches_wrong_env_and_version():
    payload = {"status": "ok", "env": "staging", "version": "unreleased", "commit": "abc1234"}
    problems = smoke_test.check(payload, "live", "foundations-v1.0")
    assert len(problems) == 2
