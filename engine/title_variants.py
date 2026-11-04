"""Alternative titles for a clip (curiosity / number / question), kept only if they are grounded in what is said.

Small local models invent details, so every variant is checked against the clip's transcript: numbers and capitalised names
that appear nowhere in the transcript, the hook or the main title get the variant dropped. No LLM, no variants (nothing is
made up from templates).
"""
import re

STYLES = ("curiosity", "number", "question")
MAX_LEN = 70

PROMPT_RULES = (
    '- title_variants: exactly 3 alternative titles for the same clip, each under 60 chars, one per style:\n'
    '  {"style": "curiosity", ...} (tease the payoff, do not give it away), {"style": "number", ...} (use a number that is '
    'said in the clip), {"style": "question", ...} (ask the question the clip answers). Use ONLY facts, numbers and names '
    'from the transcript.\n'
)
PROMPT_SCHEMA = '"title_variants": [{"style": "curiosity", "title": "..."}, {"style": "number", "title": "..."}, {"style": "question", "title": "..."}]'

_NUMBER_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
    "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "twenty": "20", "thirty": "30", "forty": "40", "fifty": "50",
    "hundred": "100", "thousand": "1000", "million": "1000000", "billion": "1000000000",
}
# capitalised words that are not names (sentence starters and fillers a title often begins a clause with)
_COMMON = {
    "the", "a", "an", "this", "that", "these", "those", "why", "how", "what", "when", "where", "who", "which", "is", "are",
    "was", "were", "do", "does", "did", "can", "could", "will", "would", "should", "you", "your", "i", "we", "they", "he",
    "she", "it", "my", "our", "his", "her", "their", "no", "not", "never", "always", "stop", "watch", "wait", "here",
    "nobody", "everyone", "everything", "secret", "truth", "real", "biggest", "best", "worst", "one", "if", "and", "but",
    "or", "so", "just", "only", "most", "more", "all", "every", "inside", "behind", "before", "after", "in", "on", "at",
    "to", "for", "of", "from", "with", "without", "about", "i'm", "it's", "don't", "here's", "that's", "let's",
}


def _words(text):
    return re.findall(r"[\w'’]+", (text or "").lower())


def _numbers(text):
    """Digits in the text (1,000 -> 1000, 2.5 stays) plus spelled-out numbers, as comparable strings."""
    out = set()
    for m in re.findall(r"\d[\d,]*(?:\.\d+)?", text or ""):
        out.add(m.replace(",", "").rstrip("."))
    for w in _words(text):
        if w in _NUMBER_WORDS:
            out.add(_NUMBER_WORDS[w])
    return out


def ungrounded_numbers(variant, source_text):
    """Numbers in `variant` that the source never says (digits or spelled out)."""
    have = _numbers(source_text)
    return sorted(n for n in _numbers(variant) if n not in have)


def ungrounded_names(variant, source_text):
    """Capitalised words (not at the start, not common words) that the source never says."""
    src = set(_words(source_text))
    src_stems = {w.rstrip("s") for w in src}
    out = []
    tokens = re.findall(r"[\w'’]+", variant or "")
    for i, tok in enumerate(tokens):
        low = tok.lower()
        # the first word is skipped: any title starts with a capital, so it says nothing (a known gap: an invented name in
        # first position is not caught, the other checks and the model's own instruction have to cover it)
        if i == 0 or not tok[0].isupper():
            continue
        if low in _COMMON or tok.isdigit():
            continue
        if low in src or low.rstrip("s") in src_stems or low.replace("’", "'") in src:
            continue
        out.append(tok)
    return out


def check_variant(title, transcript, extra_sources=()):
    """List of problems with a variant: [] when it is grounded and usable."""
    title = (title or "").strip()
    if not title:
        return ["empty"]
    if len(title) > MAX_LEN:
        return ["too long"]
    source = " ".join([transcript or ""] + [s for s in extra_sources if s])
    problems = []
    nums = ungrounded_numbers(title, source)
    if nums:
        problems.append("numbers not in the transcript: " + ", ".join(nums))
    names = ungrounded_names(title, source)
    if names:
        problems.append("names not in the transcript: " + ", ".join(names))
    return problems


def parse_variants(raw, transcript, base_title="", hook=None, max_variants=3):
    """Variants from the model's `title_variants` value: [{"style", "title"}] kept when grounded, unique, and different from
    the main title. Accepts plain strings too. Returns [] on anything unusable."""
    if not isinstance(raw, list):
        return []
    seen = {re.sub(r"\W+", "", (base_title or "").lower())}
    out = []
    for i, item in enumerate(raw):
        if isinstance(item, dict):
            title, style = str(item.get("title") or "").strip(), str(item.get("style") or "").strip().lower()
        else:
            title, style = str(item or "").strip(), ""
        if style not in STYLES:
            style = STYLES[i] if i < len(STYLES) else "curiosity"
        title = title.strip('"').strip()
        key = re.sub(r"\W+", "", title.lower())
        if not key or key in seen:
            continue
        if check_variant(title, transcript, extra_sources=(hook, base_title)):
            continue
        seen.add(key)
        out.append({"style": style, "title": title})
        if len(out) >= max_variants:
            break
    return out


def variants_text(variants):
    """Copy-ready lines: '[Curiosity] title' per variant."""
    return "\n".join(f"[{(v.get('style') or 'idea').title()}] {v.get('title', '')}" for v in variants or [] if v.get("title"))
