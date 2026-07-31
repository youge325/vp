# ruff: noqa: F821
"""Reviewed dynamic entry points for the Vulture zero-findings gate.

Every name here is consumed by Pydantic, pytest, TypedDict, or a framework
callback rather than by a statically visible Python call.
"""

model_config
_.model_post_init
__context
_._output_dir_not_blank
default_denoise
default_edge_boost
median_size
denoise_gain
edge_radius
edge_gain
edge_threshold
collect_ignore
pytestmark
_.__spec__
_cleanup_output
restore_root_logger
_reset_registry
# Imported and called by the protected dynamic ``ifnet_v4_*`` RIFE modules.
warp
# Called by PyTorch when tracing the ONNX export wrapper.
_.forward
