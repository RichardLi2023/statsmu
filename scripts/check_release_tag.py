"""Check a release tag against the contract: <module slug>-v<major>.<minor>, a matching module
folder, and a CHANGELOG.md entry headed '## <tag> — YYYY-MM-DD'.

Usage: python scripts/check_release_tag.py <tag>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAG = re.compile(
    r"^(?P<slug>[a-z][a-z0-9-]*[a-z0-9])-v(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)$"
)


def module_slugs(root: Path = ROOT) -> set[str]:
    slugs = set()
    for folder in (root / "modules").iterdir():
        m = re.match(r"^\d{2}-(.+)$", folder.name)
        if folder.is_dir() and m:
            slugs.add(m.group(1))
    return slugs


def check(tag: str, root: Path = ROOT) -> list[str]:
    """Return a list of problems; empty means the tag is valid."""
    m = TAG.match(tag)
    if not m:
        return [f"Tag {tag!r} must look like <module>-v<major>.<minor>, e.g. ingestion-v1.0"]
    problems = []
    if m.group("slug") not in module_slugs(root):
        problems.append(f"No module folder modules/NN-{m.group('slug')}/ for tag {tag!r}")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    heading = re.compile(rf"^## {re.escape(tag)} — \d{{4}}-\d{{2}}-\d{{2}}\s*$", re.MULTILINE)
    if not heading.search(changelog):
        problems.append(f"CHANGELOG.md has no entry headed '## {tag} — YYYY-MM-DD'")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    problems = check(argv[1])
    for p in problems:
        print(f"::error::{p}")
    if not problems:
        print(f"Release tag {argv[1]} is valid.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
