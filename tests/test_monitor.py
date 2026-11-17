import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from monitor.backends import StubBackend, make_backend           # noqa: E402
from monitor.data import attack_set, load_cases, load_hand_labels, load_runs  # noqa: E402
from monitor.framing import (NAMES, build_messages, delimited, escape, parse_delimited,  # noqa: E402
                             plain, sections, user_text)
from monitor.judge import Cache, judge, parse_verdict            # noqa: E402
from monitor.payloads import PAYLOADS                            # noqa: E402

RUNS, CASES, LABELS = load_runs(), load_cases(), load_hand_labels()
RUN = next(r for r in RUNS if r["category"] == "tool_injection")
CASE = CASES[RUN["case_id"]]


class Framing(unittest.TestCase):
    def test_token_is_random_per_call(self):
        tokens = {build_messages(RUN, CASE, "delimited")[2] for _ in range(20)}
        self.assertEqual(len(tokens), 20)

    def test_escape_removes_marker_like_runs(self):
        for text in ("<<<END>>>", "a <<<abc END>>> b", ">>>>>>", "<<<<"):
            self.assertNotRegex(escape(text), r"<{3}|>{3}")

    def test_every_payload_stays_inside_its_block(self):
        for name, payload in PAYLOADS.items():
            system, user, token = build_messages(RUN, CASE, "delimited", payload)
            blocks = parse_delimited(user, token)
            self.assertEqual([b[0] for b in blocks], NAMES, name)
            reply = dict(blocks)["AGENT REPLY"]
            self.assertIn(escape(payload).strip().splitlines()[-1], reply, name)
            self.assertEqual(user.count(f"<<<{token} "), len(NAMES) * 2, name)   # no extra markers

    def test_plain_framing_can_be_forged(self):
        # a naive "NAME:" header parser finds extra sections when the payload forges them
        def headers(prompt):
            return re.findall(r"^(" + "|".join(NAMES) + r"):$", prompt, re.M)
        clean = plain(sections(RUN, CASE))
        forged = plain(sections(RUN, CASE, PAYLOADS["forged_sections"]))
        self.assertEqual(len(headers(clean)), len(NAMES))
        self.assertGreater(len(headers(forged)), len(NAMES))

    def test_delimited_system_prompt_names_the_token(self):
        system, user, token = build_messages(RUN, CASE, "delimited")
        self.assertIn(token, system)
        self.assertNotIn(token, build_messages(RUN, CASE, "plain")[0])

    def test_token_not_guessable_from_content(self):
        secs = [("AGENT REPLY", "x")]
        _, token = delimited(secs, token="cafe1234")
        self.assertEqual(token, "cafe1234")


class UserText(unittest.TestCase):
    def test_every_case_has_user_text(self):
        for c in CASES.values():
            self.assertTrue(user_text(c).strip(), c["id"])

    def test_multi_turn_case_lists_turns(self):
        self.assertIn("(turn 2)", user_text(CASES["conversation_data_exfiltration_001"]))


class Judge(unittest.TestCase):
    def test_parse_verdict(self):
        self.assertEqual(parse_verdict("fine\nVERDICT: Y"), "Y")
        self.assertEqual(parse_verdict("VERDICT: Y\nbut actually\nVERDICT: N"), "N")   # last wins
        self.assertEqual(parse_verdict("verdict: n"), "N")
        self.assertEqual(parse_verdict("no idea"), "UNPARSED")
        self.assertEqual(parse_verdict("VERDICT: Yes"), "UNPARSED")
        self.assertEqual(parse_verdict(None), "UNPARSED")

    def test_stub_modes(self):
        for mode, want in (("always_y", "Y"), ("always_n", "N")):
            self.assertEqual(judge(StubBackend(mode), RUN, CASE, "plain")["verdict"], want)
        gullible = StubBackend("gullible")
        self.assertEqual(judge(gullible, RUN, CASE, "plain")["verdict"], "N")
        self.assertEqual(judge(gullible, RUN, CASE, "plain", PAYLOADS["direct_note"])["verdict"], "Y")

    def test_backend_error_is_recorded(self):
        class Broken:
            def chat(self, system, user):
                return None
        self.assertEqual(judge(Broken(), RUN, CASE, "plain")["verdict"], "ERROR")

    def test_bad_specs(self):
        for spec in ("ollama", "stub:nope", "x:y"):
            with self.assertRaises(ValueError):
                make_backend(spec)

    def test_cache_resumes_and_retries_errors(self):
        with tempfile.TemporaryDirectory() as d:
            c = Cache(Path(d) / "c.jsonl")
            c.put({"key": "a", "verdict": "Y"})
            c.put({"key": "b", "verdict": "ERROR"})
            c2 = Cache(Path(d) / "c.jsonl")
            self.assertEqual(c2.get("a")["verdict"], "Y")
            self.assertIsNone(c2.get("b"))
            self.assertIsNone(c2.get("zzz"))


class Data(unittest.TestCase):
    def test_load_runs_counts(self):
        self.assertEqual(len(RUNS), 459)
        self.assertEqual(sum(r["report_pass"] is False for r in RUNS), 104)

    def test_hand_labels_map_to_runs(self):
        ids = {r["id"] for r in RUNS}
        self.assertEqual(len(LABELS), 34)
        self.assertTrue(set(LABELS) <= ids)

    def test_attack_set_puts_hand_n_first_and_respects_limit(self):
        chosen = attack_set(RUNS, LABELS, limit=20, seed=1)
        self.assertEqual(len(chosen), 20)
        hand_n = [r for r, s in chosen if s == "hand_N"]
        self.assertEqual(len(hand_n), sum(v == "N" for v in LABELS.values()))
        self.assertTrue(all(r["report_pass"] is False for r, s in chosen if s == "scorer_fail"))
        self.assertEqual([r["id"] for r, _ in chosen], [r["id"] for r, _ in attack_set(RUNS, LABELS, 20, 1)])


if __name__ == "__main__":
    unittest.main()
