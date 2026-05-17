"""Paddle-backed algorithm implementations.

Phase 8 — placeholder package reserved for future paddle-side algorithm
implementations (paddle-RIFE, paddle super-resolution etc.). Today there
are no algorithms here; the package exists so that:

1. The tree layout already encodes the "PyTorch / Paddle never coexist
   in the same Python process" constraint (the test harness in
   ``backend/tests/conftest.py`` enforces it at collection time).
2. ``backend/app/processing/interpolation.py::SUPPORTED_ALGORITHMS`` can
   declare ``tensorBackends: ["paddle"]`` for future entries without
   needing to also relocate code.

This module is **side-effect-free**: importing it does not pull in
``paddle`` (which would conflict with ``torch`` over cudnn DLL
ownership on Windows — see ``conftest.py`` for the longer story).
"""

from __future__ import annotations

__all__: list[str] = []
