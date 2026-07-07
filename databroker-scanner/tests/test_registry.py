from databroker_scanner.core.broker import Broker
from databroker_scanner.models import BrokerMode, Person
from databroker_scanner.registry import load_brokers, load_registry


def test_registry_loads_and_validates():
    metas = load_registry()
    assert len(metas) > 20
    slugs = [m.slug for m in metas]
    assert len(slugs) == len(set(slugs)), "broker slugs must be unique"
    assert "spokeo" in slugs
    assert "schufa" in slugs


def test_no_broker_is_automated_in_v1():
    # Promotion to automated requires a robots.txt check; none yet.
    assert all(m.mode is not BrokerMode.AUTOMATED for m in load_registry())


def test_load_brokers_returns_broker_instances():
    brokers = load_brokers()
    assert brokers and all(isinstance(b, Broker) for b in brokers)


def test_numeric_slug_is_a_string_not_a_module():
    # "11880" would be an invalid Python module name; it lives as data instead.
    slugs = {m.slug for m in load_registry()}
    assert "11880" in slugs


def test_search_url_templating():
    broker = next(b for b in load_brokers() if b.slug == "fastpeoplesearch")
    url = broker.build_search_url(Person(firstname="Jane", lastname="Doe"))
    assert url is not None
    assert "Jane" in url and "Doe" in url
