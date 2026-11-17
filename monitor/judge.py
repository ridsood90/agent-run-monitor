"""One monitor call, plus a resumable jsonl cache so a long run can be stopped and restarted."""
import json
import re
from pathlib import Path

from .framing import build_messages

_VERDICT = re.compile(r"VERDICT:\s*([YN])\b", re.I)


def parse_verdict(text):
    found = _VERDICT.findall(text or "")
    return found[-1].upper() if found else "UNPARSED"   # last one wins: the format asks for it last


def judge(backend, run, case, framing, payload_text=None, case_context=False):
    system, user, _ = build_messages(run, case, framing, payload_text, case_context)
    raw = backend.chat(system, user)
    if raw is None:
        return {"verdict": "ERROR", "raw": None}
    return {"verdict": parse_verdict(raw), "raw": raw[:400]}


class Cache:
    """Append-only jsonl keyed by a string. Re-running skips keys already judged,
    except ERROR records, which are tried again."""

    def __init__(self, path):
        self.path = Path(path)
        self.rows = {}
        if self.path.exists():
            with open(self.path) as f:
                for line in f:
                    if line.strip():
                        row = json.loads(line)
                        self.rows[row["key"]] = row

    def get(self, key):
        row = self.rows.get(key)
        return row if row and row["verdict"] != "ERROR" else None

    def put(self, row):
        self.rows[row["key"]] = row
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a") as f:
            f.write(json.dumps(row) + "\n")


def slug(spec):
    return re.sub(r"[^A-Za-z0-9.-]+", "_", spec)
