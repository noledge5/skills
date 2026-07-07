"""Confidence scoring for candidate profiles.

A match's confidence is a weighted sum of corroborating signals between the
subject (:class:`Person`) and a candidate profile extracted from a broker.
Kept dependency-free and pure so it is trivial to unit-test.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import ConfidenceBand, Person

# Signal weights (sum of all achievable weights is normalised to 100).
_W_LASTNAME = 35
_W_FIRSTNAME = 25
_W_FIRSTNAME_INITIAL = 10
_W_CITY = 15
_W_STATE = 10
_W_ZIP = 15
_W_PHONE = 25
_W_EMAIL = 25

_LIKELY_THRESHOLD = 70
_POSSIBLE_THRESHOLD = 40


@dataclass
class Candidate:
    """Normalised fields extracted from a broker profile for scoring."""

    firstname: str | None = None
    lastname: str | None = None
    city: str | None = None
    state: str | None = None
    zipcode: str | None = None
    phones: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def _digits(value: str | None) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def score(person: Person, candidate: Candidate) -> tuple[int, ConfidenceBand]:
    """Return ``(0..100, band)`` for how well ``candidate`` matches ``person``.

    Only signals the user actually provided contribute to the denominator, so a
    sparse query (e.g. just first + last name) is not unfairly penalised.
    """
    earned = 0
    possible = 0

    if person.lastname:
        possible += _W_LASTNAME
        if _norm(person.lastname) == _norm(candidate.lastname):
            earned += _W_LASTNAME

    if person.firstname:
        possible += _W_FIRSTNAME
        pf, cf = _norm(person.firstname), _norm(candidate.firstname)
        if pf and pf == cf:
            earned += _W_FIRSTNAME
        elif pf and cf and pf[0] == cf[0]:
            earned += _W_FIRSTNAME_INITIAL

    if person.city:
        possible += _W_CITY
        if _norm(person.city) == _norm(candidate.city):
            earned += _W_CITY

    if person.state:
        possible += _W_STATE
        if _norm(person.state) == _norm(candidate.state):
            earned += _W_STATE

    if person.zipcode:
        possible += _W_ZIP
        if _digits(person.zipcode) and _digits(person.zipcode) == _digits(candidate.zipcode):
            earned += _W_ZIP

    if person.phone:
        possible += _W_PHONE
        pd = _digits(person.phone)
        if pd and any(pd == _digits(p) for p in candidate.phones):
            earned += _W_PHONE

    if person.email:
        possible += _W_EMAIL
        pe = _norm(person.email)
        if pe and any(pe == _norm(e) for e in candidate.emails):
            earned += _W_EMAIL

    if possible == 0:
        return 0, ConfidenceBand.UNLIKELY

    value = round(earned / possible * 100)
    if value >= _LIKELY_THRESHOLD:
        band = ConfidenceBand.LIKELY
    elif value >= _POSSIBLE_THRESHOLD:
        band = ConfidenceBand.POSSIBLE
    else:
        band = ConfidenceBand.UNLIKELY
    return value, band
