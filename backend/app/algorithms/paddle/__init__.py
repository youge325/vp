"""Paddle-backed algorithm implementations.

Paddle implementations live in backend-specific subpackages such as
``paddlegan_vsr``. The package boundary ensures that:

1. The tree layout already encodes the "PyTorch / Paddle never coexist
   in the same Python process" constraint (the test harness in
   ``backend/tests/conftest.py`` enforces it at collection time).
2. Algorithm metadata can declare ``tensorBackends: ["paddle"]`` without
   importing Paddle into the parent package.

This module is **side-effect-free**: importing it does not pull in
``paddle`` (which would conflict with ``torch`` over cudnn DLL
ownership on Windows — see ``conftest.py`` for the longer story).
"""
