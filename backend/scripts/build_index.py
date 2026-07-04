from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ingest import write_index  # noqa: E402

if __name__ == "__main__":
    meta = write_index()
    print("index built:")
    print(json.dumps(meta, indent=2))
