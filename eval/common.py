import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.getenv("AGENTIC_DATA", ROOT / "data"))


def load_jsonl(name):
    p = DATA / name
    rows = []
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    return rows


def append_jsonl(name, entry):
    DATA.mkdir(parents=True, exist_ok=True)
    with open(DATA / name, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
