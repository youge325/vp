"""Compact spec table for the 36 supported RIFE checkpoints.

Phase C.1.2 replaced the 250-line hand-written ``MODEL_CONFIGS`` dict in
``model_loader.py`` with a frozen-dataclass + grouped tuple list defined
here. The legacy dict form ``MODEL_CONFIGS`` is still derived and exported
verbatim because external callers (``onnx_export``, ``onnx_solver``,
tests) read fields like ``MODEL_CONFIGS[v]["head_type"]``.

Adding a new model version means appending one line to ``_VERSION_GROUPS``
— no boilerplate, no extra dict literal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Head type constants — also re-exported by ``model_loader`` so external
# code can keep importing them from there.
HEAD_NONE = "none"  # No Head encoder (v4.0 ~ v4.6)
HEAD_SEQUENTIAL = "sequential"  # nn.Sequential Head (v4.7 ~ v4.13.lite)
HEAD_CUSTOM = "custom"  # Custom Head class imported from the IFNet file


@dataclass(frozen=True)
class RifeModelSpec:
    """Immutable spec for one RIFE checkpoint.

    The 4 mandatory fields are what the loader / IFNet wrapper care about:
    - ``encode_channel``: feature-pyramid output channel count (0 = no head)
    - ``modulo``: input frame padding stride
    - ``ensemble``: whether to average forward+flip flows
    - ``head_type``: one of HEAD_NONE / HEAD_SEQUENTIAL / HEAD_CUSTOM

    ``head_config`` is only used for ``HEAD_SEQUENTIAL``; for CUSTOM the
    head class is imported from the per-version IFNet module.
    """

    encode_channel: int
    modulo: int
    ensemble: bool
    head_type: str
    head_config: dict[str, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Render this spec as the legacy ``MODEL_CONFIGS[v]`` dict shape.

        A fresh ``dict`` is returned each call so external code that does
        ``MODEL_CONFIGS[v].copy()`` cannot accidentally mutate the shared
        spec instance.
        """
        out: dict[str, Any] = {
            "encode_channel": self.encode_channel,
            "modulo": self.modulo,
            "ensemble": self.ensemble,
            "head_type": self.head_type,
        }
        if self.head_config is not None:
            out["head_config"] = dict(self.head_config)
        return out


# Versions grouped by spec. Order here also defines ``SUPPORTED_MODELS``.
# Each entry: (list_of_versions, RifeModelSpec).
_VERSION_GROUPS: list[tuple[list[str], RifeModelSpec]] = [
    # v4.0 ~ v4.6: no Head encoder; 4-block; ensemble enabled
    (
        ["4.0", "4.1", "4.2", "4.3", "4.4", "4.5", "4.6"],
        RifeModelSpec(0, 32, True, HEAD_NONE),
    ),
    # v4.7 ~ v4.9: sequential Head (3 → 16 → 4); encode_channel=4
    (
        ["4.7", "4.8", "4.9"],
        RifeModelSpec(
            4,
            32,
            True,
            HEAD_SEQUENTIAL,
            {"in_channels": 3, "mid_channels": 16, "out_channels": 4},
        ),
    ),
    # v4.10 ~ v4.12: sequential Head (3 → 32 → 8); encode_channel=8
    (
        ["4.10", "4.11", "4.12"],
        RifeModelSpec(
            8,
            32,
            True,
            HEAD_SEQUENTIAL,
            {"in_channels": 3, "mid_channels": 32, "out_channels": 8},
        ),
    ),
    # v4.12.lite / v4.13.lite: sequential Head (3 → 32 → 4); encode_channel=4
    (
        ["4.12.lite", "4.13.lite"],
        RifeModelSpec(
            4,
            32,
            True,
            HEAD_SEQUENTIAL,
            {"in_channels": 3, "mid_channels": 32, "out_channels": 4},
        ),
    ),
    # v4.13 ~ v4.20: custom Head; encode_channel=8 except v4.15.lite / v4.16.lite / v4.17.lite
    (
        ["4.13", "4.14", "4.14.lite", "4.15", "4.17", "4.18", "4.19", "4.20"],
        RifeModelSpec(8, 32, True, HEAD_CUSTOM),
    ),
    (
        ["4.15.lite", "4.16.lite", "4.17.lite"],
        RifeModelSpec(4, 32, True, HEAD_CUSTOM),
    ),
    # v4.21 ~ v4.24: custom Head; feat 传播,无 ensemble
    (
        ["4.21", "4.22", "4.23", "4.24"],
        RifeModelSpec(8, 32, False, HEAD_CUSTOM),
    ),
    (
        ["4.22.lite"],
        RifeModelSpec(4, 32, False, HEAD_CUSTOM),
    ),
    # v4.25 / v4.26 / v4.25.heavy: 5-block, modulo=64; no ensemble; encode_channel=4
    (
        ["4.25", "4.26", "4.25.heavy"],
        RifeModelSpec(4, 64, False, HEAD_CUSTOM),
    ),
    # v4.25.lite: 5-block, modulo=128
    (
        ["4.25.lite"],
        RifeModelSpec(4, 128, False, HEAD_CUSTOM),
    ),
    # v4.26.heavy: encode_channel=16
    (
        ["4.26.heavy"],
        RifeModelSpec(16, 64, False, HEAD_CUSTOM),
    ),
]


# Public API ---------------------------------------------------------------

SUPPORTED_MODELS: list[str] = [v for versions, _ in _VERSION_GROUPS for v in versions]

MODEL_SPECS: dict[str, RifeModelSpec] = {version: spec for versions, spec in _VERSION_GROUPS for version in versions}


# Legacy dict form retained for backward compatibility with external
# callers (``onnx_export``, ``onnx_solver``, tests) that read fields
# like ``MODEL_CONFIGS[v]["head_type"]``.
MODEL_CONFIGS: dict[str, dict[str, Any]] = {version: spec.to_dict() for version, spec in MODEL_SPECS.items()}


def get_spec(version: str) -> RifeModelSpec:
    """Look up the immutable spec for a model version.

    Use this in new code instead of ``MODEL_CONFIGS[version]`` — the spec
    has the same fields but with typed access and no risk of accidental
    mutation. ``dataclasses.replace`` lets you derive a tweaked
    copy when needed (e.g. ``replace(spec, ensemble=False)``).
    """
    return MODEL_SPECS[version]


# Re-export for callers that previously imported these from ``model_loader``
__all__ = [
    "HEAD_CUSTOM",
    "HEAD_NONE",
    "HEAD_SEQUENTIAL",
    "MODEL_CONFIGS",
    "MODEL_SPECS",
    "RifeModelSpec",
    "SUPPORTED_MODELS",
    "get_spec",
]
