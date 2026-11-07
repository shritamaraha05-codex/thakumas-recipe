"""Bengali recipe vocabulary and lexicon lookup (M-07).

This module is the recognition layer between text normalisation (M-05) and the
deterministic rule parser (M-08). It knows *what words mean* in a family recipe
narration but deliberately decides *nothing about the recipe*: it never converts
a traditional measure to grams, never invents a yield, and never silently
rewrites a word it does not recognise.

Vocabulary groups (kept separate, as required by the M-07 brief)
    * ingredient - food names and their classes (A);
    * measure    - household/traditional units and vague quantity phrases (B);
    * number     - number words, classifiers and spoken/numeric ranges (C);
    * duration   - cooking-time words (D).

Lookup order (deterministic, conservative)
    1. exact surface form in the original script;
    2. normalised alias (Roman Bengali / Hindi / English variant);
    3. single-token numeric expressions (digits, decimals, fractions, ranges);
    4. conservative suffix stripping (classifiers first, then genitive ``ের``);
    5. phrase matching, longest first (e.g. ``ছোট চামচ`` is one measure, not two
       words; ``চিতল মাছ`` is one ingredient).
    Fuzzy matching is *not* part of the scan. It is only exposed through
    :meth:`Lexicon.suggest`, which returns candidates for a caller to review; it
    never changes a token on its own.

Evidence
    Vocabulary is drawn from ``docs/05_PARSER_SPEC.md`` cases, the prototype
    tables in ``prototype_v0/core.py`` (as a reference, not copied verbatim),
    ``docs/06_UNITS_REFERENCE.md``, the Chitol Macher Muitha regression fixture
    and the M-07 brief. Every addition is traceable to one of those. The brief's
    explicit warning that ``মুইঠা`` (the fish preparation) must never be read as
    the handful ``মুঠো``/``মুঠি`` is honoured by simply not having ``মুইঠা`` or
    ``মুঠা`` in the vocabulary at all.

Known limitations (documented, not hidden)
    * Only the classifier suffixes and the genitive ``ের`` are stripped. The
      locative ``ে`` is deliberately *not* stripped: it would turn the connector
      ``একে একে`` into two number matches ("একে" -> 1). Other case endings such
      as ``কে``/``ে`` and multi-step stripping are out of scope for M-07.
    * Fuzzy suggestions are English/Roman only, length >= 4, cutoff 0.85 (the
      prototype's rule). Bengali script is never fuzzy-matched.
    * A word that is not in the vocabulary stays unknown; it is never "fixed".
    * Canonical ingredient names are neutral labels for the parser, not a claim
      about nutrition, synonyms or regional variants beyond what is recorded.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Iterable, Sequence

from backend.app.parse.normalize import NormalizedText, Token


class Category(StrEnum):
    """The four separate vocabulary groups required by M-07."""

    INGREDIENT = "ingredient"
    MEASURE = "measure"
    NUMBER = "number"
    DURATION = "duration"


# Match methods, in increasing order of uncertainty. ``find`` only ever emits
# the first four; ``fuzzy`` is produced only by :meth:`Lexicon.suggest`.
METHOD_EXACT = "exact"
METHOD_ALIAS = "alias"
METHOD_NUMERIC = "numeric"
METHOD_SUFFIX = "suffix"
METHOD_PHRASE = "phrase"
METHOD_FUZZY = "fuzzy"


@dataclass(frozen=True, slots=True)
class Entry:
    """One canonical vocabulary item and all the forms that point to it.

    ``surface_forms`` are the original-script forms; ``aliases`` are the Roman
    Bengali / Hindi / English variants. ``kind`` refines a group (e.g. a measure
    that is a unit vs a vague phrase; a number that is a plain value vs an
    "add half" modifier vs a classifier).
    """

    canonical: str
    category: Category
    surface_forms: tuple[str, ...]
    aliases: tuple[str, ...] = ()
    kind: str | None = None
    ingredient_class: str | None = None
    value: float | None = None
    classifier: str | None = None
    to_taste: bool = False
    ambiguous: bool = False
    options: tuple[str, ...] = ()
    note: str = ""

    @property
    def all_forms(self) -> tuple[str, ...]:
        """Every form (surface + alias) that should resolve to this entry."""
        return self.surface_forms + self.aliases


@dataclass(frozen=True, slots=True)
class Match:
    """A recognised expression with its provenance and (optional) ambiguity.

    ``surface`` is always the wording that was actually present (the original
    transcript substring when the caller had one), never the canonical name.
    Spans index the token sequence; ``char_*`` index the normalised text and
    ``orig_*`` index the untouched original transcript when available.
    """

    surface: str
    canonical: str
    category: Category
    method: str
    token_start: int
    token_end: int
    entry: Entry | None = None
    char_start: int | None = None
    char_end: int | None = None
    orig_start: int | None = None
    orig_end: int | None = None
    confidence: float = 1.0
    ambiguous: bool = False
    options: tuple[str, ...] = ()
    value: float | None = None
    value_max: float | None = None
    classifier: str | None = None
    to_taste: bool = False
    kind: str | None = None


# --------------------------------------------------------------------------- #
# Vocabulary tables (group A..D). Kept as separate tuples for auditability.    #
# --------------------------------------------------------------------------- #

INGREDIENT_ENTRIES: tuple[Entry, ...] = (
    Entry("rice", Category.INGREDIENT, ("চাল",), ("chal", "chawal", "rice"), "grain"),
    Entry("lentils", Category.INGREDIENT, ("ডাল",), ("dal", "daal", "lentil", "lentils"), "grain"),
    Entry(
        "flour",
        Category.INGREDIENT,
        ("আটা", "ময়দা", "বেসন"),
        ("atta", "moyda", "maida", "besan", "flour"),
        "flour",
    ),
    Entry(
        "salt",
        Category.INGREDIENT,
        ("নুন", "লবণ"),
        ("nun", "noon", "lobon", "namak", "salt"),
        "salt",
    ),
    Entry("sugar", Category.INGREDIENT, ("চিনি",), ("chini", "cheeni", "sugar"), "sugar"),
    Entry("oil", Category.INGREDIENT, ("তেল",), ("tel", "oil"), "liquid"),
    Entry(
        "mustard oil",
        Category.INGREDIENT,
        ("সরষের তেল",),
        ("sorser tel", "shorsher tel", "sarser tel", "mustard oil"),
        "liquid",
    ),
    Entry("ghee", Category.INGREDIENT, ("ঘি",), ("ghee", "ghi"), "liquid"),
    Entry("water", Category.INGREDIENT, ("জল", "পানি"), ("jol", "pani", "water"), "liquid"),
    Entry("milk", Category.INGREDIENT, ("দুধ",), ("dudh", "doodh", "milk", "दूध"), "liquid"),
    Entry("turmeric", Category.INGREDIENT, ("হলুদ",), ("holud", "haldi", "turmeric"), "spice"),
    Entry(
        "chilli",
        Category.INGREDIENT,
        ("লঙ্কা", "মরিচ"),
        ("lonka", "lanka", "mirch", "chilli", "chili"),
        "spice",
    ),
    Entry(
        "green chilli",
        Category.INGREDIENT,
        ("কাঁচা লঙ্কা",),
        ("kacha lonka", "kachha lonka", "kancha lonka", "green chilli"),
        "spice",
    ),
    Entry(
        "chilli powder",
        Category.INGREDIENT,
        ("লঙ্কার গুঁড়ো", "লঙ্কা গুঁড়ো"),
        ("lonkar guro", "lanka guro", "lonka guro", "chilli powder"),
        "spice",
    ),
    Entry(
        "cumin", Category.INGREDIENT, ("জিরে", "জিরা"), ("jeere", "jeera", "jire", "cumin"), "spice"
    ),
    Entry(
        "whole cumin",
        Category.INGREDIENT,
        ("গোটা জিরে",),
        ("gota jeere", "gota jeera", "whole cumin"),
        "spice",
    ),
    Entry(
        "coriander",
        Category.INGREDIENT,
        ("ধনে", "ধনিয়া"),
        ("dhone", "dhania", "dhaniya", "coriander"),
        "spice",
    ),
    Entry(
        "coriander powder",
        Category.INGREDIENT,
        ("ধনের গুঁড়ো", "ধনে গুঁড়ো"),
        ("dhone guro", "dhania powder", "coriander powder"),
        "spice",
    ),
    Entry(
        "coriander leaves",
        Category.INGREDIENT,
        ("ধনেপাতা", "ধনে পাতা"),
        ("dhonepata", "dhone pata", "coriander leaves"),
        "herb",
    ),
    Entry("onion", Category.INGREDIENT, ("পেঁয়াজ",), ("peyaj", "piyaj", "pyaj", "onion"), "produce"),
    Entry("potato", Category.INGREDIENT, ("আলু",), ("alu", "aloo", "potato"), "produce"),
    Entry("tomato", Category.INGREDIENT, ("টমেটো",), ("tomato", "tometo"), "produce"),
    Entry(
        "tomato paste",
        Category.INGREDIENT,
        ("টমেটো বাটা",),
        ("tomato bata", "tomato paste"),
        "produce",
    ),
    Entry(
        "garlic", Category.INGREDIENT, ("রসুন",), ("roshun", "rasun", "rosun", "garlic"), "produce"
    ),
    Entry("ginger", Category.INGREDIENT, ("আদা",), ("ada", "adrak", "ginger"), "produce"),
    Entry(
        "ginger garlic paste",
        Category.INGREDIENT,
        ("আদা-রসুন বাটা", "আদা রসুন বাটা"),
        ("ada-roshun bata", "ada roshun bata", "ginger garlic paste"),
        "produce",
    ),
    Entry(
        "onion ginger garlic paste",
        Category.INGREDIENT,
        ("পেঁয়াজ-আদা-রসুন বাটা", "পেঁয়াজ আদা রসুন বাটা"),
        ("peyaj-ada-roshun bata", "peyaj ada roshun bata", "onion ginger garlic paste"),
        "produce",
    ),
    Entry(
        "bay leaf",
        Category.INGREDIENT,
        ("তেজপাতা",),
        ("tejpata", "tej patta", "bay leaf", "bay leaves"),
        "spice",
    ),
    Entry(
        "garam masala",
        Category.INGREDIENT,
        ("গরম মশলা", "গরম মসলা"),
        ("garam masala", "garam mosla"),
        "spice",
    ),
    Entry(
        "whole garam masala",
        Category.INGREDIENT,
        ("গোটা গরম মশলা", "গোটা গরম মসলা"),
        ("gota garam masala", "gota garam mosla", "whole garam masala"),
        "spice",
    ),
    Entry("fish", Category.INGREDIENT, ("মাছ",), ("mach", "maach", "fish"), "produce"),
    Entry(
        "chitol fish",
        Category.INGREDIENT,
        ("চিতল মাছ",),
        ("chitol mach", "chital mach", "chitol fish"),
        "produce",
    ),
    Entry("mustard", Category.INGREDIENT, ("সরষে",), ("sorse", "shorshe", "mustard"), "spice"),
)

MEASURE_ENTRIES: tuple[Entry, ...] = (
    Entry(
        "muthi",
        Category.MEASURE,
        ("মুঠো", "মুঠি"),
        ("muthi", "mutho", "muthhi", "mutthi"),
        kind="unit",
        note="handful; never a gram value",
    ),
    Entry(
        "chimti",
        Category.MEASURE,
        ("চিমটি", "চিমটে"),
        ("chimti", "chimte", "chutki", "pinch"),
        kind="unit",
    ),
    Entry(
        "spoon",
        Category.MEASURE,
        ("চামচ",),
        ("chamoch", "chamach", "chamcha", "spoon"),
        kind="unit",
        ambiguous=True,
        options=("tsp", "tbsp"),
        note="plain chamoch is tsp or tbsp; ছোট/বড় resolves it",
    ),
    Entry(
        "tsp",
        Category.MEASURE,
        ("ছোট চামচ",),
        ("tsp", "teaspoon", "choto chamoch", "chhoto chamoch"),
        kind="unit",
    ),
    Entry(
        "tbsp",
        Category.MEASURE,
        ("বড় চামচ",),
        ("tbsp", "tablespoon", "boro chamoch", "bodo chamoch"),
        kind="unit",
    ),
    Entry(
        "cup",
        Category.MEASURE,
        ("কাপ",),
        ("kap", "cup", "कप"),
        kind="unit",
        ambiguous=True,
        options=("tea cup", "measuring cup", "my cup"),
        note="cup type needs a weighing or a choice",
    ),
    Entry("bowl", Category.MEASURE, ("বাটি",), ("bati", "katori", "bowl"), kind="unit"),
    Entry("glass", Category.MEASURE, ("গ্লাস", "গেলাস"), ("glass", "gelas"), kind="unit"),
    Entry("poa", Category.MEASURE, ("পোয়া",), ("poa",), kind="unit"),
    Entry("chhatak", Category.MEASURE, ("ছটাক",), ("chhatak", "chhotak", "chatak"), kind="unit"),
    Entry("ser", Category.MEASURE, ("সের",), ("ser", "seer"), kind="unit"),
    Entry("gram", Category.MEASURE, ("গ্রাম",), ("g", "gm", "gram", "grams"), kind="unit"),
    Entry("kilogram", Category.MEASURE, ("কেজি", "কিলো"), ("kg", "kilo"), kind="unit"),
    Entry("millilitre", Category.MEASURE, ("মিলি",), ("ml",), kind="unit"),
    Entry("litre", Category.MEASURE, ("লিটার",), ("litre", "liter"), kind="unit"),
    Entry("a little", Category.MEASURE, ("সামান্য",), ("saman", "samanaya", "slight"), kind="vague"),
    Entry("a little", Category.MEASURE, ("অল্প",), ("olpo", "alpo"), kind="vague"),
    Entry("a little", Category.MEASURE, ("একটু",), ("ektu", "aktu"), kind="vague"),
    Entry(
        "little by little",
        Category.MEASURE,
        ("অল্প অল্প",),
        ("olpo olpo", "little by little"),
        kind="vague",
    ),
    Entry(
        "as needed",
        Category.MEASURE,
        ("পরিমাণমতো",),
        ("pariman moto", "parimano moto", "as needed"),
        kind="vague",
    ),
    Entry(
        "to taste",
        Category.MEASURE,
        ("স্বাদমতো",),
        ("swad moto", "swadmoto", "to taste"),
        kind="taste",
        to_taste=True,
    ),
    Entry(
        "to taste",
        Category.MEASURE,
        ("জেমন লাগে",),
        ("jemon lage", "jemon lagey"),
        kind="taste",
        to_taste=True,
    ),
    Entry(
        "to taste",
        Category.MEASURE,
        ("যতটা লাগে",),
        ("joto lage", "joto ta lage"),
        kind="taste",
        to_taste=True,
    ),
)

NUMBER_ENTRIES: tuple[Entry, ...] = (
    Entry(
        "1", Category.NUMBER, ("এক", "একটি", "একটা"), ("ek", "ak", "ekta", "akta", "one"), value=1
    ),
    Entry(
        "2",
        Category.NUMBER,
        ("দুই", "দুটি", "দুটো", "দু"),
        ("dui", "dute", "duto", "do", "du", "two"),
        value=2,
    ),
    Entry("3", Category.NUMBER, ("তিন",), ("tin", "teen", "tinte", "three"), value=3),
    Entry("4", Category.NUMBER, ("চার",), ("char", "chaar", "four"), value=4),
    Entry("5", Category.NUMBER, ("পাঁচ",), ("panch", "pach", "paanch", "five"), value=5),
    Entry("6", Category.NUMBER, ("ছয়",), ("chhoy", "choy", "chhe", "six"), value=6),
    Entry("7", Category.NUMBER, ("সাত",), ("saat", "sat", "seven"), value=7),
    Entry("8", Category.NUMBER, ("আট",), ("aat", "aath", "eight"), value=8),
    Entry("9", Category.NUMBER, ("নয়",), ("noy", "nau", "nine"), value=9),
    Entry("10", Category.NUMBER, ("দশ",), ("dosh", "dos", "das", "ten"), value=10),
    Entry("15", Category.NUMBER, ("পনেরো",), ("panero", "paneraw", "fifteen"), value=15),
    Entry("20", Category.NUMBER, ("বিশ",), ("bish", "twenty"), value=20),
    Entry("30", Category.NUMBER, ("তিরিশ",), ("tirish", "thirty"), value=30),
    Entry(
        "0.5",
        Category.NUMBER,
        ("আধা", "আধ", "অর্ধেক"),
        ("adha", "aadha", "adh", "ardhek", "half", "आधा"),
        value=0.5,
    ),
    Entry("1.5", Category.NUMBER, ("দেড়",), ("der", "dedh", "dedha", "one and a half"), value=1.5),
    Entry("2.5", Category.NUMBER, ("আড়াই",), ("arai", "dhai", "dhaai", "two and a half"), value=2.5),
    Entry(
        "add_half",
        Category.NUMBER,
        ("সাড়ে",),
        ("sarhe", "saade", "sade"),
        kind="add_half",
        value=0.5,
        note="modifier: সাড়ে তিন = 3.5; rules combine it with the next number",
    ),
    Entry(
        "pair",
        Category.NUMBER,
        ("একজোড়া",),
        ("ekjora", "ek jora", "one pair"),
        kind="classifier",
        value=1,
        classifier="pair",
    ),
)

DURATION_ENTRIES: tuple[Entry, ...] = (
    Entry(
        "minute",
        Category.DURATION,
        ("মিনিট",),
        ("minute", "minutes", "min", "mins", "minit"),
        kind="unit",
    ),
    Entry(
        "hour",
        Category.DURATION,
        ("ঘণ্টা", "ঘন্টা"),
        ("ghonta", "ghanta", "hour", "hours"),
        kind="unit",
    ),
    Entry(
        "second",
        Category.DURATION,
        ("সেকেন্ড",),
        ("second", "seconds", "sec", "secs", "sekend"),
        kind="unit",
    ),
    Entry(
        "some time",
        Category.DURATION,
        ("কিছুক্ষণ",),
        ("kichukkhon", "kichu kkhon", "a while", "some time"),
        kind="vague",
    ),
    Entry(
        "a short while",
        Category.DURATION,
        ("অল্পক্ষণ",),
        ("olpokkhon", "olpo kkhon", "a short while"),
        kind="vague",
    ),
)

ALL_ENTRIES: tuple[Entry, ...] = (
    INGREDIENT_ENTRIES + MEASURE_ENTRIES + NUMBER_ENTRIES + DURATION_ENTRIES
)

# Conservative suffix handling. Classifiers are grammatical quantity markers
# (``তিনটা`` -> ``তিন`` + classifier ``টা``); the genitive ``ের`` is needed for
# fixture forms such as ``মাছের``. Longest suffix is tried first.
CLASSIFIER_SUFFIXES: tuple[str, ...] = (
    "গুলো",
    "গুলি",
    "খানা",
    "টুকু",
    "টা",
    "টি",
    "gulo",
    "guli",
    "khana",
    "tuku",
    "ta",
    "ti",
)
CASE_SUFFIXES: tuple[str, ...] = ("ের",)

_DECIMAL = re.compile(r"\d+(?:\.\d+)?$")
_FRACTION = re.compile(r"(\d+)/(\d+)$")


def _sorted_suffixes(suffixes: Iterable[str]) -> tuple[str, ...]:
    """Longest first, then stable so results never depend on dict order."""
    return tuple(sorted(suffixes, key=lambda suffix: (-len(suffix), suffix)))


class Lexicon:
    """Deterministic lookup over the vocabulary tables.

    The object is immutable after construction; repeated lookups always return
    equal results for equal input.
    """

    def __init__(self, entries: Sequence[Entry] = ALL_ENTRIES) -> None:
        self.entries = tuple(entries)
        self._forms: dict[str, tuple[Entry, str]] = {}
        self._numbers: dict[str, float] = {}
        self._phrases: dict[int, list[tuple[tuple[str, ...], Entry]]] = {}
        max_phrase = 0
        for entry in self.entries:
            for form in entry.surface_forms:
                self._register(form, entry, METHOD_EXACT)
            for form in entry.aliases:
                self._register(form, entry, METHOD_ALIAS)
            if entry.category is Category.NUMBER and entry.kind is None and entry.value is not None:
                for form in entry.all_forms:
                    self._numbers.setdefault(form.lower(), entry.value)
            for form in entry.all_forms:
                if " " in form:
                    phrase = tuple(form.lower().split())
                    self._register_phrase(phrase, entry)
                    max_phrase = max(max_phrase, len(phrase))
        self._max_phrase = max_phrase
        self._classifier_suffixes = _sorted_suffixes(CLASSIFIER_SUFFIXES)
        self._case_suffixes = _sorted_suffixes(CASE_SUFFIXES)

    def _register(self, form: str, entry: Entry, method: str) -> None:
        key = form.lower()
        existing = self._forms.get(key)
        if existing is not None and existing[0] is not entry:
            raise ValueError(
                f"conflicting lexicon form {form!r}: {existing[0].canonical!r} and {entry.canonical!r}"
            )
        self._forms[key] = (entry, method)

    def _register_phrase(self, phrase: tuple[str, ...], entry: Entry) -> None:
        bucket = self._phrases.setdefault(len(phrase), [])
        for existing, existing_entry in bucket:
            if existing == phrase and existing_entry is not entry:
                raise ValueError(
                    f"conflicting lexicon phrase {' '.join(phrase)!r}: "
                    f"{existing_entry.canonical!r} and {entry.canonical!r}"
                )
        bucket.append((phrase, entry))

    # -- single token ------------------------------------------------------- #

    def lookup(self, token: str) -> Match | None:
        """Look up one token: exact, alias, numeric, then suffix-stripped."""
        text = token.lower()
        hit = self._forms.get(text)
        if hit is not None:
            return self._make(hit[0], text, hit[1], 0, 1)
        numeric = self._parse_number(text)
        if numeric is not None:
            return numeric
        stripped = self._strip_suffix(text)
        if stripped is not None:
            stem, classifier = stripped
            entry, _ = self._forms[stem]
            return self._make(entry, text, METHOD_SUFFIX, 0, 1, classifier=classifier)
        return None

    def suggest(self, token: str, *, cutoff: float = 0.85, limit: int = 3) -> tuple[Match, ...]:
        """Return fuzzy candidates for a mistyped Roman/English token.

        This is a *suggestion* API only. It never accepts a match by itself and
        it is never used by :meth:`find`, so a similar-looking word cannot be
        silently turned into a different ingredient, quantity or measurement.
        """
        text = token.lower()
        if not (text.isascii() and text.isalpha() and len(text) >= 4):
            return ()
        scored: list[tuple[float, str, Entry]] = []
        for form, (entry, _method) in self._forms.items():
            if not (form.isascii() and form.isalpha() and len(form) >= 4):
                continue
            ratio = difflib.SequenceMatcher(None, text, form).ratio()
            if ratio >= cutoff:
                scored.append((ratio, form, entry))
        scored.sort(key=lambda item: (-item[0], item[1]))
        chosen: list[tuple[float, str, Entry]] = []
        seen: set[str] = set()
        for ratio, form, entry in scored:
            if entry.canonical in seen:
                continue
            seen.add(entry.canonical)
            chosen.append((ratio, form, entry))
            if len(chosen) >= limit:
                break
        ambiguous = len(chosen) > 1
        return tuple(
            self._make(
                entry, text, METHOD_FUZZY, 0, 1, confidence=round(ratio, 4), ambiguous=ambiguous
            )
            for ratio, _form, entry in chosen
        )

    # -- token sequences ---------------------------------------------------- #

    def find(self, tokens: Sequence[str]) -> tuple[Match, ...]:
        """Scan a token sequence, longest phrase first, non-overlapping.

        Returns matches with token-index spans. Unknown tokens are skipped and
        keep their position; the input is never modified.
        """
        matches: list[Match] = []
        index = 0
        count = len(tokens)
        while index < count:
            match = self._match_at(tokens, index)
            if match is None:
                index += 1
                continue
            matches.append(match)
            index = match.token_end
        return tuple(matches)

    def find_in(self, normalized: NormalizedText) -> tuple[Match, ...]:
        """Scan a :class:`NormalizedText` and attach char + original spans."""
        tokens = normalized.tokens
        matches: list[Match] = []
        for match in self.find([token.text for token in tokens]):
            first: Token = tokens[match.token_start]
            last: Token = tokens[match.token_end - 1]
            matches.append(
                replace(
                    match,
                    surface=normalized.original[first.orig_start : last.orig_end],
                    char_start=first.start,
                    char_end=last.end,
                    orig_start=first.orig_start,
                    orig_end=last.orig_end,
                )
            )
        return tuple(matches)

    def entries_for(self, category: Category) -> tuple[Entry, ...]:
        """All entries in one vocabulary group, in table order."""
        return tuple(entry for entry in self.entries if entry.category is category)

    # -- internals ---------------------------------------------------------- #

    def _match_at(self, tokens: Sequence[str], index: int) -> Match | None:
        remaining = len(tokens) - index
        for length in range(min(self._max_phrase, remaining), 1, -1):
            for phrase, entry in self._phrases.get(length, ()):
                if all(
                    self._token_matches(tokens[index + offset], phrase[offset])
                    for offset in range(length)
                ):
                    surface = " ".join(tokens[index : index + length])
                    return self._make(entry, surface, METHOD_PHRASE, index, index + length)
        single = self.lookup(tokens[index])
        if single is None:
            return None
        return replace(single, surface=tokens[index], token_start=index, token_end=index + 1)

    def _token_matches(self, token: str, surface: str) -> bool:
        text = token.lower()
        if text == surface:
            return True
        stripped = self._strip_suffix(text)
        return stripped is not None and stripped[0] == surface

    def _strip_suffix(self, token: str) -> tuple[str, str | None] | None:
        """Return ``(stem, classifier)`` if a conservative suffix is safe.

        A suffix is only removed when the remaining stem is itself a known
        vocabulary form, so stripping can never manufacture a match.
        """
        for suffix in self._classifier_suffixes:
            if self._can_strip(token, suffix):
                stem = token[: -len(suffix)]
                if stem in self._forms:
                    return stem, suffix
        for suffix in self._case_suffixes:
            if self._can_strip(token, suffix):
                stem = token[: -len(suffix)]
                if stem in self._forms:
                    return stem, None
        return None

    @staticmethod
    def _can_strip(token: str, suffix: str) -> bool:
        return len(token) > len(suffix) + 1 and token.endswith(suffix)

    def _parse_number(self, token: str) -> Match | None:
        if "-" in token:
            left, sep, right = token.partition("-")
            if sep:
                low = self._number_value(left)
                high = self._number_value(right)
                if low is not None and high is not None:
                    return Match(
                        surface=token,
                        canonical=f"{_fmt(low)}-{_fmt(high)}",
                        category=Category.NUMBER,
                        method=METHOD_NUMERIC,
                        token_start=0,
                        token_end=1,
                        value=low,
                        value_max=high,
                    )
        fraction = _FRACTION.match(token)
        if fraction is not None:
            denominator = int(fraction.group(2))
            if denominator != 0:
                value = int(fraction.group(1)) / denominator
                return self._numeric(token, value)
        if _DECIMAL.match(token):
            return self._numeric(token, float(token))
        return None

    def _number_value(self, part: str) -> float | None:
        known = self._numbers.get(part.lower())
        if known is not None:
            return known
        if _DECIMAL.match(part):
            return float(part)
        return None

    def _numeric(self, token: str, value: float) -> Match:
        return Match(
            surface=token,
            canonical=_fmt(value),
            category=Category.NUMBER,
            method=METHOD_NUMERIC,
            token_start=0,
            token_end=1,
            value=value,
        )

    def _make(
        self,
        entry: Entry,
        surface: str,
        method: str,
        token_start: int,
        token_end: int,
        *,
        classifier: str | None = None,
        confidence: float = 1.0,
        ambiguous: bool | None = None,
    ) -> Match:
        return Match(
            surface=surface,
            canonical=entry.canonical,
            category=entry.category,
            method=method,
            token_start=token_start,
            token_end=token_end,
            entry=entry,
            confidence=confidence,
            ambiguous=entry.ambiguous if ambiguous is None else ambiguous,
            options=entry.options,
            value=entry.value,
            classifier=classifier if classifier is not None else entry.classifier,
            to_taste=entry.to_taste,
            kind=entry.kind,
        )


def _fmt(value: float) -> str:
    """Canonical string for a number: integers without ``.0``, else trimmed."""
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


def default_lexicon() -> Lexicon:
    """Build the shared lexicon from the module vocabulary tables."""
    return Lexicon(ALL_ENTRIES)


LEXICON = default_lexicon()
