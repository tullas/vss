"""Schema-validated, environment-aware configuration for VSS."""

from .loader import ConfigError, load_configuration, render_configuration

__all__ = ["ConfigError", "load_configuration", "render_configuration"]
