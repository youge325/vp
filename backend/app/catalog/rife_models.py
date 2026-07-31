"""Neutral model metadata for the 36 supported RIFE checkpoints.

The catalog deliberately lives outside ``algorithms`` and ``utils`` so model
loaders, planning metadata, and environment reporting can depend on it without
creating a package cycle.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

# Head type constants shared by model loading, runtime metrics and tests.
HEAD_NONE = "none"  # No Head encoder (v4.0 ~ v4.6)
HEAD_SEQUENTIAL = "sequential"  # nn.Sequential Head (v4.7 ~ v4.13.lite)
HEAD_CUSTOM = "custom"  # Custom Head class imported from the IFNet file


@dataclass(frozen=True)
class RifeModelSpec:
    """Immutable spec for one RIFE checkpoint.

    The mandatory fields are what the loader / IFNet wrapper care about:
    - ``modulo``: input frame padding stride
    - ``ensemble``: whether to average forward+flip flows
    - ``head_type``: one of HEAD_NONE / HEAD_SEQUENTIAL / HEAD_CUSTOM

    ``head_config`` is only used for ``HEAD_SEQUENTIAL``; for CUSTOM the
    head class is imported from the per-version IFNet module.
    """

    modulo: int
    ensemble: bool
    head_type: str
    head_config: Mapping[str, int] | None = None

    def __post_init__(self) -> None:
        if self.head_config is not None:
            object.__setattr__(self, "head_config", MappingProxyType(dict(self.head_config)))


# Versions grouped by spec. Order here also defines ``SUPPORTED_MODELS``.
# Each entry: (list_of_versions, RifeModelSpec).
_VERSION_GROUPS: tuple[tuple[tuple[str, ...], RifeModelSpec], ...] = (
    # v4.0 ~ v4.6: no Head encoder; 4-block; ensemble enabled
    (
        ("4.0", "4.1", "4.2", "4.3", "4.4", "4.5", "4.6"),
        RifeModelSpec(32, True, HEAD_NONE),
    ),
    # v4.7 ~ v4.9: sequential Head (3 → 16 → 4); encode_channel=4
    (
        ("4.7", "4.8", "4.9"),
        RifeModelSpec(
            32,
            True,
            HEAD_SEQUENTIAL,
            {"in_channels": 3, "mid_channels": 16, "out_channels": 4},
        ),
    ),
    # v4.10 ~ v4.12: sequential Head (3 → 32 → 8); encode_channel=8
    (
        ("4.10", "4.11", "4.12"),
        RifeModelSpec(
            32,
            True,
            HEAD_SEQUENTIAL,
            {"in_channels": 3, "mid_channels": 32, "out_channels": 8},
        ),
    ),
    # v4.12.lite / v4.13.lite: sequential Head (3 → 32 → 4); encode_channel=4
    (
        ("4.12.lite", "4.13.lite"),
        RifeModelSpec(
            32,
            True,
            HEAD_SEQUENTIAL,
            {"in_channels": 3, "mid_channels": 32, "out_channels": 4},
        ),
    ),
    # v4.13 ~ v4.20: custom Head; encode_channel=8 except v4.15.lite / v4.16.lite / v4.17.lite
    (
        ("4.13", "4.14", "4.14.lite", "4.15", "4.17", "4.18", "4.19", "4.20"),
        RifeModelSpec(32, True, HEAD_CUSTOM),
    ),
    (
        ("4.15.lite", "4.16.lite", "4.17.lite"),
        RifeModelSpec(32, True, HEAD_CUSTOM),
    ),
    # v4.21 ~ v4.24: custom Head; feat 传播,无 ensemble
    (
        ("4.21", "4.22", "4.23", "4.24"),
        RifeModelSpec(32, False, HEAD_CUSTOM),
    ),
    (
        ("4.22.lite",),
        RifeModelSpec(32, False, HEAD_CUSTOM),
    ),
    # v4.25 / v4.26 / v4.25.heavy: 5-block, modulo=64; no ensemble; encode_channel=4
    (
        ("4.25", "4.26", "4.25.heavy"),
        RifeModelSpec(64, False, HEAD_CUSTOM),
    ),
    # v4.25.lite: 5-block, modulo=128
    (
        ("4.25.lite",),
        RifeModelSpec(128, False, HEAD_CUSTOM),
    ),
    # v4.26.heavy: encode_channel=16
    (
        ("4.26.heavy",),
        RifeModelSpec(64, False, HEAD_CUSTOM),
    ),
)


# Public API ---------------------------------------------------------------

SUPPORTED_MODELS: tuple[str, ...] = tuple(v for versions, _ in _VERSION_GROUPS for v in versions)

MODEL_SPECS: Mapping[str, RifeModelSpec] = MappingProxyType(
    {version: spec for versions, spec in _VERSION_GROUPS for version in versions}
)


def get_spec(version: str) -> RifeModelSpec:
    """Look up the immutable spec for a model version.

    The spec exposes typed fields with no risk of accidental mutation.
    """
    return MODEL_SPECS[version]


__all__ = [
    "HEAD_CUSTOM",
    "HEAD_NONE",
    "HEAD_SEQUENTIAL",
    "MODEL_SPECS",
    "RifeModelSpec",
    "SUPPORTED_MODELS",
    "get_spec",
]
