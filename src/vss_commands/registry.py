from __future__ import annotations

import importlib
import pkgutil
from typing import Iterable

from .models import CommandMetadata, RegisteredCommand

_commands: dict[str, RegisteredCommand] = {}
_discovered = False


def register(metadata: CommandMetadata):
    """Register a command handler; command modules use this decorator."""

    def decorator(handler):
        if metadata.name in _commands:
            raise RuntimeError(f"duplicate command registration: {metadata.name}")
        _commands[metadata.name] = RegisteredCommand(metadata, handler)
        return handler

    return decorator


def discover_commands() -> None:
    global _discovered
    if _discovered:
        return
    from . import commands

    for module in sorted(pkgutil.iter_modules(commands.__path__), key=lambda item: item.name):
        if not module.name.startswith("_"):
            importlib.import_module(f"{commands.__name__}.{module.name}")
    _discovered = True


def get_command(name: str) -> RegisteredCommand | None:
    discover_commands()
    return _commands.get(name)


def list_commands() -> Iterable[CommandMetadata]:
    discover_commands()
    return tuple(_commands[name].metadata for name in sorted(_commands))
