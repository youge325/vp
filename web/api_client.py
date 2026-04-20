"""网页端 CLI 后端客户端 — subprocess 调用，无需 HTTP 服务器。"""

import json
import logging
import os
import subprocess
import sys
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class CliClient:
    """通过 subprocess 调用 `python -m app`。输出 JSON 行到 stdout。"""

    def __init__(self, backend_dir: str = None):
        if backend_dir is None:
            backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
        self.backend_dir = os.path.normpath(backend_dir)
        self._python = sys.executable
        logger.info("CliClient 初始化: backend_dir=%s", self.backend_dir)

    # ---- 核心命令 ----

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
        return self._run_with_progress(cmd, on_progress)

    def get_video_info(self, input_path: str) -> dict:
        logger.info("查询视频信息: %s", input_path)
        cmd = [self._python, "-m", "app", "info", "--input", input_path]
        return self._run_simple(cmd)

    def check_environment(self) -> dict:
        logger.info("检查环境可用性")
        cmd = [self._python, "-m", "app", "check"]
        return self._run_simple(cmd)

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

    # ---- 内部辅助方法 ----

    def _run_simple(self, cmd: list[str]) -> dict:
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
            return {"type": "error", "message": f"无效 JSON: {e}"}
        except Exception as e:
            logger.error("CLI 执行异常: %s", e)
            return {"type": "error", "message": str(e)}

    def _run_with_progress(self, cmd: list[str], on_progress=None) -> dict:
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


# 全局单例
client = CliClient()
