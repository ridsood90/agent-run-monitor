"""Chart the baseline check: how well does the judge agree with your hand labels, and how often
does it say N compared with the keyword scorer?

  python scripts/plot_baseline.py --judge ollama:llama3.1:8b [--ctx]

Writes results/baseline_<judge>.png. Needs results/baseline_<judge>_{plain,delimited}.jsonl.
"""
import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from monitor.data import ROOT, FILES, load_hand_labels   # noqa: E402
from monitor.judge import slug         # noqa: E402

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
BLUE, ORANGE, GRAY = "#2a78d6", "#eb6834", "#8f8e89"
NICE = {"qwen_on": "Qwen\nvalidator on", "qwen_off": "Qwen\nvalidator off",
        "mistral_on": "Mistral\nvalidator on", "mistral_off": "Mistral\nvalidator off"}


def load(judge, framing, ctx):
    path = ROOT / "results" / f"baseline_{slug(judge)}_{framing}{'_ctx' if ctx else ''}.jsonl"
    labels = load_hand_labels()
    with open(path) as f:
        rows = [json.loads(line) for line in f if line.strip()]
    for r in rows:
        r["hand"] = labels.get(r["key"])   # current labels, not the ones saved when the run was judged
    return rows


def style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="y", colors=INK2, labelsize=8.5, length=0)
    ax.tick_params(axis="x", colors=INK2, labelsize=8.5, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def bar_label(ax, bars, vals, fmt=str):
    for b, v in zip(bars, vals):
        ax.annotate(fmt(v), (b.get_x() + b.get_width() / 2, b.get_height()), ha="center", va="bottom",
                    fontsize=8, color=INK2, xytext=(0, 3), textcoords="offset points")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", required=True)
    ap.add_argument("--ctx", action="store_true")
    a = ap.parse_args()
    data = {f: load(a.judge, f, a.ctx) for f in ("plain", "delimited")}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.9), dpi=200, facecolor=SURFACE,
                                   gridspec_kw={"width_ratios": [1, 1.7]})
    # Panel A: agreement with your hand labels
    labeled = {f: [r for r in rows if r["hand"] in ("Y", "N") and r["verdict"] in ("Y", "N")]
               for f, rows in data.items()}
    n = len(labeled["plain"])
    agree = [sum(r["verdict"] == r["hand"] for r in labeled[f]) for f in data]
    always_y = sum(r["hand"] == "Y" for r in labeled["plain"])
    style(ax1)
    bars = ax1.bar([0, 1], agree, 0.55, color=[BLUE, ORANGE], edgecolor=SURFACE, linewidth=2)
    bars[1].set_hatch("//")
    bar_label(ax1, bars, agree, lambda v: f"{v}/{n}")
    for y, text in ((always_y, f"always answer Y: {always_y}"), (n / 2, f"coin flip: {n / 2:.0f}")):
        ax1.axhline(y, color=INK2, linewidth=1, linestyle=(0, (4, 3)))
        ax1.text(1.42, y, text, va="bottom", ha="right", fontsize=8, color=INK2)
    ax1.set_xticks([0, 1])
    ax1.set_xticklabels(["plain", "delimited"])
    ax1.set_xlim(-0.6, 1.5)
    ax1.set_ylim(0, n + 2)
    ax1.set_ylabel("runs where judge agrees with your label", color=INK2, fontsize=9)
    ax1.set_title("Agreement with hand labels", loc="left", fontsize=10, color=INK, pad=10)

    # Panel B: how often each says N (report fails), per agent run
    tags = list(FILES)
    scorer, plain_n, delim_n = [], [], []
    for t in tags:
        scorer.append(sum(r["scorer"] == "N" for r in data["plain"] if r["tag"] == t))
        plain_n.append(sum(r["verdict"] == "N" for r in data["plain"] if r["tag"] == t))
        delim_n.append(sum(r["verdict"] == "N" for r in data["delimited"] if r["tag"] == t))
    style(ax2)
    w = 0.26
    xs = range(len(tags))
    b1 = ax2.bar([x - w - 0.02 for x in xs], scorer, w, color=GRAY, edgecolor=SURFACE, linewidth=2,
                 label="keyword scorer: fail")
    b2 = ax2.bar(list(xs), plain_n, w, color=BLUE, edgecolor=SURFACE, linewidth=2, label="judge, plain: N")
    b3 = ax2.bar([x + w + 0.02 for x in xs], delim_n, w, color=ORANGE, edgecolor=SURFACE, linewidth=2,
                 hatch="//", label="judge, delimited: N")
    for bars_, vals in ((b1, scorer), (b2, plain_n), (b3, delim_n)):
        bar_label(ax2, bars_, vals)
    ax2.set_xticks(list(xs))
    ax2.set_xticklabels([NICE[t] for t in tags])
    ax2.set_ylim(0, max(scorer + plain_n + delim_n) * 1.18)
    ax2.set_ylabel("runs called a bad report (count)", color=INK2, fontsize=9)
    ax2.set_title("How many runs each one flags", loc="left", fontsize=10, color=INK, pad=10)
    ax2.legend(frameon=False, fontsize=8.5, labelcolor=INK2, loc="upper center",
               bbox_to_anchor=(0.5, -0.16), ncol=3)

    fig.suptitle(f"Baseline check, judge: {a.judge}" + (" (with case description)" if a.ctx else ""),
                 x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out = ROOT / "results" / f"baseline_{slug(a.judge)}{'_ctx' if a.ctx else ''}.png"
    fig.savefig(out, facecolor=SURFACE, bbox_inches="tight")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
