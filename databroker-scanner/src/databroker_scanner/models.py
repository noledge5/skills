"""Core domain models.

All models are Pydantic v2 so that config/registry parsing and validation are
handled uniformly and fail early with clear messages.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


def _utcnow() -> datetime:
    return datetime.now(UTC)


class BrokerMode(str, Enum):
    """How a broker may be interacted with, given its robots.txt/ToS posture."""

    AUTOMATED = "automated"      # robots.txt permits automated fetch + parse
    ASSISTED = "assisted"        # human-in-the-loop in a visible browser; no evasion
    OPTOUT_ONLY = "optout_only"  # no scan at all; curated opt-out deep link only


class OptOutType(str, Enum):
    FORM = "form"
    EMAIL = "email"
    ACCOUNT = "account"
    POSTAL = "postal"
    LINK = "link"          # a landing page describing the process


class MatchStatus(str, Enum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    NEEDS_REVIEW = "needs_review"  # assisted mode: awaiting human confirmation
    BLOCKED = "blocked"            # site refused automation — respected, not bypassed
    SKIPPED = "skipped"            # tier not yet supported / disabled
    OPTOUT_ONLY = "optout_only"    # informational opt-out record, no scan performed


class ConfidenceBand(str, Enum):
    LIKELY = "likely"
    POSSIBLE = "possible"
    UNLIKELY = "unlikely"


class Person(BaseModel):
    """The subject of a self-audit. Only populated fields are used in searches."""

    firstname: str | None = None
    lastname: str | None = None
    middlename: str | None = None
    phone: str | None = None
    email: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    zipcode: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def _blank_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    def provided_fields(self) -> dict[str, str]:
        """Return only the fields the user actually supplied (non-empty)."""
        return {k: v for k, v in self.model_dump().items() if v}

    def full_name(self) -> str:
        parts = [self.firstname, self.middlename, self.lastname]
        return " ".join(p for p in parts if p)


class BrokerMeta(BaseModel):
    """Declarative metadata for a broker, mirrored from registry.yaml."""

    slug: str
    name: str
    website: str
    country: str
    category: str
    mode: BrokerMode
    search_url_template: str | None = None
    optout_url: str
    optout_type: OptOutType = OptOutType.LINK
    requires_captcha: bool = False
    requires_login: bool = False
    enabled: bool = True
    # Whether the opt-out URL has been human-verified. Unverified entries are
    # surfaced with a warning so users are never silently sent to a wrong page.
    verified: bool = False
    notes: str | None = None


class Match(BaseModel):
    """A single result recorded for one broker within a scan run."""

    broker_slug: str
    broker_name: str
    status: MatchStatus
    profile_name: str | None = None
    profile_url: str | None = None
    search_term: str | None = None
    screenshot_path: str | None = None
    optout_url: str | None = None
    optout_type: OptOutType | None = None
    confidence: int = 0                # 0..100
    confidence_band: ConfidenceBand = ConfidenceBand.UNLIKELY
    found_at: datetime = Field(default_factory=_utcnow)


class ScanRun(BaseModel):
    id: int | None = None
    person: Person
    started_at: datetime = Field(default_factory=_utcnow)
    finished_at: datetime | None = None
    status: str = "running"
    config_snapshot: dict = Field(default_factory=dict)
