from __future__ import annotations

from types import SimpleNamespace
from typing import Any


class _FakeTensor:
    def permute(self, *_args: Any) -> _FakeTensor:
        return self

    def unsqueeze(self, _dimension: int) -> _FakeTensor:
        return self

    def to(self, **_kwargs: Any) -> _FakeTensor:
        return self

    def __truediv__(self, _divisor: float) -> _FakeTensor:
        return self


class _FakeCuda:
    class OutOfMemoryError(RuntimeError):
        pass

    cleared = False

    @classmethod
    def empty_cache(cls) -> None:
        cls.cleared = True


class _InferenceMode:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *_args: Any) -> bool:
        return False


def make_oom_torch() -> tuple[Any, Any, type[_FakeCuda]]:
    _FakeCuda.cleared = False

    def fail_oom(_tensor: Any) -> None:
        raise _FakeCuda.OutOfMemoryError("out of memory")

    fake_torch = SimpleNamespace(
        cuda=_FakeCuda,
        float32=object(),
        from_numpy=lambda _array: _FakeTensor(),
        inference_mode=lambda: _InferenceMode(),
    )
    return fake_torch, fail_oom, _FakeCuda


__all__ = ["make_oom_torch"]
