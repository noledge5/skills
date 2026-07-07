"""Bespoke ``automated``-mode broker implementations.

Drop a module here that defines a :class:`~databroker_scanner.core.broker.Broker`
subclass decorated with ``@register`` and a matching ``SLUG``. It is discovered
automatically — no changes to the core are needed. None exist yet: promoting a
broker to ``automated`` requires confirming its robots.txt permits the fetch.
"""
