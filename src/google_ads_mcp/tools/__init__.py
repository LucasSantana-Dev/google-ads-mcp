"""Tool registry.

Each tool lives in its own module exposing ``register(mcp)``. ``register_all`` discovers and
calls them, so adding a tool module requires no edits to shared files (keeps modules disjoint).
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any


def register_all(mcp: Any) -> list[str]:
    """Import every non-underscore submodule and call its ``register(mcp)``.

    Returns the sorted names of modules that registered tools.
    """
    registered: list[str] = []
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{info.name}")
        register = getattr(module, "register", None)
        if callable(register):
            register(mcp)
            registered.append(info.name)
    return sorted(registered)
