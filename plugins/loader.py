"""Minimal plugin discovery (Hermes plugins/ counterpart)."""
from __future__ import annotations

import importlib
import pkgutil
from typing import List


def discover_plugins() -> List[str]:
    """Return importable plugin module names under plugins.*."""
    import plugins

    found = []
    if not hasattr(plugins, "__path__"):
        return found
    for m in pkgutil.iter_modules(plugins.__path__, plugins.__name__ + "."):
        if m.name.endswith(".loader"):
            continue
        found.append(m.name)
    return found


def load_plugins() -> List[str]:
    loaded = []
    for name in discover_plugins():
        try:
            importlib.import_module(name)
            loaded.append(name)
        except Exception:
            continue
    return loaded
