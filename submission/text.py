from __future__ import annotations

import re


TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "i", "in", "is", "it", "me", "my", "of", "on", "or", "please", "some",
    "that", "the", "this", "to", "want", "with", "would", "you", "looking",
}

MATERIALS = ("cotton", "polyester", "nylon", "leather", "wool", "spandex", "silk", "rayon", "fabric")
COLORS = ("black", "white", "blue", "red", "pink", "green", "brown", "gray", "grey", "purple", "yellow", "orange")


def terms(text: str, limit: int = 80) -> list[str]:
    """Return deterministic unique terms in first-seen order."""
    values = [
        token.lower()
        for token in TOKEN_RE.findall(text)
        if len(token) > 1 and token.lower() not in STOPWORDS
    ]
    return list(dict.fromkeys(values))[:limit]


def clean_value(value: str, limit: int = 240) -> str:
    return re.sub(r"\s+", " ", value).strip(" -;,.:\t\n")[:limit].rstrip()


def classify_attribute(value: str) -> str:
    lowered = value.lower()
    if "budget" in lowered or re.search(r"(?:\$|<=|under|below|less than)\s*\d", lowered):
        return "budget"
    if any(material in lowered for material in MATERIALS):
        return "material"
    if any(word in lowered for word in ("color", *COLORS)):
        return "color"
    if any(word in lowered for word in ("size", "sizing", "width", "wide", "narrow")):
        return "size"
    if any(word in lowered for word in ("brand", "store", "label", "designer")):
        return "brand"
    if any(word in lowered for word in ("department", "style", "fit", "sleeve", "neck", "waist")):
        return "style"
    if any(word in lowered for word in ("hiking", "running", "gym", "winter", "outdoor", "work", "wedding", "casual")):
        return "use_case"
    return "feature"


def safe_session_name(session_id: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_.-]+", "_", session_id).strip("._")
    return value[:96] or "session"
