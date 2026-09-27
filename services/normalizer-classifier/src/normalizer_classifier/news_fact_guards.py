"""Conservative lexical blockers, not a fact extractor or evidence of equivalence."""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal

from .news_deduplication import Pair, Report

NUMBER = re.compile(r"(?<!\d)[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
UNIT = re.compile(r"\s*(%|٪|percent\b|per cent\b|bps\b|basis points?\b|barrels?\b|USD\b|EUR\b|dollars?\b|euros?\b|tonnes?\b|tons?\b)", re.I)
UNIT_NAMES = {"%": "percent", "٪": "percent", "per cent": "percent",
              "basis point": "bps", "basis points": "bps", "barrel": "barrels",
              "dollar": "usd", "dollars": "usd", "euro": "eur", "euros": "eur",
              "tonne": "tonnes", "ton": "tons"}
SCALE = re.compile(r"\s*(thousand|million|billion|trillion)\b", re.I)
SCALES = {"thousand": Decimal(1000), "million": Decimal(1000000),
          "billion": Decimal(1000000000), "trillion": Decimal(1000000000000)}
PREFIX = re.compile(r"(USD|EUR|GBP|\$|€|£)\s*$", re.I)
PREFIX_UNITS = {"$": "dollar_symbol", "€": "eur", "£": "gbp"}
SMALL_NUMBERS = dict(zip(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split(),
    range(21), strict=True,
))
SMALL_NUMBER_RE = re.compile(r"\b(" + "|".join(SMALL_NUMBERS) + r")\b", re.I)
MONTHS = "january february march april may june july august september october november december".split()
MONTH_MAP = {name: str(index) for index, name in enumerate(MONTHS, 1)}
MONTH_RE = re.compile(r"\b(" + "|".join(MONTHS) + r")\b", re.I)
CJK_MONTHS = {name: str(index) for index, name in enumerate(
    ("一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二"), 1)}
DATELINE = re.compile(r"\bTEHRAN,\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2}\s+\(MNA\)\s*[–—-]\s*")
STATUS_CUES = {
    "departure": re.compile(r"\b(?:departed|departs|heads to|heading to)\b", re.I),
    "arrival": re.compile(r"\b(?:arrived|arrives|arrival)\b", re.I),
    "meeting_occurred": re.compile(r"\b(?:has met|have met|held talks|hold talks)\b", re.I),
    "denial": re.compile(r"\b(?:denied|denies|denial)\b", re.I),
    "confirmation": re.compile(r"\b(?:confirmed|confirms|confirmation)\b", re.I),
    "uncertain": re.compile(r"\b(?:rumou?rs?|unconfirmed|reportedly)\b", re.I),
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = "".join(str(unicodedata.decimal(char)) if char.isdecimal() else char for char in text)
    text = text.replace("٫", ".").replace("٬", ",")
    # URLs and handles are provenance, not figures in the reported claim.
    text = re.sub(r"https?://\S+|@[\w]+", " ", text)
    # This exact publisher wrapper is provenance, not a claim number. Do not
    # generically strip dates: dates inside actual news can change its identity.
    return DATELINE.sub(" ", text)


def original_text(report: Report) -> str:
    return "\n".join(value for value in (report.title, report.content) if value)


def figures(text: str) -> set[tuple[str, str]]:
    normalized = normalize(text)
    # Match common literal English counts to their digit form (e.g. eight/8).
    # This is not a general number-word parser: compounds and other languages
    # still require review and must not be assumed numerically equivalent.
    normalized = SMALL_NUMBER_RE.sub(lambda match: str(SMALL_NUMBERS[match.group().lower()]), normalized)
    # Numeric CJK months are compared separately as periods, not quantities.
    normalized = re.sub(r"(?<!\d)(1[0-2]|0?[1-9])月", " month ", normalized)
    result = set()
    for match in NUMBER.finditer(normalized):
        value = Decimal(match.group().replace(",", ""))
        scale = SCALE.match(normalized, match.end())
        if scale:
            value *= SCALES[scale.group(1).lower()]
        suffix = UNIT.match(normalized, scale.end() if scale else match.end())
        unit = suffix.group(1).lower() if suffix else "unspecified"
        prefix = PREFIX.search(normalized[:match.start()])
        if prefix and not suffix:
            unit = PREFIX_UNITS.get(prefix.group(1), prefix.group(1).lower())
        result.add((str(value.normalize()), UNIT_NAMES.get(unit, unit)))
    return result


def periods(text: str) -> set[str]:
    normalized = normalize(text)
    # Lowercase modal "may" is not a date. Ambiguous unsupported expressions
    # remain for semantic review rather than being asserted as parsed periods.
    result = {f"month:{MONTH_MAP[match.group().lower()]}" for match in MONTH_RE.finditer(normalized)
              if match.group() != "may"}
    for match in re.finditer(r"(?<!\d)(1[0-2]|0?[1-9])月", normalized):
        result.add(f"month:{int(match.group(1))}")
    for match in re.finditer(r"(十二|十一|[一二三四五六七八九十])月", normalized):
        result.add(f"month:{CJK_MONTHS[match.group(1)]}")
    for match in re.finditer(r"\b(?:Q([1-4])|([1-4])(?:st|nd|rd|th) quarter)\b", normalized, re.I):
        result.add(f"quarter:{match.group(1) or match.group(2)}")
    for match in re.finditer(r"\b(20\d{2})\b", normalized):
        result.add(f"year:{match.group(1)}")
    return result


def merge_blockers(pair: Pair, *, text_mode: str = "original") -> list[str]:
    """A mismatch requires keeping the reports, never declaring a new fact automatically.

    Additional background figures can also block: false negatives are intentional
    until scoped fact extraction is validated. Equal sets do NOT prove duplication.
    Spelled-out numbers, entity drift and unsupported periods require semantic review.
    """
    left, right = original_text(pair.current), original_text(pair.candidate)
    blockers = []
    if figures(left) != figures(right):
        blockers.append("original_numeric_or_unit_difference")
    if periods(left) != periods(right):
        blockers.append("original_period_difference")
    # Lexical cues are NOT parsed event facts: a quoted denial, future-tense
    # meeting or background arrival can over-block a valid duplicate. This is
    # deliberately only a keep-both veto, never a semantic status classifier.
    # The snapshot pilot exposed departure/arrival/meeting stage conflation.
    left_status = {name for name, pattern in STATUS_CUES.items() if pattern.search(normalize(left))}
    right_status = {name for name, pattern in STATUS_CUES.items() if pattern.search(normalize(right))}
    if left_status != right_status:
        blockers.append("original_status_cue_difference")
    if text_mode != "original":
        # A translated decision may be scored, but cannot authorize suppression.
        blockers.append("translation_only_decision")
    return blockers
