"""Consent gate.

Because the tool can technically look up anyone, the first action in any scan
is an explicit, recorded acknowledgement that the user is auditing their own
data (or has a documented lawful basis). This is a guardrail against turning a
self-audit into a doxxing tool — enforced in code, not just documented.
"""

from __future__ import annotations

STATEMENT_VERSION = "2026-07-07"

STATEMENT = (
    "I confirm that I am searching for MY OWN personal data, or that I have a\n"
    "documented lawful basis and the consent of the person concerned.\n"
    "I will use the results only to request removal / opt-out of my data.\n"
    "This tool does not bypass logins, CAPTCHAs or bot-protection, and only\n"
    "collects publicly accessible information."
)


class ConsentRequired(RuntimeError):
    """Raised when a scan is attempted without recorded consent."""


def ensure_consent(db, *, assume_yes: bool = False, prompt=input) -> None:
    """Ensure consent is recorded for the current statement version.

    Parameters
    ----------
    db:
        A :class:`~databroker_scanner.storage.db.Database` instance.
    assume_yes:
        Non-interactive acceptance (e.g. ``--yes`` flag). Still recorded.
    prompt:
        Injectable input function (eases testing).
    """
    if db.has_consent(STATEMENT_VERSION):
        return
    if assume_yes:
        db.record_consent(STATEMENT_VERSION)
        return
    answer = prompt(f"{STATEMENT}\n\nType 'I AGREE' to continue: ").strip()
    if answer.upper() != "I AGREE":
        raise ConsentRequired("Consent was not given; aborting.")
    db.record_consent(STATEMENT_VERSION)
