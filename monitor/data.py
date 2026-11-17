"""Load stored agent runs, cases and hand labels from agentic-ai-lab."""
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# tag -> result file (same four runs as agentic-ai-lab: 2 models x validator on/off)
FILES = {
    "qwen_on": "results_validate_results_true",
    "qwen_off": "results_validate_results_false",
    "mistral_on": "results_mistral-latest_validate_results_true",
    "mistral_off": "results_mistral-latest_validate_results_false",
}


def load_cases(root=ROOT):
    return {c["id"]: c for c in json.load(open(Path(root) / "data" / "cases.json"))}


def load_runs(root=ROOT):
    """All scored, non-baseline, non-ERROR runs. Each run gets a 'tag' and an 'id'."""
    out = []
    for tag, name in FILES.items():
        path = Path(root) / "data" / "results" / f"{name}.json"
        for r in json.load(open(path))["results"]:
            if r["status"] == "ERROR" or r["category"] == "baseline" or r["report_pass"] is None:
                continue
            run = dict(r)
            run["tag"] = tag
            run["id"] = f"{tag}|{r['case_id']}|{r['repetition']}"
            out.append(run)
    return out


def load_hand_labels(root=ROOT):
    """{run id: 'Y'|'N'} from the two hand-check samples ('?' labels are dropped)."""
    labels = {}
    for d in ("handcheck", "handcheck_strat"):
        p = Path(root) / "data" / "handlabels" / d
        key = {k["n"]: k for k in json.load(open(p / "key.json"))}
        for line in open(p / "labels.txt"):
            parts = line.split()
            if len(parts) == 2 and parts[1] in ("Y", "N"):
                k = key[int(parts[0])]
                labels[f"{k['file']}|{k['case']}|{k['rep']}"] = parts[1]
    return labels


def attack_set(runs, labels, limit=40, seed=1):
    """Runs the payloads are inserted into: every hand-labeled N run first (ground truth),
    then a seeded random sample of runs the keyword scorer failed, up to `limit` in total.
    Returns [(run, source)] with source 'hand_N' or 'scorer_fail'."""
    hand_n = [r for r in runs if labels.get(r["id"]) == "N"]
    rest = [r for r in runs if r["report_pass"] is False and labels.get(r["id"]) != "N"]
    rng = random.Random(seed)
    rng.shuffle(rest)
    take = max(0, limit - len(hand_n))
    return [(r, "hand_N") for r in hand_n] + [(r, "scorer_fail") for r in rest[:take]]
