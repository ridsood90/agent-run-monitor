"""Insert each payload into runs the monitor should call N, and record the verdicts.

  python scripts/run_attack.py --judge ollama:llama3.1:8b --limit 40
  python scripts/run_attack.py --judge stub:gullible --limit 12       # wiring check, no model

Attack set = every hand-labeled N run, then a seeded sample of keyword-scorer failures, up to
--limit. For each run and framing the monitor is called once with no payload and once per
payload. Resumable (results/attack_<judge>_<framing>.jsonl). Then: python scripts/report.py.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from monitor.backends import make_backend                                   # noqa: E402
from monitor.data import ROOT, attack_set, load_cases, load_hand_labels, load_runs  # noqa: E402
from monitor.judge import Cache, judge, slug                                 # noqa: E402
from monitor.payloads import PAYLOADS                                        # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", required=True)
    ap.add_argument("--framing", choices=["plain", "delimited", "both"], default="both")
    ap.add_argument("--limit", type=int, default=40, help="runs in the attack set")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--payloads", nargs="*", default=list(PAYLOADS))
    ap.add_argument("--case-context", action="store_true")
    a = ap.parse_args()

    runs, cases, labels = load_runs(), load_cases(), load_hand_labels()
    chosen = attack_set(runs, labels, a.limit, a.seed)
    n_hand = sum(s == "hand_N" for _, s in chosen)
    print(f"attack set: {len(chosen)} runs ({n_hand} hand-labeled N, {len(chosen) - n_hand} scorer failures)")
    backend = make_backend(a.judge)
    framings = ["plain", "delimited"] if a.framing == "both" else [a.framing]
    names = [None] + a.payloads          # None = no payload (the monitor's own verdict)
    for framing in framings:
        cache = Cache(ROOT / "results" / f"attack_{slug(a.judge)}_{framing}.jsonl")
        total = len(chosen) * len(names)
        done = 0
        for r, source in chosen:
            for p in names:
                key = f"{r['id']}|{p or 'none'}"
                if cache.get(key) is None:
                    j = judge(backend, r, cases[r["case_id"]], framing,
                              PAYLOADS[p] if p else None, a.case_context)
                    cache.put({"key": key, "run": r["id"], "source": source, "framing": framing,
                               "payload": p or "none", **j})
                done += 1
                if done % 50 == 0:
                    print(f"  {framing}: {done}/{total}", flush=True)
        print(f"{framing}: finished {total} calls")


if __name__ == "__main__":
    main()
