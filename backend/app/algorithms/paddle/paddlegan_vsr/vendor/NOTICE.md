This directory vendors the minimal PaddleGAN source subset required for VP's
native video super-resolution integration.

Source: https://github.com/PaddlePaddle/PaddleGAN
License: Apache License 2.0

Copied components:
- `ppgan/models/generators/{basicvsr,edvr,iconvsr,basicvsr_plus_plus,msvsr,builder}.py`
- `ppgan/modules/init.py`
- `ppgan/utils/{download,logger,registry}.py`

Only VP integration code should import this vendored package. Runtime code must
not import an external `ppgan` package or a local PaddleGAN checkout.
