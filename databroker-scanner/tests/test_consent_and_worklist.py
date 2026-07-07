import pytest

from databroker_scanner.consent import STATEMENT_VERSION, ConsentRequired, ensure_consent
from databroker_scanner.models import MatchStatus, Person
from databroker_scanner.registry import load_brokers
from databroker_scanner.storage.db import Database


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "t.db")
    yield database
    database.close()


def test_consent_required_when_declined(db):
    with pytest.raises(ConsentRequired):
        ensure_consent(db, prompt=lambda _: "no")
    assert not db.has_consent(STATEMENT_VERSION)


def test_consent_recorded_when_agreed(db):
    ensure_consent(db, prompt=lambda _: "I AGREE")
    assert db.has_consent(STATEMENT_VERSION)


def test_consent_assume_yes_is_recorded(db):
    ensure_consent(db, assume_yes=True)
    assert db.has_consent(STATEMENT_VERSION)


def test_optout_only_broker_produces_optout_record():
    broker = next(b for b in load_brokers() if b.meta.mode.value == "optout_only")
    match = broker.optout_match(Person(firstname="Jane", lastname="Doe"))
    assert match.status is MatchStatus.OPTOUT_ONLY
    assert match.optout_url


def test_run_roundtrip_persists_matches(db):
    ensure_consent(db, assume_yes=True)
    person = Person(firstname="Jane", lastname="Doe")
    pid = db.add_person(person)
    run_id = db.start_run(pid, "{}")
    for broker in load_brokers():
        db.add_match(run_id, broker.optout_match(person))
    db.finish_run(run_id)
    rows = db.matches_for_run(run_id)
    assert len(rows) == len(load_brokers())
    assert db.latest_run_id() == run_id
