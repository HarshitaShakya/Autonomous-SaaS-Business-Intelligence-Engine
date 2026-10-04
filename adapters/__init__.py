"""Adapter registry.

Each adapter module exposes a ``load(path) -> list[CanonicalRecord]`` function.
The registry maps human-readable source names to their loader so the pipeline
can auto-detect or manually select the right one.

To add a new source
-------------------
1. Create ``adapters/<source_name>_adapter.py`` with a ``load()`` function.
2. Import and register it in this ``__init__.py``.
"""

from __future__ import annotations

from typing import Callable

from pathlib import Path

from schemas.canonical import CanonicalRecord

# Registry: source_name -> load function
_ADAPTER_REGISTRY: dict[str, Callable[[str | Path], list[CanonicalRecord]]] = {}


def register(name: str) -> Callable:
    """Decorator that registers an adapter's ``load`` function."""

    def wrapper(fn: Callable[[str | Path], list[CanonicalRecord]]) -> Callable:
        _ADAPTER_REGISTRY[name] = fn
        return fn

    return wrapper


def get_adapter(name: str) -> Callable[[str | Path], list[CanonicalRecord]]:
    """Retrieve a registered adapter by name.

    Raises
    ------
    KeyError
        If no adapter with that name has been registered.
    """
    if name not in _ADAPTER_REGISTRY:
        available = ", ".join(_ADAPTER_REGISTRY.keys()) or "(none)"
        raise KeyError(
            f"No adapter registered as '{name}'. Available: {available}"
        )
    return _ADAPTER_REGISTRY[name]


def list_adapters() -> list[str]:
    """Return names of all registered adapters."""
    return list(_ADAPTER_REGISTRY.keys())


# ------------------------------------------------------------------
# Auto-import all adapter modules so their @register decorators fire
# ------------------------------------------------------------------
from adapters import telco_churn_adapter as _telco  # noqa: F401, E402
