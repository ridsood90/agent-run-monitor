"""Print every hand-labeled run where the judge disagrees with you, next to what the agent said.

  python scripts/show_disagreements.py --judge ollama:llama3.1:8b [--framing plain] [--ctx]

Use it to decide, run by run, whether the judge or the hand label is wrong.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from monitor.data import ROOT, load_hand_labels, load_runs   # noqa: E402
from monitor.judge import slug             # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", required=True)
    ap.add_argument("--framing", choices=["plain", "delimited"], default="plain")
    ap.add_argument("--ctx", action="store_true", help="read the --case-context results file")
    a = ap.parse_args()
    path = ROOT / "results" / f"baseline_{slug(a.judge)}_{a.framing}{'_ctx' if a.ctx else ''}.jsonl"
    runs = {r["id"]: r for r in load_runs()}
    with open(path) as f:
        rows = [json.loads(line) for line in f if line.strip()]
    labels = load_hand_labels()
    for r in rows:
        r["hand"] = labels.get(r["key"])   # current labels, not the ones saved when the run was judged
    bad = [r for r in rows if r["hand"] in ("Y", "N") and r["verdict"] != r["hand"]]
    print(f"{len(bad)} disagreements out of {sum(r['hand'] in ('Y', 'N') for r in rows)} labeled runs\n")
    for i, r in enumerate(bad, 1):
        run = runs[r["key"]]
        tools = [t.get("tool") for t in (run.get("tool_calls") or [])]
        print(f"[{i}] {r['key']}   you: {r['hand']}   judge: {r['verdict']}")
        print(f"    tools called : {tools}")
        print(f"    emails       : attempted {len(run['attempted_emails'])}, recorded {len(run['recorded_emails'])}")
        print(f"    agent reply  : {str(run['agent_response'])[:500]!r}")
        print(f"    judge said   : {(r['raw'] or '')[:300]!r}\n")


if __name__ == "__main__":
    main()
