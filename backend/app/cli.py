"""CLI 入口 — python -m app process|info|check"""

import argparse
import json
import math
import os
import subprocess
import sys
import time
import uuid

# 确保 backend 目录在 sys.path 上，使 app.* 导入在任何 cwd 下都能工作
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.config import settings
from app.utils.logger import setup_logging, get_logger
from app.algorithms.factory import register_default_algorithms
from app.processing.pipeline import Pipeline
from app.processing.decoder import DecodeFilter
from app.processing.frame_processor import FrameProcessFilter
from app.processing.encoder import EncodeFilter
from app.utils.ffmpeg_wrapper import FFmpegWrapper
from app.utils.file_utils import validate_input_path, get_output_path, cleanup_dir

logger = get_logger(__name__)

PROCESS_ORDER_MAP = {
    "super_resolution_then_interpolation": [
        "super_resolution",
        "frame_interpolation",
    ],
    "frame_interpolation_then_super_resolution": [
        "frame_interpolation",
        "super_resolution",
    ],
}

PROCESS_LABEL_MAP = {
    "frame_interpolation": "视频补帧",
    "super_resolution": "超分辨率",
    "anime_optimization": "动漫帧优化",
    "format_conversion": "格式转换",
}


# ---------------------------------------------------------------------------
# 子进程隔离检查辅助函数（避免 PyTorch/PaddlePaddle CUDA DLL 冲突）
# ---------------------------------------------------------------------------


def _check_pytorch_in_subprocess() -> dict:
    """在独立子进程中检查 PyTorch 和 GPU 可用性。

    PyTorch 和 PaddlePaddle 在 Windows 上会争抢 CUDA 运行时 DLL，
    必须在不同进程中分别 import 以避免冲突。
    """
    script = (
        "import json, sys;\n"
        "result = {'pytorch_available': False, 'gpu_available': False, 'gpu_devices': []};\n"
        "try:\n"
        "    import torch;\n"
        "    result['pytorch_available'] = True;\n"
        "    if torch.cuda.is_available():\n"
        "        result['gpu_available'] = True;\n"
        "        result['gpu_devices'] = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())];\n"
        "except (ImportError, OSError):\n"
        "    pass;\n"
        "print(json.dumps(result), flush=True)\n"
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout.strip())
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
        pass
    return {"pytorch_available": False, "gpu_available": False, "gpu_devices": []}


def _check_paddle_in_subprocess() -> dict:
    """在独立子进程中检查 PaddlePaddle 可用性。"""
    script = (
        "import json, sys;\n"
        "result = {'paddle_available': False};\n"
        "try:\n"
        "    import paddle;\n"
        "    result['paddle_available'] = True;\n"
        "except (ImportError, OSError):\n"
        "    pass;\n"
        "print(json.dumps(result), flush=True)\n"
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout.strip())
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
        pass
    return {"paddle_available": False}


# ---------------------------------------------------------------------------
# JSON 行协议辅助函数
# ---------------------------------------------------------------------------


def _emit(obj: dict) -> None:
    """向 stdout 输出一行 JSON（立即刷新）。"""
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def _build_algorithm_kwargs(args, algorithm_type: str) -> dict:
    """根据算法类型构建参数。"""
    if algorithm_type == "frame_interpolation":
        return {
            "multi": args.multi,
            "model_version": args.model,
            "scale": args.scale,
            "fp16": args.fp16,
        }
    if algorithm_type == "super_resolution":
        return {
            "scale_factor": args.sr_scale_factor,
            "sr_algorithm": args.sr_algorithm,
        }
    return {}


def _resolve_processing_steps(args) -> list[dict]:
    """
    解析当前任务需要执行的处理步骤。

    兼容旧用法：
    - 未传开关时，继续使用 --algorithm 的单算法模式
    - format_conversion 不需要帧算法处理，直接走解码/编码链
    """
    enable_interpolation = bool(args.enable_interpolation)
    enable_super_resolution = bool(args.enable_super_resolution)

    logger.debug(
        "_resolve_processing_steps: algorithm=%s, enable_interpolation=%s, enable_super_resolution=%s",
        args.algorithm,
        enable_interpolation,
        enable_super_resolution,
    )

    if enable_interpolation or enable_super_resolution:
        if enable_interpolation and enable_super_resolution:
            algorithm_types = PROCESS_ORDER_MAP[args.process_order]
        elif enable_interpolation:
            algorithm_types = ["frame_interpolation"]
        else:
            algorithm_types = ["super_resolution"]
    elif args.algorithm == "format_conversion":
        algorithm_types = []
    else:
        algorithm_types = [args.algorithm]

    steps = []
    for index, algorithm_type in enumerate(algorithm_types, start=1):
        steps.append(
            {
                "algorithm_type": algorithm_type,
                "algorithm_kwargs": _build_algorithm_kwargs(args, algorithm_type),
                "stage_name": f"{index:02d}_{algorithm_type}",
            }
        )
    return steps


def _make_progress_callback(stage_index: int, total_stages: int, algorithm_type: str):
    """构建带阶段信息的整体进度回调。"""

    def progress_callback(current: int, total: int):
        stage_fraction = (current / total) if total > 0 else 0.0
        overall_percent = 100.0
        if total_stages > 0:
            overall_percent = ((stage_index + stage_fraction) / total_stages) * 100
        _emit(
            {
                "type": "progress",
                "current": current,
                "total": total,
                "percent": round(overall_percent, 1),
                "stage": PROCESS_LABEL_MAP.get(algorithm_type, algorithm_type),
                "stage_index": stage_index + 1,
                "stage_total": total_stages,
            }
        )

    return progress_callback


# ---------------------------------------------------------------------------
# 子命令实现
# ---------------------------------------------------------------------------


def _resolve_fps_and_multi(args, ffmpeg: FFmpegWrapper, input_path: str) -> tuple[int, float, float, bool]:
    """根据 fps-mode 解析最终帧率、倍率和是否需要压制。

    返回:
        (multi, encode_fps, interpolated_fps, need_resample)
        - multi: 补帧倍率
        - encode_fps: 编码器输出帧率
        - interpolated_fps: 补帧后的帧率（编码器输入帧率）
        - need_resample: 是否需要帧率压制
    """
    fps_mode = getattr(args, "fps_mode", "multi")

    if fps_mode == "target":
        # 目标帧率模式：自动计算倍率
        target_fps = getattr(args, "target_fps", 60.0)
        source_fps = ffmpeg.get_fps(input_path)

        # multi = max(2, ceil(target_fps / source_fps))
        # 例如 24fps→60fps: ceil(60/24)=3, 30fps→60fps: ceil(60/30)=2
        multi = max(2, math.ceil(target_fps / source_fps))
        interpolated_fps = source_fps * multi
        need_resample = interpolated_fps > target_fps
        encode_fps = target_fps if need_resample else interpolated_fps

        logger.info(
            "目标帧率模式: source_fps=%.3f, target_fps=%.1f, multi=%d, "
            "interpolated_fps=%.1f, encode_fps=%.1f, need_resample=%s",
            source_fps,
            target_fps,
            multi,
            interpolated_fps,
            encode_fps,
            need_resample,
        )
        return multi, encode_fps, interpolated_fps, need_resample
    else:
        # 补帧倍率模式：用户直接指定倍率
        multi = args.multi
        encode_fps = args.fps  # 仅作为无帧处理时的默认编码帧率
        interpolated_fps = None  # 补帧后由 FrameProcessFilter 自动计算
        need_resample = False

        logger.info(
            "补帧倍率模式: multi=%d, default_encode_fps=%.1f",
            multi,
            encode_fps,
        )
        return multi, encode_fps, interpolated_fps, need_resample


def cmd_process(args) -> None:
    """执行视频处理管道。"""
    register_default_algorithms()

    logger.info(
        "cmd_process 参数: algorithm=%s, enable_interpolation=%s, enable_super_resolution=%s, "
        "fps=%.1f, multi=%d, fps_mode=%s, target_fps=%.1f, model=%s, backend=%s",
        args.algorithm,
        args.enable_interpolation,
        args.enable_super_resolution,
        args.fps,
        args.multi,
        getattr(args, "fps_mode", "multi"),
        getattr(args, "target_fps", 0.0),
        args.model,
        args.backend,
    )

    input_path = args.input
    if not validate_input_path(input_path):
        _emit({"type": "error", "message": f"输入文件无效或格式不支持: {input_path}"})
        sys.exit(1)

    # 确定输出路径
    output_dir = args.output_dir or settings.OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    output_path = args.output or get_output_path(input_path, output_dir)

    temp_dir = args.temp_dir or settings.TEMP_DIR
    os.makedirs(temp_dir, exist_ok=True)

    # 确保 models 目录存在
    os.makedirs(settings.RIFE_MODEL_DIR, exist_ok=True)

    task_id = uuid.uuid4().hex[:12]
    start_time = time.time()

    # 根据 fps-mode 解析倍率和编码帧率
    ffmpeg = FFmpegWrapper()
    multi, encode_fps, interpolated_fps, need_resample = _resolve_fps_and_multi(
        args,
        ffmpeg,
        input_path,
    )

    # 如果是目标帧率模式，覆盖 args.multi 以便 _build_algorithm_kwargs 使用计算后的倍率
    if getattr(args, "fps_mode", "multi") == "target":
        args.multi = multi

    # 构建管道
    pipeline = Pipeline(name=f"task_{task_id}")
    processing_steps = _resolve_processing_steps(args)

    if not processing_steps and args.algorithm != "format_conversion":
        logger.warning(
            "算法为 '%s' 但处理步骤为空，视频将被原样复制。"
            "如果需要补帧或超分，请检查 --enable-interpolation / --enable-super-resolution 参数。",
            args.algorithm,
        )

    pipeline.add_filter(DecodeFilter(ffmpeg_wrapper=ffmpeg))
    logger.info("处理步骤数量: %d", len(processing_steps))
    for stage_index, step in enumerate(processing_steps):
        logger.info(
            "添加帧处理器: stage=%s, algorithm_type=%s",
            step["stage_name"],
            step["algorithm_type"],
        )
        pipeline.add_filter(
            FrameProcessFilter(
                algorithm_type=step["algorithm_type"],
                tensor_backend_name=args.backend,
                progress_callback=_make_progress_callback(
                    stage_index,
                    len(processing_steps),
                    step["algorithm_type"],
                ),
                algorithm_kwargs=step["algorithm_kwargs"],
                stage_name=step["stage_name"],
            )
        )

    pipeline.add_filter(
        EncodeFilter(
            ffmpeg_wrapper=ffmpeg,
            codec=args.codec,
            crf=args.crf,
            preset=args.preset,
        )
    )

    # 准备输入数据和上下文
    input_data = {
        "input_path": input_path,
        "output_path": output_path,
        "fps": args.fps,
    }

    # 目标帧率模式下传递压制信息给编码器
    if need_resample:
        input_data["target_fps"] = encode_fps
        if interpolated_fps is not None:
            # 补帧后 fps 会被 FrameProcessFilter 覆盖为 interpolated_fps，
            # 但编码器需要知道实际输出帧率
            context = {
                "task_id": task_id,
                "temp_dir": temp_dir,
                "output_dir": output_dir,
                "processing_steps": processing_steps,
                "target_fps": encode_fps,
            }
        else:
            context = {
                "task_id": task_id,
                "temp_dir": temp_dir,
                "output_dir": output_dir,
                "processing_steps": processing_steps,
            }
    else:
        context = {
            "task_id": task_id,
            "temp_dir": temp_dir,
            "output_dir": output_dir,
            "processing_steps": processing_steps,
        }

    try:
        result = pipeline.execute(input_data, context)
        elapsed = round(time.time() - start_time, 2)
        _emit(
            {
                "type": "completed",
                "output_path": result.get("output_path", output_path),
                "processed_frames": result.get("processed_frames", 0),
                "time_seconds": elapsed,
            }
        )
    except Exception as e:
        _emit({"type": "error", "message": str(e)})
        sys.exit(1)
    finally:
        # 清理临时帧文件
        frame_dir = context.get("frame_dir")
        if frame_dir and os.path.isdir(frame_dir):
            cleanup_dir(os.path.dirname(frame_dir))


def cmd_info(args) -> None:
    """查询视频文件信息。"""
    input_path = args.input
    if not os.path.isfile(input_path):
        _emit({"type": "error", "message": f"文件不存在: {input_path}"})
        sys.exit(1)

    ffmpeg = FFmpegWrapper()
    try:
        info = ffmpeg.get_video_info(input_path)
        fps = ffmpeg.get_fps(input_path)
        frames = ffmpeg.get_frame_count(input_path)
        duration = ffmpeg.get_duration(input_path)
        has_audio = ffmpeg.has_audio(input_path)

        # 提取分辨率
        width, height = 0, 0
        for stream in info.get("streams", []):
            if stream.get("codec_type") == "video":
                width = int(stream.get("width", 0))
                height = int(stream.get("height", 0))
                break

        _emit(
            {
                "type": "info",
                "fps": fps,
                "frames": frames,
                "duration": duration,
                "has_audio": has_audio,
                "width": width,
                "height": height,
            }
        )
    except Exception as e:
        _emit({"type": "error", "message": str(e)})
        sys.exit(1)


def cmd_check(args) -> None:
    """检查环境可用性。

    PyTorch 和 PaddlePaddle 在独立子进程中检查，避免 Windows 上
    两个框架争抢 CUDA 运行时 DLL 导致环境冲突。
    """
    # FFmpeg 检查（不涉及 DLL 冲突，在主进程中执行）
    ffmpeg = FFmpegWrapper()
    ffmpeg_available = ffmpeg.is_available()
    ffmpeg_version = ffmpeg.get_version() if ffmpeg_available else None

    # PyTorch + GPU 检查（子进程隔离）
    pytorch_result = _check_pytorch_in_subprocess()
    pytorch_available = pytorch_result["pytorch_available"]
    gpu_available = pytorch_result["gpu_available"]
    gpu_devices = pytorch_result["gpu_devices"]

    # PaddlePaddle 检查（子进程隔离）
    paddle_result = _check_paddle_in_subprocess()
    paddle_available = paddle_result["paddle_available"]

    # RIFE 模型权重检查（只检查文件，不涉及 DLL）
    rife_model_available = False
    rife_model_path = os.path.join(settings.RIFE_MODEL_DIR, f"flownet_v{settings.RIFE_MODEL_VERSION}.pkl")
    if os.path.isfile(rife_model_path) and os.path.getsize(rife_model_path) > 0:
        rife_model_available = True

    _emit(
        {
            "type": "check",
            "ffmpeg": {
                "available": ffmpeg_available,
                "path": ffmpeg.ffmpeg_path if ffmpeg_available else "",
                "version": ffmpeg_version or "",
            },
            "gpu": {
                "available": gpu_available,
                "devices": gpu_devices,
            },
            "tensor_backends": {
                "pytorch": pytorch_available,
                "paddle": paddle_available,
            },
            "rife_model": {
                "available": rife_model_available,
                "version": settings.RIFE_MODEL_VERSION,
                "path": rife_model_path,
            },
        }
    )


# ---------------------------------------------------------------------------
# 参数解析器
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app",
        description="视频补帧与超分软件 — 命令行工具",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- process ---
    p_process = sub.add_parser("process", help="执行视频处理管道")
    p_process.add_argument("--input", required=True, help="输入视频文件路径")
    p_process.add_argument("--output", default=None, help="输出文件路径（默认自动生成）")
    p_process.add_argument(
        "--algorithm",
        default="frame_interpolation",
        choices=[
            "frame_interpolation",
            "super_resolution",
            "anime_optimization",
            "format_conversion",
        ],
        help="处理算法 (默认: frame_interpolation)",
    )
    p_process.add_argument("--enable-interpolation", action="store_true", help="启用视频补帧步骤")
    p_process.add_argument("--enable-super-resolution", action="store_true", help="启用超分辨率步骤")
    p_process.add_argument(
        "--process-order",
        default="super_resolution_then_interpolation",
        choices=list(PROCESS_ORDER_MAP.keys()),
        help="同时启用补帧和超分时的执行顺序",
    )
    p_process.add_argument(
        "--fps",
        type=float,
        default=60.0,
        help="目标帧率 (默认: 60，补帧倍率模式下仅作无帧处理器时的编码帧率)",
    )
    p_process.add_argument(
        "--fps-mode",
        default="multi",
        choices=["multi", "target"],
        help="帧率模式: multi=补帧倍率模式(默认), target=目标帧率模式(自动计算倍率)",
    )
    p_process.add_argument(
        "--target-fps",
        type=float,
        default=60.0,
        help="目标帧率模式下的目标帧率 (默认: 60)",
    )
    p_process.add_argument("--codec", default="libx264", help="视频编码器 (默认: libx264)")
    p_process.add_argument("--crf", type=int, default=18, help="CRF质量 (默认: 18)")
    p_process.add_argument("--preset", default="medium", help="编码预设 (默认: medium)")
    p_process.add_argument(
        "--backend",
        default="pytorch",
        choices=["pytorch", "paddle"],
        help="Tensor后端 (默认: pytorch)",
    )
    p_process.add_argument("--temp-dir", default=None, help="临时文件目录")
    p_process.add_argument("--output-dir", default=None, help="输出文件目录")

    # RIFE 补帧参数
    p_process.add_argument("--multi", type=int, default=2, help="补帧倍率: 2=2x, 4=4x (默认: 2)")
    p_process.add_argument(
        "--model",
        default="4.25",
        help="RIFE 模型版本 (默认: 4.25)，可选: 4.0~4.6, 4.7~4.9, 4.10~4.12.lite, 4.13~4.20, 4.21~4.26.heavy",
    )
    p_process.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="处理分辨率缩放，4K视频建议0.5 (默认: 1.0)",
    )
    p_process.add_argument("--fp16", action="store_true", help="启用半精度推理（加速，需GPU支持）")
    p_process.add_argument(
        "--sr-scale-factor",
        type=float,
        default=2.0,
        help="超分放大倍率（当前为占位参数，默认: 2.0）",
    )
    p_process.add_argument("--sr-algorithm", default="placeholder", help="超分算法名称（当前为占位参数）")

    p_process.set_defaults(func=cmd_process)

    # --- info ---
    p_info = sub.add_parser("info", help="查询视频信息")
    p_info.add_argument("--input", required=True, help="视频文件路径")
    p_info.set_defaults(func=cmd_info)

    # --- check ---
    p_check = sub.add_parser("check", help="检查环境可用性")
    p_check.set_defaults(func=cmd_check)

    return parser


def main():
    setup_logging()
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
