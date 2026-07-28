"""PyTorch-backed algorithm implementations.

Algorithms are partitioned by tensor backend so that
``app.algorithms.paddle.*`` and ``app.algorithms.pytorch.*`` can coexist
in the source tree without their dependency closures (cudnn, paddle.fluid
…) being pulled into the same Python process at import time.

This package itself stays **side-effect-free**: it does not import
``torch`` at module level and does not auto-register algorithms. Each
sub-package (e.g. ``pytorch.rife``) decides for itself when to import
PyTorch, mirroring the lazy ``__getattr__`` pattern documented in
``pytorch/rife/__init__.py``.
"""
