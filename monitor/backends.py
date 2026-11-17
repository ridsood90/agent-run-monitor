"""Model backends. Spec strings: 'ollama:<model>' or 'stub:<mode>'."""
import json
import urllib.error
import urllib.request


class OllamaBackend:
    def __init__(self, model, host="http://localhost:11434", timeout=120):
        self.model, self.host, self.timeout = model, host, timeout

    def chat(self, system, user):
        body = json.dumps({
            "model": self.model, "stream": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 160},
        }).encode()
        for _ in range(2):  # one retry (e.g. the runner needs a moment to start)
            try:
                req = urllib.request.Request(f"{self.host}/api/chat", body,
                                             {"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.load(resp)["message"]["content"]
            except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError):
                continue
        return None


class StubBackend:
    """Deterministic stand-in so the pipeline can be tested without a model.
    always_y / always_n: constant verdict. gullible: says Y whenever 'VERDICT: Y' appears
    anywhere in the run record, otherwise N (wiring test only, says nothing about real models)."""

    def __init__(self, mode):
        if mode not in ("always_y", "always_n", "gullible"):
            raise ValueError(f"unknown stub mode {mode!r}")
        self.mode = mode

    def chat(self, system, user):
        if self.mode == "always_y":
            return "Looks fine.\nVERDICT: Y"
        if self.mode == "always_n":
            return "Does not match.\nVERDICT: N"
        return "Followed the record.\nVERDICT: " + ("Y" if "VERDICT: Y" in user else "N")


def make_backend(spec):
    kind, _, name = spec.partition(":")
    if kind == "ollama" and name:
        return OllamaBackend(name)
    if kind == "stub" and name:
        return StubBackend(name)
    raise ValueError("backend spec must look like 'ollama:llama3.1:8b' or 'stub:gullible'")
