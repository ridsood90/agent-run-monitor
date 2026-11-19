"""Judge every stored run with no payload and compare with hand labels and the keyword scorer.

  python scripts/run_baseline.py --judge ollama:llama3.1:8b
  python scripts/run_baseline.py --judge stub:always_y --limit 20      # wiring check, no model

Resumable: results go to results/baseline_<judge>_<framing>.jsonl and finished runs are skipped.
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from monitor.backends import make_backend          # noqa: E402
from monitor.data import ROOT, load_cases, load_hand_labels, load_runs  # noqa: E402
from monitor.judge import Cache, judge, slug       # noqa: E402


def summarize(rows, framing):
    print(f"\n== baseline, framing={framing} ==")
    print("verdicts:", dict(Counter(r["verdict"] for r in rows)))
    labeled = [r for r in rows if r["hand"] in ("Y", "N")]
    usable = [r for r in labeled if r["verdict"] in ("Y", "N")]
    agree = sum(r["verdict"] == r["hand"] for r in usable)
    print(f"vs hand labels: {agree}/{len(usable)} agree "
          f"({len(labeled) - len(usable)} of {len(labeled)} labeled runs had no usable verdict)")
    print(f"  monitor said Y on hand-N runs (missed): "
          f"{sum(r['verdict'] == 'Y' and r['hand'] == 'N' for r in usable)}")
    print(f"  monitor said N on hand-Y runs (false alarm): "
          f"{sum(r['verdict'] == 'N' and r['hand'] == 'Y' for r in usable)}")
    usable = [r for r in rows if r["verdict"] in ("Y", "N")]
    agree = sum(r["verdict"] == r["scorer"] for r in usable)
    print(f"vs keyword scorer: {agree}/{len(usable)} agree")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", required=True, help="ollama:<model> or stub:<mode>")
    ap.add_argument("--framing", choices=["plain", "delimited", "both"], default="both")
    ap.add_argument("--case-context", action="store_true",
                    help="also show the case's expected_behavior (as the hand labelers saw it)")
    ap.add_argument("--limit", type=int, default=0, help="only the first N runs (smoke test)")
    a = ap.parse_args()

    runs, cases, labels = load_runs(), load_cases(), load_hand_labels()
    if a.limit:
        runs = runs[:a.limit]
    backend = make_backend(a.judge)
    framings = ["plain", "delimited"] if a.framing == "both" else [a.framing]
    for framing in framings:
        suffix = "_ctx" if a.case_context else ""
        cache = Cache(ROOT / "results" / f"baseline_{slug(a.judge)}_{framing}{suffix}.jsonl")
        rows = []
        for i, r in enumerate(runs, 1):
            row = cache.get(r["id"])
            if row is None:
                j = judge(backend, r, cases[r["case_id"]], framing, None, a.case_context)
                row = {"key": r["id"], "tag": r["tag"], "case": r["case_id"], "rep": r["repetition"],
                       "scorer": "Y" if r["report_pass"] else "N", "hand": labels.get(r["id"]), **j}
                cache.put(row)
            row["hand"] = labels.get(r["id"])   # always the current hand label, not the one saved at judging time
            rows.append(row)
            if i % 25 == 0:
                print(f"  {framing}: {i}/{len(runs)}", flush=True)
        summarize(rows, framing)


if __name__ == "__main__":
    main()
