"""PaddleGAN video super-resolution integration.

The runtime code in this package is self-contained under the VP backend. It
must not import an external ``ppgan`` package or a local PaddleGAN checkout.
"""

from app.algorithms.paddle.paddlegan_vsr.weights import PADDLEGAN_VSR_SPECS

__all__ = ["PADDLEGAN_VSR_SPECS"]
