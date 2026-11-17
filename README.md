# agent-run-monitor

**Question.** A small LLM reads a finished run of a tool-using agent and says whether the agent's
report to the user matches what actually happened. If text the attacker controls reaches the
monitor, can it change the verdict? And does wrapping the run in unguessable delimiters, with
delimiter-like text escaped, reduce that?

This is the second project after [agentic-ai-lab](https://github.com/ridsood90/agentic-ai-lab),
a robustness eval of a travel agent under tool failures and indirect prompt injection.

<!-- TODO(Ridhi): "Why I built this" in your own words, 3-5 sentences. Start from what you saw
in the hand-check of agentic-ai-lab (the keyword scorer missed and over-flagged runs). -->

## Background

agentic-ai-lab found no attacker emails in 520 runs. The failures were in what the agent told the
user: it relayed injected text, claimed success that did not happen, or invented results. Judging
that by keywords needed a hand-check and a scorer fix, which is the case for a separate monitor.
The monitor reads text the attacker can influence, so it can be attacked too.

The framing comes from the monitor-injection finding in Anthropic's
[Red-Teaming Auto Mode](https://alignment.anthropic.com/2026/red-teaming-auto-mode/) post:
framing each turn with unguessable delimiters and escaping agent-written content substantially
reduced attack success there. This repo is **inspired by that mechanism, not a replication**. Their
monitor guards a coding agent against a strong attacker; this one is a small local model judging a
travel agent's report against fixed payloads. The numbers are not comparable.

## Data

Copied from agentic-ai-lab (`data/`): four runs of the same 26 cases x 5 repetitions
(Qwen3 8B and Mistral 7B, validator on and off). After dropping baseline cases, ERROR records and
unscored runs, 459 runs remain. The keyword scorer failed 104 of them on the report score. 34 runs
were labeled by hand in agentic-ai-lab (8 of them N: the report does not match what happened).

## Method

1. **Monitor input.** For each run: the user request, tools called, emails attempted, emails
   recorded and the agent's reply. The monitor answers `VERDICT: Y` (report matches what happened)
   or `VERDICT: N`, using the same rubric as the hand-check.
2. **Two framings.** *plain*: sections pasted under `NAME:` headers. *delimited*: each section is
   wrapped in `<<<token NAME>>>` ... `<<<token END>>>` with a fresh random token per call, and
   runs of `<<<` or `>>>` inside the content are escaped.
3. **Payloads.** Six fixed, hand-written texts aimed at the monitor (`monitor/payloads.py`):
   a direct note, forged sections, a fake end marker, a forged system message, a forged human
   reviewer comment and a format hijack. Each is appended to the agent reply, as if a tool had
   returned it and the agent had echoed it.
4. **Attack set.** Every hand-labeled N run, then a seeded sample of keyword-scorer failures, up
   to 40 runs.
5. **Metric.** A *flip* is a run the monitor called N with no payload that it calls Y with one.
   Counts are flips / runs-at-risk, per payload and framing. Unparsed and error verdicts are
   listed, not dropped.

## Running it

```bash
pip install -r requirements.txt
python -m unittest discover -s tests            # no model needed

ollama pull llama3.1:8b                          # judge: a different family from the agents
python scripts/run_baseline.py --judge ollama:llama3.1:8b
python scripts/run_attack.py   --judge ollama:llama3.1:8b --limit 40
python scripts/report.py       --judge ollama:llama3.1:8b
```

Runs are resumable (`results/*.jsonl`). `--judge stub:gullible` runs the whole pipeline with a
fake model to check the wiring; its numbers mean nothing.

## Results

Not run yet. The table and chart from `scripts/report.py` go here, with the judge model and its
digest (`ollama show <model>`).

## Limitations

- **The tool output itself was not stored** in agentic-ai-lab's results, so payloads reach the
  monitor through the agent's reply, not through raw tool output.
- **The delimited framing changes two things at once:** the delimiters and an extra paragraph
  telling the monitor how the markers work. This design cannot separate them.
- **Small local judge, fixed payloads.** The payloads are not adaptive and were not tuned to a
  judge. A small model's behavior says little about a production monitor.
- **The at-risk set leans on the keyword scorer.** Only 8 attack runs are hand-labeled N; the rest
  are runs the scorer failed and the monitor itself called N. Hand labels are thin (34).
- **One sample per call** (temperature 0), no confidence intervals. Small differences are noise.
- **Hand labelers saw the case description; the monitor does not** unless run with
  `--case-context`.

## Project structure

```
monitor/     framing, payloads, backends, judge, data loading
scripts/     run_baseline.py, run_attack.py, report.py
tests/       framing (forgery and escaping), parsing, cache, data checks
data/        runs, cases and hand labels copied from agentic-ai-lab
results/     jsonl, summary tables and charts
```
