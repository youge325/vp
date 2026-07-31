"""Argparse plumbing for the VP Workbench CLI commands."""

from __future__ import annotations

import argparse

from app.generated.contracts import FpsMode, ProcessOrder, ResumeMode, TensorBackend
from app.generated.protocol_constants import STAGE_WORKER_CONFIG_FLAG, STAGE_WORKER_SUBCOMMAND


def _add_shared_planning_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments common to ``process`` and ``inspect-output`` subcommands.

    Keeps the parser definitions in sync so a change to one command's CLI
    surface is automatically reflected in the other.

    ``--config-stdin`` accepts the neutral ``{decode, workflow, encode, output}``
    object used by the desktop host. Without it, the scalar CLI arguments below
    are the sole source for the validated defaults.
    """
    parser.add_argument(
        "--config-stdin",
        action="store_true",
        help=(
            "Read decode/workflow/encode/output config as a single JSON object "
            "from stdin (keys: decode, workflow, encode, output)."
        ),
    )
    parser.add_argument(
        "--algorithm",
        default="frame_interpolation",
        choices=[
            "frame_interpolation",
            "super_resolution",
            "format_conversion",
        ],
        help="Primary algorithm to run",
    )
    parser.add_argument("--enable-interpolation", action="store_true", help="Enable interpolation stage")
    parser.add_argument("--enable-super-resolution", action="store_true", help="Enable super-resolution stage")
    parser.add_argument(
        "--process-order",
        type=ProcessOrder,
        default=ProcessOrder.SUPER_RESOLUTION_THEN_INTERPOLATION,
        choices=list(ProcessOrder),
        help="Stage order when interpolation and super-resolution are both enabled",
    )
    parser.add_argument(
        "--fps-mode",
        type=FpsMode,
        default=FpsMode.MULTI,
        choices=list(FpsMode),
        help="FPS calculation mode",
    )
    parser.add_argument("--target-fps", type=float, default=60.0, help="Target FPS when using target mode")
    parser.add_argument("--codec", default="libx264", help="Video codec")
    parser.add_argument("--crf", type=int, default=18, help="CRF quality")
    parser.add_argument("--preset", default="medium", help="Encoding preset")
    parser.add_argument(
        "--backend",
        type=TensorBackend,
        default=TensorBackend.PYTORCH,
        choices=list(TensorBackend),
        help="Tensor backend",
    )
    parser.add_argument("--output-dir", default=None, help="Output directory override")
    parser.add_argument(
        "--multi",
        type=int,
        default=None,
        help="Interpolation multiplier (falls back to settings.RIFE_DEFAULT_MULTI)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="RIFE model version (falls back to settings.RIFE_MODEL_VERSION)",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=None,
        help="Interpolation scale factor (falls back to settings.RIFE_SCALE)",
    )
    parser.add_argument(
        "--fp16",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable FP16 inference (falls back to settings.RIFE_FP16)",
    )
    parser.add_argument("--sr-scale-factor", type=float, default=2.0, help="Super-resolution scale")
    parser.add_argument("--sr-algorithm", default="placeholder", help="Super-resolution algorithm")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app",
        description="Video Processing Workbench CLI",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    process_parser = subcommands.add_parser("process", help="Run the processing pipeline")
    process_parser.add_argument("--input", required=True, help="Input video path")
    process_parser.add_argument("--output", default=None, help="Optional output file path")
    _add_shared_planning_args(process_parser)
    process_parser.add_argument(
        "--resume-mode",
        type=ResumeMode,
        default=ResumeMode.AUTO,
        choices=list(ResumeMode),
        help=(
            "Conflict policy when an existing output is detected. 'auto' (default) "
            "resumes on signature match, otherwise emits a resume_conflict error so "
            "the caller can prompt the user. 'force-fresh' wipes both the sidecar "
            "and the existing final file. 'force-resume' keeps the sidecar."
        ),
    )
    process_parser.set_defaults(handler="process")

    info_parser = subcommands.add_parser("info", help="Inspect an input video")
    info_parser.add_argument("--input", required=True, help="Input video path")
    info_parser.set_defaults(handler="info")

    inspect_output_parser = subcommands.add_parser(
        "inspect-output",
        help="Probe whether a final output and resume sidecar already exist for a planned run.",
    )
    inspect_output_parser.add_argument("--input", required=True, help="Input video path")
    inspect_output_parser.add_argument("--output", default=None, help="Optional explicit output file path")
    _add_shared_planning_args(inspect_output_parser)
    inspect_output_parser.set_defaults(handler="inspect_output")

    stage_worker_parser = subcommands.add_parser(
        STAGE_WORKER_SUBCOMMAND,
        help=argparse.SUPPRESS,
    )
    stage_worker_parser.add_argument(STAGE_WORKER_CONFIG_FLAG, required=True, help=argparse.SUPPRESS)
    stage_worker_parser.set_defaults(handler="stage_worker")

    check_parser = subcommands.add_parser("check", help="Inspect runtime availability")
    check_parser.set_defaults(handler="check")

    benchmark_parser = subcommands.add_parser("benchmark", help="Run backend benchmark regression checks")
    benchmark_parser.add_argument("--scenario", default=None)
    benchmark_parser.add_argument("--baseline", default=None, help="Baseline JSON path")
    benchmark_parser.add_argument("--threshold", type=float, default=0.15, help="Relative regression threshold")
    benchmark_parser.add_argument("--report-json", default=None, help="Write JSON report to this path")
    benchmark_parser.add_argument("--report-markdown", default=None, help="Write Markdown report to this path")
    benchmark_parser.add_argument("--work-dir", default=None, help="Benchmark scratch directory")
    benchmark_parser.add_argument("--update-baseline", action="store_true", help="Overwrite the baseline with this run")
    benchmark_parser.add_argument("--warmup-runs", type=int, default=1)
    benchmark_parser.add_argument("--runs", type=int, default=3)
    benchmark_parser.add_argument("--width", type=int, default=640)
    benchmark_parser.add_argument("--height", type=int, default=360)
    benchmark_parser.add_argument("--fps", type=int, default=24)
    benchmark_parser.add_argument("--frames", type=int, default=96)
    benchmark_parser.add_argument("--multi", type=int, default=2)
    benchmark_parser.add_argument("--backend", default="pytorch", choices=["pytorch"])
    benchmark_parser.add_argument("--model", default="4.25")
    benchmark_parser.set_defaults(handler="benchmark")

    return parser
