"""Put every module's src/ folder on the import path, so new modules need no config change."""

import sys
from pathlib import Path

ROOT = Path(__file__).parent
for src in sorted(ROOT.glob("modules/*/src")):
    if src.parent.name != "_template" and str(src) not in sys.path:
        sys.path.insert(0, str(src))
