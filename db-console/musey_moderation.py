"""Musey-as-moderator: ask the local `musey` Ollama model to review a post.

Experimental: the deployed Musey is a small open-weights model (qwen3:0.6b)
with documented honesty limits (see forum-stack/musey/SMOKE_TESTS.md). A
spam/abuse verdict on a short post is a bounded task, but every verdict is
labeled as model-generated and an audit trail is kept.

Audit log: musey_reviews.jsonl next to this file — one JSON object per
review. Local-only until the forum database is provisioned, at which point
reviews should move to a proper table.
"""

import json
import os
import time
import urllib.request

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("MUSEY_MODEL", "musey:latest")

SYSTEM_PROMPT = (
    "You are Musey, the moderator of a small discussion forum. "
    "Review the forum post below for spam, abuse, harassment, or "
    "off-topic commercial content. Ordinary disagreement, typos, and "
    "short replies are fine. Reply with exactly two lines:\n"
    "VERDICT: OK  — if the post is acceptable\n"
    "VERDICT: FLAG — if it should be reviewed by a human\n"
    "REASON: one short sentence explaining the verdict."
)

AUDIT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "musey_reviews.jsonl")


def _post_json(url, payload, timeout):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ollama_available():
    try:
        data = _post_json(OLLAMA_URL + "/api/tags", {}, timeout=5)
        names = [m.get("name", "") for m in data.get("models", [])]
        return True, names
    except Exception as e:  # noqa: BLE001
        return False, ["%s: %s" % (type(e).__name__, e)]


def parse_verdict(text):
    """(verdict, reason) from model output. verdict in {OK, FLAG, UNKNOWN}."""
    verdict, reason = "UNKNOWN", ""
    for line in (text or "").splitlines():
        s = line.strip()
        up = s.upper()
        if up.startswith("VERDICT:"):
            v = up.split(":", 1)[1].strip().split()[0] if up.split(":", 1)[1].strip() else ""
            verdict = v if v in ("OK", "FLAG") else "UNKNOWN"
        elif up.startswith("REASON:"):
            reason = s.split(":", 1)[1].strip()
    return verdict, reason


def review_post(body, timeout=120):
    """Ask Musey to review a post body. Returns a result dict.

    On any failure (server down, model missing, timeout, unparseable
    output) the dict carries verdict="ERROR" and an `error` message —
    never raises.
    """
    started = time.time()
    result = {"model": MODEL, "verdict": "ERROR", "reason": "",
              "raw": "", "ms": 0, "error": ""}
    try:
        data = _post_json(
            OLLAMA_URL + "/api/chat",
            {"model": MODEL, "stream": False,
             "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user",
                           "content": "Forum post to review:\n\n" + body}]},
            timeout=timeout)
        raw = (data.get("message") or {}).get("content", "")
        verdict, reason = parse_verdict(raw)
        result.update(raw=raw, ms=int((time.time() - started) * 1000))
        if verdict == "UNKNOWN":
            result["error"] = "could not parse a VERDICT from model output"
        else:
            result["verdict"] = verdict
            result["reason"] = reason
    except Exception as e:  # noqa: BLE001
        result["error"] = "%s: %s" % (type(e).__name__, e)
        result["ms"] = int((time.time() - started) * 1000)
    return result


def log_review(post_id, username, body, result):
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
             "post_id": post_id, "username": username,
             "body_excerpt": (body or "")[:200],
             "model": result.get("model"), "verdict": result.get("verdict"),
             "reason": result.get("reason"), "ms": result.get("ms"),
             "error": result.get("error", "")}
    with open(AUDIT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def recent_reviews(limit=20):
    if not os.path.isfile(AUDIT_PATH):
        return []
    out = []
    with open(AUDIT_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    return out[-limit:][::-1]
