"""Create a new module folder from the template.

Usage: python scripts/new_module.py <NN> <slug>
Example: python scripts/new_module.py 01 ingestion
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def create(number: str, slug: str, root: Path = ROOT) -> Path:
    if not re.fullmatch(r"\d{2}", number):
        raise ValueError("Module number must be two digits, e.g. 01")
    if not re.fullmatch(r"[a-z][a-z0-9-]*[a-z0-9]", slug):
        raise ValueError("Slug must be lower case letters, digits and hyphens, e.g. ingestion")
    modules = root / "modules"
    for existing in modules.iterdir():
        if existing.name.startswith(f"{number}-") or existing.name.endswith(f"-{slug}"):
            raise FileExistsError(f"{existing.name} already uses that number or slug")
    target = modules / f"{number}-{slug}"
    shutil.copytree(modules / "_template", target)
    package = slug.replace("-", "_")
    (target / "src" / package).mkdir()
    (target / "src" / package / "__init__.py").write_text(
        f'"""Module {int(number)} — {slug}."""\n', encoding="utf-8"
    )
    test = target / "tests" / "test_module.py"
    test.write_text(test.read_text(encoding="utf-8").replace("PACKAGE", package), encoding="utf-8")
    spec = target / "spec.md"
    spec.write_text(
        spec.read_text(encoding="utf-8")
        .replace("Module N", f"Module {int(number)}")
        .replace("<name>", slug),
        encoding="utf-8",
    )
    return target


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    target = create(argv[1], argv[2])
    print(f"Created {target.relative_to(ROOT)}. Fill in spec.md first (stage 1).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
