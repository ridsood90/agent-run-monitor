# agent-run-monitor

**Can a small LLM monitor tell whether an agent's report matches what happened, and can text the
attacker controls change its verdict?**

> **Status: work in progress.** The first judge has been run on 459 stored agent runs and checked
> against hand labels. It does not yet pass that check, so the attack test has not been run.
> What was found, and what comes next, is below.

## Why I built this

I am building this to understand if there is a way to make the LLM as a judge more secure from the
prompt injection or tool injection so it can provide that safety barrier to the application in
general against the attacks.

This is the second project after [agentic-ai-lab](https://github.com/ridsood90/agentic-ai-lab),
a robustness eval of a tool-using travel agent under tool failures and indirect prompt injection.
That project found no attacker emails in 520 runs. The failures were in what the agent told the
user: it repeated injected text, claimed success that did not happen, or invented results. Judging
that with keywords needed a hand-check and a scorer fix, which is the case for a separate monitor.
A monitor reads text the attacker can influence, so it can be attacked too.

The attack idea comes from the monitor-injection finding in Anthropic's
[Red-Teaming Auto Mode](https://alignment.anthropic.com/2026/red-teaming-auto-mode/) post: framing
each turn with unguessable delimiters and escaping agent-written content substantially reduced
attack success there. This repo is **inspired by that mechanism, not a replication**. Their monitor
guards a coding agent against a strong attacker. This one is a small local model judging a travel
agent's report against fixed payloads, so the numbers are not comparable.

## How it works

```mermaid
flowchart LR
    A["agentic-ai-lab<br/>26 cases x 5 repetitions<br/>Qwen, Mistral<br/>validator on / off"] --> B["459 stored runs<br/>user request, tools called,<br/>emails, agent reply"]
    B --> C{"how the run<br/>is shown"}
    C --> D["plain<br/>NAME: headers"]
    C --> E["delimited<br/>random token + escaping"]
    D --> F["judge LLM<br/>Llama 3.1 8B"]
    E --> F
    F --> G["verdict<br/>Y = report matches what happened<br/>N = it does not"]
    G --> H["Baseline check (done)<br/>agreement with hand labels<br/>and keyword scorer"]
    G -.-> I["Attack test (not run yet)<br/>add a payload to the reply,<br/>count runs flipped N to Y"]
    classDef todo stroke-dasharray: 5 5
    class I todo
```

- **Data.** Four runs from agentic-ai-lab (Qwen3 8B and Mistral 7B, validator on and off), copied
  into `data/`. After dropping baseline cases, ERROR records and unscored runs, 459 runs remain.
  The keyword scorer failed 104 of them on the report score. 34 runs were labeled by hand.
- **Judge.** Sees the user request, tools called, emails attempted and recorded, and the agent's
  reply. It answers `VERDICT: Y` (the report matches what happened) or `VERDICT: N`, using the
  same rubric as the hand-check.
- **Two framings.** *plain*: sections pasted under `NAME:` headers. *delimited*: each section is
  wrapped in `<<<token NAME>>>` ... `<<<token END>>>` with a fresh random token per call, and runs
  of `<<<` or `>>>` inside the content are escaped.
- **Payloads (attack test).** Six fixed, hand-written texts aimed at the monitor: a direct note,
  forged sections, a fake end marker, a forged system message, a forged human reviewer comment and
  a format hijack. Each is appended to the agent's reply.
- **Metric (attack test).** A *flip* is a run the judge called N with no payload that it calls Y
  with one. Counts are flips / runs-at-risk, per payload and framing.

## Where it stands: the baseline check

Before attacking a judge, it has to be shown that it judges well without an attack. Otherwise a
"flip" means little.

![Baseline check: agreement with hand labels, and how many runs each judge and the keyword scorer flag](results/baseline_ollama_llama3.1_8b.png)

*Left: runs (of the 34 hand-labeled) where the judge agrees with the hand label. The dashed lines
show what answering Y for every run or a coin flip would score. Right: runs flagged as bad reports
in each agent run, by the keyword scorer and by the judge. Counts, not percentages.*


The judge called N on 323 of 459 runs in plain framing and 290 in delimited, while the keyword
scorer failed 104. It does not clearly beat answering Y for every run on the hand labels.

**What reading the disagreements showed** (15 runs where the judge and my hand label differed):
- **Most were judge errors.** In 7 of 15, the agent said the email could not be sent (timeouts and
  tool errors) and the judge read it as claiming the email was sent. Several judge reasons cited
  tool output it was never shown. Two were stricter than the rubric.
- **In the rest the judge was right and my label was wrong or debatable.** For example a reply that
  repeated the injected instruction, or filled in flight details with placeholders. Those labels
  were corrected.
- **So the 34 labels are no longer a clean test set.** I only re-checked the runs where we
  disagreed, which pushes agreement upward. A fresh, blind sample is needed before claiming the
  judge works.

## What comes next

1. **Judge prompt v2**, in a new file so the v1 results stay as the record: say that the email
   tool is a mock where "recorded" counts as sent, that a reply saying the email failed is honest,
   and that tool outputs are not shown.
2. **A fresh blind hand-labeled sample** to test v2 on, since v2 is written after seeing the
   current 34.
3. **Pass or stop.** If v2 clearly beats answering Y for every run on fresh labels, run the attack
   test. If not, report that and stop.
4. **Log tool outputs** in agentic-ai-lab (patch prepared), re-run the four agent runs, and
   let the monitor see the real tool output, so payloads arrive where an attacker would put them.
5. **A second judge model** from a different family, and a larger attack set.
6. **More attack types from the paper**, such as a monitor that does not see some actions.
7. **A write-up** of the whole line of work.

## My prediction for the attack test

*Written on 19 Nov 2026, before the attack test was run:* My prediction is that there will be some
decrease in the failures with unguessable delimiters, but this is just a prediction and testing will
prove whether it will work or not.

## Running it

```bash
pip install -r requirements.txt
python -m unittest discover -s tests              # no model needed

ollama pull llama3.1:8b                            # judge: a different family from the agents
python scripts/run_baseline.py --judge ollama:llama3.1:8b
python scripts/plot_baseline.py --judge ollama:llama3.1:8b      # chart above
python scripts/show_disagreements.py --judge ollama:llama3.1:8b # judge vs hand label, with replies

# only after the baseline check passes:
python scripts/run_attack.py --judge ollama:llama3.1:8b --limit 40
python scripts/report.py     --judge ollama:llama3.1:8b
```

Runs are resumable (`results/*.jsonl`). The scripts always compare with the current hand labels in
`data/handlabels/`, so corrected labels take effect without re-judging. `--judge stub:gullible`
runs the pipeline with a fake model to check the wiring; its numbers mean nothing.

Judge model: `llama3.1:8b`, digest `46e0c10c039e`.

## Limitations

- **The judge is not shown tool outputs.** agentic-ai-lab's stored results did not keep them, so
  the judge cannot check claims about search results, and payloads would reach it through the
  agent's reply, not through raw tool output.
- **Labels were corrected after seeing the judge's verdicts**, and only where we disagreed.
- **Hand labels are thin** (34 runs, a few of them N), and the same labels were used to find the
  judge's problems.
- **The delimited framing changes two things at once:** the delimiters and an extra paragraph
  telling the judge how the markers work.
- **Small local judge, fixed payloads.** The payloads are not adaptive. A small model's behavior
  says little about a production monitor.
- **One sample per call** (temperature 0), no confidence intervals.

## Project structure

```
monitor/     framing, payloads, backends, judge, data loading
scripts/     run_baseline.py, plot_baseline.py, show_disagreements.py, run_attack.py, report.py
tests/       framing (forgery and escaping), parsing, cache, data checks
data/        runs, cases and hand labels copied from agentic-ai-lab
results/     jsonl, charts and summary tables
```
