"""Optional LLM second opinion on the top-ranked pairs.

Enabled when COMPARE50_LLM_URL, COMPARE50_LLM_KEY and COMPARE50_LLM_MODEL are set
(any OpenAI-compatible /chat/completions endpoint). Only the two sources are sent,
labelled A and B: submission names/paths never leave the machine.
"""
import concurrent.futures
import datetime
import json
import os
import time
import urllib.error
import urllib.request

SOURCE_LIMIT = 12000  # chars per submission sent to the model
TIMEOUT = 90          # seconds per call
WORKERS = 4
RETRY_WAITS = tuple(float(s) for s in os.environ.get("COMPARE50_LLM_RETRY_WAITS", "5,15,30").split(",") if s)
VERDICTS = ("likely_copied", "shared_template", "independent", "unclear")

SYSTEM_PROMPT = """You help programming-contest judges review plagiarism reports.
You get two solutions (A and B) to the same problem, flagged as similar by an automatic checker.
Decide whether one was likely copied from the other (or both from a shared source).
Standard algorithms, common templates (fast I/O, #define shortcuts, typical DP loops) and
short solutions are often similar by nature: they are not evidence on their own.
Evidence of copying: same unusual structure or order, identical quirks, dead code or comments,
consistent identifier renaming, same bugs.
Answer with JSON only: {"verdict": "likely_copied" | "shared_template" | "independent" | "unclear",
"confidence": 0.0-1.0, "reasons": [at most 3 short sentences citing concrete code]}"""


class Config:
    def __init__(self, url, key, model, pairs=5, min_score=5.0, language="English"):
        self.url = url.rstrip("/") + "/chat/completions"
        self.key = key
        self.model = model
        self.pairs = pairs
        self.min_score = min_score
        self.language = language

    @classmethod
    def from_env(cls, pairs, min_score, language="English"):
        url, key, model = (os.environ.get(f"COMPARE50_LLM_{k}", "") for k in ("URL", "KEY", "MODEL"))
        if not (url and key and model) or pairs <= 0:
            return None
        return cls(url, key, model, pairs, min_score, language)


def _source(sub):
    parts = []
    for file in sub.files:
        try:
            with open(file.path, encoding="utf8", errors="replace") as f:
                parts.append(f"// file: {file.name}\n{f.read()}")
        except OSError:
            pass
    text = "\n\n".join(parts)
    return text[:SOURCE_LIMIT] + ("\n... (truncated)" if len(text) > SOURCE_LIMIT else "")


def _ask(config, sub_a, sub_b, score):
    user = (f"Checker similarity: {score:.1f}/10 (relative to the most similar pair in this report)\n\n"
            f"--- Solution A ---\n{_source(sub_a)}\n\n--- Solution B ---\n{_source(sub_b)}")
    body = json.dumps({"model": config.model, "temperature": 0,
                       "messages": [{"role": "system", "content": SYSTEM_PROMPT + (
                                        f"\nWrite the reasons in {config.language}; keep the JSON keys and "
                                        "verdict values exactly as given in English.")},
                                    {"role": "user", "content": user}]}).encode()
    req = urllib.request.Request(config.url, data=body, method="POST", headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {config.key}"})
    for wait in RETRY_WAITS + (None,):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                raw = resp.read(1 << 20)
            break
        except urllib.error.HTTPError as e:
            # Rate limits and overload ("high demand") are usually brief: back off and retry
            if e.code in (429, 500, 502, 503, 504) and wait is not None:
                time.sleep(wait)
                continue
            raise RuntimeError(f"HTTP {e.code}: {e.read(200).decode('utf8', 'replace')}") from None

    content = json.loads(raw)["choices"][0]["message"]["content"]
    # Models often wrap the JSON in a ```json fence; take the outermost object.
    i, j = content.find("{"), content.rfind("}")
    ans = json.loads(content[i:j + 1] if 0 <= i < j else content)
    verdict = ans.get("verdict") if ans.get("verdict") in VERDICTS else "unclear"
    reasons = [str(r) for r in (ans.get("reasons") or [])][:3]
    return {"verdict": verdict, "confidence": float(ans.get("confidence") or 0), "reasons": reasons}


def review(config, pairs):
    """pairs: [(match_id, sub_a, sub_b, relative_score)] in rank order.

    Returns the llm.json dict; failed calls are recorded per pair as verdict "error".
    """
    chosen = [p for p in pairs if p[3] >= config.min_score][:config.pairs]

    def one(pair):
        match_id, sub_a, sub_b, score = pair
        out = {"match": match_id, "a": str(sub_a.path), "b": str(sub_b.path), "score": round(score, 2),
               "verdict": "error", "confidence": 0, "reasons": []}
        try:
            out.update(_ask(config, sub_a, sub_b, score))
        except Exception as e:  # never fail the report because of the model
            out["error"] = f"{type(e).__name__}: {e}"[:300]
        return out

    with concurrent.futures.ThreadPoolExecutor(WORKERS) as pool:
        results = list(pool.map(one, chosen))
    return {"model": config.model,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "pairs": results}
