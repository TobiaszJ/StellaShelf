"""StellaShelf — Astrophotography Digital Asset Manager & Processing Hub."""

__version__ = "0.5.0"

try:
    from stellashelf._build import __build__  # noqa: F401
except ImportError:
    __build__ = "dev"
