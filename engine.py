"""RUMOURPRINT narrative detection.

Embeddings identify possible shared topics/narratives, NOT truth, authorship,
spread, temporal priority, or implication that the message is disinformation.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from math import sqrt
from typing import Any

STOP = {
    'the', 'a', 'an', 'is', 'are', 'to', 'of', 'for', 'and', 'on', 'in',
    'has', 'have', 'had', 'that', 'all', 'with', 'by', 'from', 'at',
    'be', 'been', 'was', 'were', 'will', 'now', 'it', 'as', 'after',
    'following', 'following', 'its', 'their', 'this', 'there', 'new',
}

BROAD_SCOPE = {"all", "every", "entire", "nationwide", "throughout", "everywhere", "countrywide"}
NARROW_SCOPE = {"some", "few", "one", "single", "only", "selected", "specific", "certain"}
UNCERTAIN = {"may", "might", "could", "considering", "proposed", "proposal", "possibly", "reportedly", "allegedly", "rumoured", "rumored"}
CERTAIN = {"confirmed", "approved", "ordered", "announced", "definitely", "officially", "declared"}
DENIAL_PATTERNS = (
    r"\b(?:did not|does not|do not|has not|have not|was not|is not|are not|will not|cannot|can not|not|never|no longer)\b",
    r"\b(?:didn['’]t|doesn['’]t|don['’]t|hasn['’]t|haven['’]t|wasn['’]t|weren['’]t|isn['’]t|aren['’]t|won['’]t|can['’]t)\b",
    r"\b(?:denied|refuted|untrue|false|fake|no evidence|not true)\b",
)
# Partial support for explicitly spelled out figures (not a general number parser).
WORD_NUMBERS_RE = re.compile(
    r"\b(?:(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
    r"thirty|forty|fifty|sixty|seventy|eighty|ninety)[ -]+(?:hundred|thousand|million))\b",
    re.I,
)
NUMBERS_RE = re.compile(r"\b(?:\d+(?:[.,]\d+)*(?:%|shs|ugx)?|\d{1,2}(?:st|nd|rd|th))\b", re.I)


def tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[\w']+", str(text).casefold()) if len(w) > 2 and w not in STOP}


def wording_similarity(a: str, b: str) -> float:
    x, y = tokens(a), tokens(b)
    overlap = len(x & y) / len(x | y) if x | y else 0.0
    sequence = SequenceMatcher(None, a.casefold(), b.casefold()).ratio()
    return round(0.65 * overlap + 0.35 * sequence, 4)


def shift_signals(new: str, previous: str) -> list[str]:
    """Surface review prompts, not conclusions. Keyword cues can be wrong."""
    n = set(re.findall(r"[\w']+", new.casefold()))
    p = set(re.findall(r"[\w']+", previous.casefold()))
    cues = []

    if n & BROAD_SCOPE and not p & BROAD_SCOPE:
        cues.append("Broader scope language appears in the new version")
    if n & NARROW_SCOPE and not p & NARROW_SCOPE:
        cues.append("Narrower scope language appears in the new version")
    if n & CERTAIN and not p & CERTAIN:
        cues.append("More definitive wording appears in the new version")
    if n & UNCERTAIN and not p & UNCERTAIN:
        cues.append("Uncertainty or allegation wording appears in the new version")

    # A future commitment is stronger than a conditional prediction, but is
    # still not proof of an official announcement or a verified event.
    if "will" in n and "will" not in p and p & UNCERTAIN and not n & UNCERTAIN:
        cues.append("Conditional possibility becomes a more definite future claim; verify source")
    if p & {"proposal", "proposed"} and n & {"law", "enacted", "passed"} and not p & {"law", "enacted", "passed"}:
        cues.append("A proposal is described as enacted policy; verify official records")

    n_denied = any(re.search(pat, new.casefold()) for pat in DENIAL_PATTERNS)
    p_denied = any(re.search(pat, previous.casefold()) for pat in DENIAL_PATTERNS)
    if n_denied != p_denied:
        cues.append("Negation or denial language differs; check meaning carefully")

    n_numbers = set(NUMBERS_RE.findall(new.casefold()))
    p_numbers = set(NUMBERS_RE.findall(previous.casefold()))
    # Compare spelled-out round numbers as well as digits.
    n_word_numbers = set(WORD_NUMBERS_RE.findall(new.casefold()))
    p_word_numbers = set(WORD_NUMBERS_RE.findall(previous.casefold()))
    if (n_numbers != p_numbers and (n_numbers or p_numbers)) or (n_word_numbers != p_word_numbers and (n_word_numbers or p_word_numbers)):
        cues.append("Dates, quantities or figures may have changed")

    if not cues:
        cues.append("Check whether the named people, dates and actions still mean the same thing")
    return cues


def candidate_label(score: float, mode: str) -> str:
    # Descriptive heuristics, not calibrated probabilities.
    if mode == "semantic":
        return "Strong candidate" if score >= 0.72 else "Review candidate"
    return "Strong wording match" if score >= 0.75 else "Possible wording match"


def candidate_threshold(mode: str) -> float:
    return 0.48 if mode == "semantic" else 0.36


def _cosine(a: Any, b: Any) -> float:
    # Model returns numpy arrays, while tests can supply Python lists.
    dot = sum(float(x) * float(y) for x, y in zip(a, b))
    n1 = sqrt(sum(float(x) * float(x) for x in a))
    n2 = sqrt(sum(float(y) * float(y) for y in b))
    return dot / (n1 * n2) if n1 and n2 else 0.0


def pairwise_scores(texts: list[str], model: Any | None = None) -> list[list[float]]:
    """Matrix for offline baseline or local AI embeddings."""
    if not texts:
        return []
    vectors = list(model.embed(texts)) if model is not None else None
    n = len(texts)
    scores = [[0.0] * n for _ in range(n)]
    for i in range(n):
        scores[i][i] = 1.0
        for j in range(i + 1, n):
            score = _cosine(vectors[i], vectors[j]) if vectors is not None else wording_similarity(texts[i], texts[j])
            score = max(-1.0, min(1.0, score))
            scores[i][j] = scores[j][i] = score
    return scores


def compare(new: str, existing: list[dict], model: Any | None = None, threshold: float | None = None) -> list[dict]:
    """Compare new text against prior messages, returning review candidates."""
    if not existing:
        return []
    mode = "semantic" if model is not None else "wording"
    cutoff = candidate_threshold(mode) if threshold is None else threshold
    values = pairwise_scores([new] + [item["text"] for item in existing], model)
    matches = []
    for j, item in enumerate(existing, 1):
        score = values[0][j]
        if score >= cutoff:
            matches.append({
                "item": item,
                "score": round(score * 100, 1),
                "method": mode,
                "label": candidate_label(score, mode),
                "added": sorted(tokens(new) - tokens(item["text"])),
                "removed": sorted(tokens(item["text"]) - tokens(new)),
                "signals": shift_signals(new, item["text"]),
            })
    return sorted(matches, key=lambda x: x["score"], reverse=True)


def group_narratives(items: list[dict], model: Any | None = None, threshold: float | None = None) -> list[dict]:
    """Graph components of similar submitted messages (NOT an actual spread graph)."""
    if not items:
        return []
    mode = "semantic" if model is not None else "wording"
    cutoff = (0.61 if mode == "semantic" else 0.44) if threshold is None else threshold
    scores = pairwise_scores([item["text"] for item in items], model)
    seen = set()
    clusters = []
    for i in range(len(items)):
        if i in seen:
            continue
        stack = [i]
        component = []
        seen.add(i)
        while stack:
            current = stack.pop()
            component.append(current)
            for j in range(len(items)):
                if j not in seen and scores[current][j] >= cutoff:
                    seen.add(j)
                    stack.append(j)
        component.sort()
        clusters.append({
            "indices": component,
            "items": [items[index] for index in component],
            "size": len(component),
            "label": items[component[0]]["text"],
        })
    return sorted(clusters, key=lambda x: (-x["size"], x["indices"][0]))
