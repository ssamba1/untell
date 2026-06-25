"""Tiered AI-text detector adapters behind a common protocol.

Importing this package never imports heavy ML dependencies. Each adapter guards its own
imports inside ``available()`` / ``score()`` so that, with nothing but the standard library
installed, only the ``lite`` detectors load and the rest report themselves unavailable.
"""

from .base import Detector, Tier, load_detectors

__all__ = ["Detector", "Tier", "load_detectors"]
