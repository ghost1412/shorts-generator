"""Second-opinion check for FACTS and TRIVIA: one more LLM call that judges each claim on its own, without being told which
one is meant to be the lie. A script is kept only when the judge agrees with the labels (the true facts are true, the lie is
false). If the judge itself cannot be reached or answers nonsense, the script is kept and a warning is printed (fail open);
SHORTSFLOW_FACT_CHECK=off turns the check off. This is a model checking a model: it lowers wrong "facts", it does not
remove them."""
import json
import os
import re


def enabled():
    return (os.getenv("SHORTSFLOW_FACT_CHECK") or "on").strip().lower() not in ("off", "0", "false", "no")


def _verdicts(text, n):
    """List of n verdict strings ("true"/"false"/"unsure") from the judge's reply, or None when unreadable."""
    m = re.search(r"\[.*\]", text or "", re.S)
    try:
        raw = json.loads(m.group(0)) if m else None
    except ValueError:
        return None
    if not isinstance(raw, list) or len(raw) != n:
        return None
    out = []
    for v in raw:
        if isinstance(v, dict):
            if "verdict" not in v:
                return None                          # not a verdict list at all
            v = v["verdict"]
        v = str(v).strip().lower()
        out.append(v if v in ("true", "false", "unsure") else "unsure")
    return out


def judge(claims, ask):
    """Verdicts for each claim string ("true", "false", "unsure"), or None when the judge failed. ask(prompt) -> reply text."""
    numbered = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(claims))
    prompt = ("You are a careful fact checker. For each numbered statement, say whether it is factually TRUE, FALSE, or UNSURE "
              "(use UNSURE when it is disputed, depends on definitions, or you do not know). Judge each one alone, by "
              "well-documented knowledge only.\n\n" + numbered +
              '\n\nReply with a JSON array of exactly %d strings, in order, each "true", "false" or "unsure". JSON only.' % len(claims))
    try:
        return _verdicts(ask(prompt), len(claims))
    except Exception as e:
        print(f"[Warning] Fact check could not run ({e}); keeping the script unchecked.")
        return None


def facts_ok(data, ask):
    """True when the judge agrees that the facts marked true are true and the lie is false (or the judge could not decide to run)."""
    if not enabled():
        return True
    facts = data["facts"]
    got = judge([f["fact"] for f in facts], ask)
    if got is None:
        print("[Warning] Fact check gave no usable answer; keeping the script unchecked.")
        return True
    for f, v in zip(facts, got):
        want = "true" if f["truth"] else "false"
        if v != want:
            print(f"[Log] Fact check disagrees ({v} vs {want}): {f['fact'][:70]!r}")
            return False
    return True


def trivia_ok(data, ask):
    """True when the judge agrees that the answer is right and the other two options are wrong."""
    if not enabled():
        return True
    opts = [data.get("opt_a"), data.get("opt_b"), data.get("opt_c")]
    if not all(isinstance(o, str) and o.strip() for o in opts):
        return True                                  # not the three-option shape: nothing to judge
    q = data.get("question", "")
    claims = [f"The answer to the question \"{q}\" is: {o}." for o in opts]
    got = judge(claims, ask)
    if got is None:
        print("[Warning] Fact check gave no usable answer; keeping the question unchecked.")
        return True
    for o, v in zip(opts, got):
        want = "true" if str(o).strip().lower() == str(data.get("answer", "")).strip().lower() else "false"
        if v != want:
            print(f"[Log] Fact check disagrees ({v} vs {want}) on option {o!r}")
            return False
    return True
