"""Broker abstraction.

A broker is defined primarily by declarative metadata (:class:`BrokerMeta`).
Only brokers in ``automated`` mode that need real HTML parsing require a
bespoke Python subclass; ``assisted`` and ``optout_only`` brokers are fully
served by :class:`DeclarativeBroker`.
"""

from __future__ import annotations

from abc import ABC
from urllib.parse import quote_plus

from ..models import BrokerMeta, Match, MatchStatus, Person


class Broker(ABC):
    """Base class for all brokers. Subclass only when custom parsing is needed."""

    def __init__(self, meta: BrokerMeta) -> None:
        self.meta = meta

    @property
    def slug(self) -> str:
        return self.meta.slug

    @property
    def name(self) -> str:
        return self.meta.name

    def build_search_url(self, person: Person) -> str | None:
        """Fill the search-URL template with the person's provided fields.

        Missing fields are substituted with an empty string; brokers whose
        template needs a field the user did not provide return ``None``.
        """
        template = self.meta.search_url_template
        if not template:
            return None
        fields = {
            "firstname": person.firstname or "",
            "lastname": person.lastname or "",
            "middlename": person.middlename or "",
            "city": person.city or "",
            "state": person.state or "",
            "zipcode": person.zipcode or "",
            "phone": person.phone or "",
            "email": person.email or "",
        }
        try:
            return template.format(**{k: quote_plus(v) for k, v in fields.items()})
        except KeyError:
            return None

    def optout_match(self, person: Person) -> Match:
        """Build the informational opt-out record (no scan performed)."""
        return Match(
            broker_slug=self.slug,
            broker_name=self.name,
            status=MatchStatus.OPTOUT_ONLY,
            search_term=person.full_name() or None,
            optout_url=self.meta.optout_url,
            optout_type=self.meta.optout_type,
        )


class DeclarativeBroker(Broker):
    """Generic broker driven entirely by metadata.

    Used for ``optout_only`` brokers (Phase 1) and simple ``assisted`` brokers
    (Phase 2), where behaviour is fully described by :class:`BrokerMeta`.
    """
