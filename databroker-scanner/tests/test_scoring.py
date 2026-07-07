from databroker_scanner.models import ConfidenceBand, Person
from databroker_scanner.scoring import Candidate, score


def test_exact_name_and_city_is_likely():
    person = Person(firstname="Jane", lastname="Doe", city="Austin", state="TX")
    cand = Candidate(firstname="Jane", lastname="Doe", city="Austin", state="TX")
    value, band = score(person, cand)
    assert value == 100
    assert band is ConfidenceBand.LIKELY


def test_wrong_lastname_is_unlikely():
    person = Person(firstname="Jane", lastname="Doe", city="Austin")
    cand = Candidate(firstname="Jane", lastname="Smith", city="Dallas")
    value, band = score(person, cand)
    assert band is ConfidenceBand.UNLIKELY
    assert value < 40


def test_first_initial_partial_credit():
    person = Person(firstname="Jonathan", lastname="Doe")
    cand = Candidate(firstname="Joseph", lastname="Doe")  # same initial only
    value, _ = score(person, cand)
    # lastname (35) + first-initial (10) out of 60 possible -> 75
    assert value == 75


def test_only_provided_fields_count():
    person = Person(lastname="Doe")  # sparse query
    cand = Candidate(lastname="Doe", city="Nowhere")
    value, band = score(person, cand)
    assert value == 100
    assert band is ConfidenceBand.LIKELY


def test_phone_digits_normalised():
    person = Person(lastname="Doe", phone="(512) 555-0100")
    cand = Candidate(lastname="Doe", phones=["512.555.0100"])
    value, _ = score(person, cand)
    assert value == 100
