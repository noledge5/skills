"""Broker registry.

Loads declarative metadata from ``brokers/registry.yaml`` and pairs each entry
with the right :class:`Broker` implementation:

* if a bespoke subclass is registered for the slug (via :func:`register`),
  that class is used (``automated`` brokers with custom parsing);
* otherwise a :class:`DeclarativeBroker` is created from the metadata.

Adding a new broker therefore means *at most* adding one YAML entry, and only
optionally a Python file — satisfying the "no core changes" requirement.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

import yaml

from .core.broker import Broker, DeclarativeBroker
from .models import BrokerMeta

_REGISTRY_PATH = Path(__file__).parent / "brokers" / "registry.yaml"

# slug -> Broker subclass, populated by the @register decorator.
_CUSTOM: dict[str, type[Broker]] = {}


def register(cls: type[Broker]) -> type[Broker]:
    """Class decorator to bind a bespoke Broker subclass to its metadata slug.

    The subclass must define a ``SLUG`` attribute matching a registry entry.
    """
    slug = getattr(cls, "SLUG", None)
    if not slug:
        raise ValueError(f"{cls.__name__} must define a SLUG to be registered")
    _CUSTOM[slug] = cls
    return cls


def _discover_custom_brokers() -> None:
    """Import every module under ``brokers/automated`` so decorators run."""
    pkg_name = f"{__package__}.brokers.automated"
    try:
        pkg = importlib.import_module(pkg_name)
    except ModuleNotFoundError:
        return
    for mod in pkgutil.iter_modules(pkg.__path__):
        importlib.import_module(f"{pkg_name}.{mod.name}")


def load_registry(path: Path | None = None) -> list[BrokerMeta]:
    """Parse and validate all broker metadata from YAML."""
    path = path or _REGISTRY_PATH
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return [BrokerMeta.model_validate(entry) for entry in raw]


def load_brokers(*, enabled_only: bool = True, path: Path | None = None) -> list[Broker]:
    """Return instantiated brokers, custom subclass where available."""
    _discover_custom_brokers()
    brokers: list[Broker] = []
    for meta in load_registry(path):
        if enabled_only and not meta.enabled:
            continue
        cls = _CUSTOM.get(meta.slug, DeclarativeBroker)
        brokers.append(cls(meta))
    return brokers
