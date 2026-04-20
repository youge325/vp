"""基于 CLI 的后端客户端 — 通过 subprocess 调用 `python -m app`，无需 HTTP 服务器。"""

import json
import logging
import os
import subprocess
import sys
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class CliClient:
    """通过 subprocess 调用 CLI 工具的后端客户端。

    CLI 向 stdout 输出 JSON 行：
      {"type":"progress","current":1,"total":100,"percent":1.0}
      {"type":"completed","output_path":"...","processed_frames":100,"time_seconds":12.3}
      {"type":"error","message":"..."}
      {"type":"info","fps":30.0,"frames":900,...}
      {"type":"check","ffmpeg":{...},"gpu":{...},"tensor_backends":{...}}
    """

    def __init__(self, backend_dir: str = None):
        """参数:
        backend_dir: 包含 app/ 包的 backend/ 目录路径。
                     默认为 <workspace>/backend。
        """
        if backend_dir is None:
            # 自动检测：desktop/.. /backend
            backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
        self.backend_dir = os.path.normpath(backend_dir)
        self._python = sys.executable
        logger.info("CliClient 初始化: backend_dir=%s", self.backend_dir)

    # ------------------------------------------------------------------
    # 核心命令
    # ------------------------------------------------------------------

    def process(
        self,
        input_path: str,
        algorithm: str = "frame_interpolation",
        output: str = None,
        fps: float = 60.0,
        fps_mode: str = "multi",
        target_fps: float = 0.0,
        codec: str = "libx264",
        crf: int = 18,
        preset: str = "medium",
        backend: str = "pytorch",
        multi: int = 2,
        model: str = "4.25",
        scale: float = 1.0,
        fp16: bool = False,
        enable_interpolation: bool = False,
        enable_super_resolution: bool = False,
        process_order: str = "super_resolution_then_interpolation",
        temp_dir: str = None,
        output_dir: str = None,
        sr_scale_factor: float = 2.0,
        sr_algorithm: str = "placeholder",
        on_progress: Optional[Callable[[int, int, float, str, int, int], None]] = None,
    ) -> dict:
        """执行视频处理管道。阻塞直到完成。

        参数:
            input_path: 输入视频文件路径
            algorithm: 算法类型 (frame_interpolation/super_resolution/anime_optimization/format_conversion)
            output: 输出文件路径（默认自动生成）
            fps: 默认帧率（补帧倍率模式下仅作无帧处理器时的编码帧率）
            fps_mode: 帧率模式: "multi"=补帧倍率(默认), "target"=目标帧率(自动计算倍率)
            target_fps: 目标帧率模式下的目标帧率值（fps_mode="target" 时生效）
            codec: 视频编码器 (默认 libx264)
            crf: CRF 质量 (默认 18)
            preset: 编码预设 (默认 medium)
            backend: Tensor 后端 (pytorch/paddle)
            multi: 补帧倍率 2=2x, 4=4x (默认 2)
            model: RIFE 模型版本 (默认 "4.25")
            scale: 处理分辨率缩放 (默认 1.0，4K 建议 0.5)
            fp16: 启用半精度推理 (默认 False)
            temp_dir: 临时文件目录
            output_dir: 输出文件目录
            sr_scale_factor: 超分放大倍率 (默认 2.0，占位参数)
            sr_algorithm: 超分算法名称 (默认 "placeholder"，占位参数)
            on_progress: 进度回调 callback(当前帧, 总帧数, 百分比, 阶段名称, 阶段序号, 总阶段数)。

        返回:
            CLI 返回的结果字典（type="completed" 或 type="error"）。
        """
        cmd = [
            self._python,
            "-m",
            "app",
            "process",
            "--input",
            input_path,
            "--algorithm",
            algorithm,
            "--fps",
            str(fps),
            "--fps-mode",
            fps_mode,
            "--codec",
            codec,
            "--crf",
            str(crf),
            "--preset",
            preset,
            "--backend",
            backend,
            "--multi",
            str(multi),
            "--model",
            model,
            "--scale",
            str(scale),
            "--sr-scale-factor",
            str(sr_scale_factor),
            "--sr-algorithm",
            sr_algorithm,
        ]
        if fps_mode == "target" and target_fps > 0:
            cmd.extend(["--target-fps", str(target_fps)])
        if fp16:
            cmd.append("--fp16")
        if enable_interpolation:
            cmd.append("--enable-interpolation")
        if enable_super_resolution:
            cmd.append("--enable-super-resolution")
        if enable_interpolation and enable_super_resolution:
            cmd.extend(["--process-order", process_order])
        if output:
            cmd.extend(["--output", output])
        if temp_dir:
            cmd.extend(["--temp-dir", temp_dir])
        if output_dir:
            cmd.extend(["--output-dir", output_dir])

        logger.info("执行视频处理: input=%s, algorithm=%s", input_path, algorithm)
        logger.debug("CLI 完整命令: %s", " ".join(cmd))
        return self._run_with_progress(cmd, on_progress)

    def get_video_info(self, input_path: str) -> dict:
        """查询视频文件信息。返回信息字典或错误字典。"""
        logger.info("查询视频信息: %s", input_path)
        cmd = [self._python, "-m", "app", "info", "--input", input_path]
        return self._run_simple(cmd)

    def check_environment(self) -> dict:
        """检查环境可用性（FFmpeg/GPU/Tensor 后端）。"""
        logger.info("检查环境可用性")
        cmd = [self._python, "-m", "app", "check"]
        return self._run_simple(cmd)

    # ------------------------------------------------------------------
    # 处理辅助方法（为 UI 提供线程支持）
    # ------------------------------------------------------------------

    def process_async(
        self,
        input_path: str,
        algorithm: str = "frame_interpolation",
        output: str = None,
        fps: float = 60.0,
        fps_mode: str = "multi",
        target_fps: float = 0.0,
        codec: str = "libx264",
        crf: int = 18,
        preset: str = "medium",
        backend: str = "pytorch",
        multi: int = 2,
        model: str = "4.25",
        scale: float = 1.0,
        fp16: bool = False,
        enable_interpolation: bool = False,
        enable_super_resolution: bool = False,
        process_order: str = "super_resolution_then_interpolation",
        temp_dir: str = None,
        output_dir: str = None,
        sr_scale_factor: float = 2.0,
        sr_algorithm: str = "placeholder",
        on_progress: Optional[Callable[[int, int, float, str, int, int], None]] = None,
        on_completed: Optional[Callable[[dict], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> threading.Thread:
        """在后台线程中启动处理。返回 Thread 对象。"""

        def _worker():
            try:
                result = self.process(
                    input_path,
                    algorithm,
                    output,
                    fps,
                    fps_mode,
                    target_fps,
                    codec,
                    crf,
                    preset,
                    backend,
                    multi,
                    model,
                    scale,
                    fp16,
                    enable_interpolation,
                    enable_super_resolution,
                    process_order,
                    temp_dir,
                    output_dir,
                    sr_scale_factor,
                    sr_algorithm,
                    on_progress,
                )
                if result.get("type") == "completed" and on_completed:
                    on_completed(result)
                elif result.get("type") == "error" and on_error:
                    on_error(result.get("message", "未知错误"))
            except Exception as e:
                if on_error:
                    on_error(str(e))

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        return t

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    def _run_simple(self, cmd: list[str]) -> dict:
        """执行 CLI 命令并解析单行 JSON 输出。"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=self.backend_dir,
                timeout=60,
            )
            if result.returncode != 0:
                logger.warning(
                    "CLI 命令失败 (退出码 %d): %s",
                    result.returncode,
                    result.stderr.strip()[:200],
                )
                return {
                    "type": "error",
                    "message": result.stderr.strip() or f"退出码 {result.returncode}",
                }
            # 解析最后一行非空内容为 JSON
            for line in reversed(result.stdout.strip().splitlines()):
                line = line.strip()
                if line:
                    return json.loads(line)
            return {"type": "error", "message": "CLI 无输出"}
        except subprocess.TimeoutExpired:
            logger.error("CLI 命令超时")
            return {"type": "error", "message": "CLI 命令超时"}
        except json.JSONDecodeError as e:
            logger.error("CLI 输出无效 JSON: %s", e)
            return {"type": "error", "message": f"无效 JSON 输出: {e}"}
        except Exception as e:
            logger.error("CLI 执行异常: %s", e)
            return {"type": "error", "message": str(e)}

    def _run_with_progress(
        self,
        cmd: list[str],
        on_progress: Optional[Callable[[int, int, float], None]] = None,
    ) -> dict:
        """执行 CLI 命令，逐行读取 stdout 获取进度更新。"""
        last_result = {"type": "error", "message": "CLI 无输出"}
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=self.backend_dir,
            )

            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_type = obj.get("type")
                if msg_type == "progress" and on_progress:
                    on_progress(
                        obj.get("current", 0),
                        obj.get("total", 0),
                        obj.get("percent", 0),
                        obj.get("stage", ""),
                        obj.get("stage_index", 1),
                        obj.get("stage_total", 1),
                    )
                elif msg_type in ("completed", "error", "info"):
                    last_result = obj

            # 视频处理可能耗时很长，等待进程结束不设超时
            proc.wait()

            # 如果进程失败且只收到进度行，检查 stderr
            if proc.returncode != 0 and last_result.get("type") not in (
                "completed",
                "error",
            ):
                stderr = proc.stderr.read().strip() if proc.stderr else ""
                logger.error("视频处理进程异常退出 (码 %d): %s", proc.returncode, stderr[:200])
                last_result = {
                    "type": "error",
                    "message": stderr or f"退出码 {proc.returncode}",
                }

        except subprocess.TimeoutExpired:
            logger.error("视频处理超时")
            last_result = {"type": "error", "message": "CLI 命令超时"}
            try:
                proc.kill()
            except Exception:
                pass
        except Exception as e:
            logger.error("视频处理异常: %s", e)
            last_result = {"type": "error", "message": str(e)}

        return last_result
