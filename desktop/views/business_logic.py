"""MainWindow 业务逻辑 Mixin — 环境检查、文件操作、视频信息、算法/开关/预设、
处理流程、进度/完成/错误回调、摘要刷新、格式化辅助、拖放事件、resize/布局。
"""

import os
import threading

from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QResizeEvent
from PyQt6.QtWidgets import QBoxLayout, QFileDialog, QWidget

from .constants import (
    ALGORITHM_HINTS,
    ALGORITHM_MAP,
    COMBINED_TASK_TYPES,
    FPS_MODE_MAP,
    PAGE_ALGORITHM_MAP,
    PROCESS_ORDER_MAP,
    VIDEO_FILTER,
    WORKSPACE_PAGES,
)


class MainWindowLogic:
    """业务逻辑 Mixin：所有非 UI 构建的方法。

    不定义 __init__，所有属性在 MainWindow.__init__ 中初始化。
    通过 self 访问 MainWindow 实例属性。
    """

    # ---- 信号连接 ----

    def _connect_live_updates(self):
        self.algorithm_combo.currentTextChanged.connect(self._on_algorithm_changed)
        self.input_path_edit.textChanged.connect(self._on_input_path_changed)
        self.output_path_edit.textChanged.connect(self._refresh_summary)
        self.output_dir_edit.textChanged.connect(self._refresh_summary)
        self.temp_dir_edit.textChanged.connect(self._refresh_summary)
        self.backend_combo.currentTextChanged.connect(self._refresh_summary)
        self.fps_mode_combo.currentTextChanged.connect(self._on_fps_mode_changed)
        self.target_fps_spin.valueChanged.connect(self._on_target_fps_changed)
        self.model_combo.currentTextChanged.connect(self._refresh_summary)
        self.multi_combo.currentTextChanged.connect(self._refresh_summary)
        self.scale_spin.valueChanged.connect(self._refresh_summary)
        self.fp16_check.toggled.connect(self._refresh_summary)
        self.enable_interpolation_check.toggled.connect(self._on_processing_switch_changed)
        self.enable_super_resolution_check.toggled.connect(self._on_processing_switch_changed)
        self.process_order_combo.currentTextChanged.connect(self._on_processing_switch_changed)
        self.codec_combo.currentTextChanged.connect(self._refresh_summary)
        self.crf_spin.valueChanged.connect(self._refresh_summary)
        self.preset_combo.currentTextChanged.connect(self._refresh_summary)
        self.sr_scale_spin.valueChanged.connect(self._refresh_summary)
        self.sr_algorithm_combo.currentTextChanged.connect(self._refresh_summary)

    # ---- 页面导航辅助 ----

    def _workspace_index(self, page_key: str) -> int:
        for index, (key, _, _) in enumerate(WORKSPACE_PAGES):
            if key == page_key:
                return index
        return 0

    def _page_algorithm_text(self, index: int) -> str | None:
        if 0 <= index < len(WORKSPACE_PAGES):
            page_key = WORKSPACE_PAGES[index][0]
            return PAGE_ALGORITHM_MAP.get(page_key)
        return None

    def _switch_to_algorithm_page(self, algorithm_text: str):
        for index, (page_key, _, _) in enumerate(WORKSPACE_PAGES):
            if PAGE_ALGORITHM_MAP.get(page_key) == algorithm_text:
                self._switch_workspace_page(index)
                return

    def _switch_workspace_page(self, index: int):
        """切换当前工作区页面。"""
        if not hasattr(self, "workspace_stack"):
            return

        self.workspace_stack.setCurrentIndex(index)
        for button_index, button in enumerate(self._workspace_nav_buttons):
            button.setChecked(button_index == index)

        if 0 <= index < len(WORKSPACE_PAGES):
            _, title, _ = WORKSPACE_PAGES[index]
            if hasattr(self, "mode_label"):
                self.mode_label.setText(f"桌面工作台 · {title}")
            algorithm_text = self._page_algorithm_text(index)
            if algorithm_text and self.algorithm_combo.currentText() != algorithm_text:
                self.algorithm_combo.setCurrentText(algorithm_text)

    # ---- 环境检查 ----

    def _check_environment(self):
        self.env_label.setText("正在检测 FFmpeg、GPU 和 Tensor 后端...")
        self._set_hero_state("pending", "环境检测中")

        for badge, value_label in self._env_badges.values():
            badge.setProperty("state", "pending")
            value_label.setText("检测中")
            self._refresh_widget_style(badge)

        def _worker():
            result = self.cli.check_environment()
            self._env_bridge.result_ready.emit(result)

        threading.Thread(target=_worker, daemon=True).start()

    def _show_env_result(self, result: dict):
        if result.get("type") == "error":
            self.env_label.setText(f"环境检查失败：{result['message']}")
            self._set_hero_state("attention", "环境异常")
            self.status_label.setText("环境检查失败")
            return

        ffmpeg = result.get("ffmpeg", {})
        gpu = result.get("gpu", {})
        tensor_backends = result.get("tensor_backends", {})
        rife = result.get("rife_model", {})

        ffmpeg_available = bool(ffmpeg.get("available"))
        pytorch_available = bool(tensor_backends.get("pytorch"))
        paddle_available = bool(tensor_backends.get("paddle"))
        gpu_available = bool(gpu.get("available"))
        rife_available = bool(rife.get("available"))

        self._set_env_badge(
            "ffmpeg",
            "ok" if ffmpeg_available else "bad",
            "可用" if ffmpeg_available else "缺失",
        )
        self._set_env_badge(
            "gpu",
            "ok" if gpu_available else "warning",
            ", ".join(gpu.get("devices", [])[:2]) if gpu_available else "未检测到",
        )
        self._set_env_badge(
            "pytorch",
            "ok" if pytorch_available else "warning",
            "可用" if pytorch_available else "不可用",
        )
        self._set_env_badge(
            "paddle",
            "ok" if paddle_available else "warning",
            "可用" if paddle_available else "不可用",
        )
        self._set_env_badge(
            "rife",
            "ok" if rife_available else "warning",
            f"v{rife.get('version', '?')}" if rife_available else "未就绪",
        )

        parts = [
            f"FFmpeg {'已就绪' if ffmpeg_available else '缺失'}",
            f"GPU {'可用' if gpu_available else '未检测到'}",
            f"PyTorch {'可用' if pytorch_available else '不可用'}",
            f"Paddle {'可用' if paddle_available else '不可用'}",
        ]
        if rife:
            parts.append(f"RIFE v{rife.get('version', '?')} {'可用' if rife_available else '未就绪'}")
        self.env_label.setText(" · ".join(parts))

        if ffmpeg_available and (pytorch_available or paddle_available):
            self._set_hero_state("ready", "环境就绪")
            self.status_label.setText("环境检查完成")
        else:
            self._set_hero_state("attention", "需要补充依赖")
            self.status_label.setText("环境存在缺口")

    def _set_env_badge(self, key: str, state: str, value_text: str):
        badge, value_label = self._env_badges[key]
        badge.setProperty("state", state)
        value_label.setText(value_text)
        self._refresh_widget_style(badge)

    def _set_hero_state(self, state: str, text: str):
        self.hero_state_badge.setProperty("state", state)
        self.hero_state_badge.setText(text)
        self._refresh_widget_style(self.hero_state_badge)

    # ---- 文件浏览 ----

    def _browse_input(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择视频文件", "", VIDEO_FILTER)
        if path:
            self._switch_workspace_page(1)
            self.input_path_edit.setText(path)
            self._query_video_info()

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "选择输出路径",
            "",
            "视频文件 (*.mp4 *.avi *.mkv *.mov);;所有文件 (*)",
        )
        if path:
            self.output_path_edit.setText(path)

    def _browse_output_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.output_dir_edit.setText(path)

    def _browse_temp_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择临时目录")
        if path:
            self.temp_dir_edit.setText(path)

    # ---- 拖放事件 ----

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if not urls:
            return

        path = urls[0].toLocalFile()
        if os.path.isfile(path):
            self._switch_workspace_page(1)
            self.input_path_edit.setText(path)
            self._query_video_info()

    # ---- 视频信息查询 ----

    def _on_input_path_changed(self, path: str):
        self._last_output_path = ""
        self._video_info = {}
        self._reset_video_metrics()

        if path:
            name = os.path.basename(path)
            self.file_meta_label.setText(f"已选择素材：{name}。正在等待读取基础信息。")
        else:
            self.file_meta_label.setText("还没有选择素材。")

        self._refresh_summary()

    def _query_video_info(self):
        input_path = self.input_path_edit.text().strip()
        if not input_path:
            self.status_label.setText("请先选择视频文件")
            return

        self._set_video_metrics("查询中...")
        self.info_hint_label.setText("正在读取视频基础信息，请稍候...")
        self.status_label.setText("正在查询视频信息...")

        def _worker():
            result = self.cli.get_video_info(input_path)
            self._info_bridge.result_ready.emit(result)

        threading.Thread(target=_worker, daemon=True).start()

    def _show_video_info(self, result: dict):
        if result.get("type") == "error":
            self._video_info = {}
            self._reset_video_metrics()
            self.info_hint_label.setText("读取失败，请检查素材路径、FFmpeg 配置或文件格式。")
            self.status_label.setText(f"查询失败：{result.get('message', '')}")
            self._refresh_summary()
            return

        self._video_info = result

        fps_value = result.get("fps", "?")
        self._info_labels["fps"].setText(self._format_fps(fps_value))
        self._info_labels["frames"].setText(str(result.get("frames", "?")))
        self._info_labels["duration"].setText(self._format_duration(result.get("duration")))
        width = result.get("width", "?")
        height = result.get("height", "?")
        self._info_labels["resolution"].setText(f"{width} x {height}")
        self._info_labels["audio"].setText("有音频" if result.get("has_audio") else "无音频")

        basename = os.path.basename(self.input_path_edit.text().strip())
        self.file_meta_label.setText(
            f"已载入：{basename} · {width} x {height} · {self._format_fps(fps_value)} fps · {self._format_duration(result.get('duration'))}"
        )

        source_fps = self._to_float(fps_value)
        multi = self._current_multi()
        fps_mode = self._current_fps_mode()
        enable_interpolation, enable_super_resolution = self._current_processing_switches()
        if source_fps and enable_interpolation:
            if fps_mode == "target":
                target_fps = self._current_target_fps()
                import math

                auto_multi = max(2, math.ceil(target_fps / source_fps))
                interpolated_fps = source_fps * auto_multi
                if interpolated_fps > target_fps:
                    self.info_hint_label.setText(
                        f"当前素材约 {self._format_fps(source_fps)} fps，目标 {self._format_fps(target_fps)} fps："
                        f"自动 {auto_multi}x 补帧到 {self._format_fps(interpolated_fps)} fps，再压制到 {self._format_fps(target_fps)} fps。"
                    )
                else:
                    self.info_hint_label.setText(
                        f"当前素材约 {self._format_fps(source_fps)} fps，目标 {self._format_fps(target_fps)} fps："
                        f"自动 {auto_multi}x 补帧到 {self._format_fps(interpolated_fps)} fps（无需压制）。"
                    )
                self._update_fps_preview()
            else:
                estimated = source_fps * multi
                self.info_hint_label.setText(
                    f"当前素材约 {self._format_fps(source_fps)} fps，使用 {multi}x 补帧时理论输出约为 {self._format_fps(estimated)} fps。"
                )
        elif enable_super_resolution:
            self.info_hint_label.setText("素材信息已读取，可以单独超分，也可以和补帧组合后再开始处理。")
        else:
            self.info_hint_label.setText("素材信息已读取，可以开始调整算法与编码参数。")

        self.status_label.setText("视频信息已获取")
        self._refresh_summary()

    # ---- 算法 / 开关 / 预设逻辑 ----

    def _supports_combined_processing(self, text: str = None) -> bool:
        """当前处理类型是否支持补帧/超分组合开关。"""
        current_text = text or self.algorithm_combo.currentText()
        return current_text in COMBINED_TASK_TYPES

    def _default_processing_switches(self, text: str) -> tuple[bool, bool]:
        """为补帧/超分模式设置默认开关。"""
        if text == "超分辨率":
            return False, True
        return True, False

    def _current_processing_switches(self) -> tuple[bool, bool]:
        """返回当前补帧和超分的启用状态。"""
        if not hasattr(self, "enable_interpolation_check"):
            return False, False
        if not self._supports_combined_processing():
            return False, False
        return (
            self.enable_interpolation_check.isChecked(),
            self.enable_super_resolution_check.isChecked(),
        )

    def _current_process_order(self) -> str:
        """返回当前选择的组合处理顺序。"""
        return PROCESS_ORDER_MAP.get(
            self.process_order_combo.currentText(),
            "super_resolution_then_interpolation",
        )

    def _current_processing_label(self, text: str = None) -> str:
        """返回当前实际会执行的处理模式名称。"""
        current_text = text or self.algorithm_combo.currentText()
        if not self._supports_combined_processing(current_text):
            return current_text

        enable_interpolation = self.enable_interpolation_check.isChecked()
        enable_super_resolution = self.enable_super_resolution_check.isChecked()
        if enable_interpolation and enable_super_resolution:
            return "补帧 + 超分"
        if enable_interpolation:
            return "视频补帧"
        if enable_super_resolution:
            return "超分辨率"
        return "未启用增强"

    def _build_algorithm_hint(self, text: str = None) -> str:
        """根据当前开关状态生成处理提示。"""
        current_text = text or self.algorithm_combo.currentText()
        if not self._supports_combined_processing(current_text):
            return ALGORITHM_HINTS.get(current_text, "")

        enable_interpolation = self.enable_interpolation_check.isChecked()
        enable_super_resolution = self.enable_super_resolution_check.isChecked()
        if enable_interpolation and enable_super_resolution:
            return f"补帧和超分都已启用，当前会按\u201c{self.process_order_combo.currentText()}\u201d执行。"
        if enable_interpolation:
            return ALGORITHM_HINTS["视频补帧"]
        if enable_super_resolution:
            return ALGORITHM_HINTS["超分辨率"]
        return "请至少开启补帧或超分其中一个开关。"

    def _refresh_processing_mode_ui(self):
        """刷新组合处理相关控件的显示状态。"""
        current_text = self.algorithm_combo.currentText()
        is_combined = self._supports_combined_processing(current_text)
        enable_interpolation, enable_super_resolution = self._current_processing_switches()
        show_order = is_combined and enable_interpolation and enable_super_resolution

        self.processing_switch_group.setVisible(is_combined)
        self.rife_group.setVisible(is_combined and enable_interpolation)
        self.process_order_label.setVisible(show_order)
        self.process_order_combo.setVisible(show_order)
        self.algorithm_hint_label.setText(self._build_algorithm_hint())
        if is_combined:
            self.delivery_focus_label.setText(
                f"当前主流程：{current_text}。如需联动另一种处理方式，可直接在下方开启并设定顺序。"
            )
        else:
            self.delivery_focus_label.setText(
                f"当前主流程：{current_text}。这个模式会按对应方法页的设置执行，再结合下方编码与输出参数完成交付。"
            )

    def _on_processing_switch_changed(self, *_):
        """开关或顺序变化后刷新界面和摘要。"""
        self._refresh_processing_mode_ui()
        self._refresh_summary()

    def _on_algorithm_changed(self, text: str):
        if self._supports_combined_processing(text):
            enable_interpolation, enable_super_resolution = self._default_processing_switches(text)
            self.enable_interpolation_check.setChecked(enable_interpolation)
            self.enable_super_resolution_check.setChecked(enable_super_resolution)
        self._refresh_processing_mode_ui()
        self._refresh_summary()

    # ---- 帧率模式切换 ----

    def _on_fps_mode_changed(self, text: str):
        """帧率模式切换时更新控件可见性和预览。"""
        is_target_mode = text == "目标帧率"
        self.target_fps_spin.setVisible(is_target_mode)
        # 目标帧率模式下倍率由 CLI 自动计算，隐藏手动倍率选择
        # 但保持 multi_combo 可见以便查看/在倍率模式下使用
        self._update_fps_preview()
        self._refresh_summary()

    def _on_target_fps_changed(self, value: int):
        """目标帧率值变化时更新预览。"""
        self._update_fps_preview()
        self._refresh_summary()

    def _current_fps_mode(self) -> str:
        """返回当前帧率模式（CLI 参数值）。"""
        return FPS_MODE_MAP.get(self.fps_mode_combo.currentText(), "multi")

    def _current_target_fps(self) -> float:
        """返回当前目标帧率。"""
        return float(self.target_fps_spin.value())

    def _update_fps_preview(self):
        """更新帧率预览标签。"""
        fps_mode = self._current_fps_mode()
        if fps_mode == "target":
            target_fps = self._current_target_fps()
            source_fps = self._to_float(self._video_info.get("fps")) if self._video_info else None
            if source_fps and source_fps > 0:
                import math

                multi = max(2, math.ceil(target_fps / source_fps))
                interpolated_fps = source_fps * multi
                if interpolated_fps > target_fps:
                    self.fps_preview_label.setText(
                        f"预览：{self._format_fps(source_fps)}fps → {multi}x 补帧 → "
                        f"{self._format_fps(interpolated_fps)}fps → 压制到 {self._format_fps(target_fps)}fps"
                    )
                else:
                    self.fps_preview_label.setText(
                        f"预览：{self._format_fps(source_fps)}fps → {multi}x 补帧 → "
                        f"{self._format_fps(interpolated_fps)}fps（无需压制）"
                    )
            else:
                self.fps_preview_label.setText("请先导入视频以预览帧率计算结果。")
        else:
            self.fps_preview_label.setText("补帧倍率模式：输出帧率 = 源帧率 × 倍率")

    def _apply_preset(self, preset_name: str):
        self._switch_to_algorithm_page("视频补帧")
        if preset_name == "smooth_60":
            self.algorithm_combo.setCurrentText("视频补帧")
            self.backend_combo.setCurrentText("PyTorch")
            self.fps_mode_combo.setCurrentText("目标帧率")
            self.target_fps_spin.setValue(60)
            self.model_combo.setCurrentText("4.25")
            self.scale_spin.setValue(1.0)
            self.fp16_check.setChecked(False)
            self.codec_combo.setCurrentText("libx264")
            self.crf_spin.setValue(18)
            self.preset_combo.setCurrentText("medium")
            self.preset_note_label.setText("已应用\u201c流畅 60fps\u201d：目标帧率模式，自动计算补帧倍率。")
        elif preset_name == "high_quality_120":
            self.algorithm_combo.setCurrentText("视频补帧")
            self.backend_combo.setCurrentText("PyTorch")
            self.fps_mode_combo.setCurrentText("目标帧率")
            self.target_fps_spin.setValue(120)
            self.model_combo.setCurrentText("4.26")
            self.scale_spin.setValue(1.0)
            self.fp16_check.setChecked(False)
            self.codec_combo.setCurrentText("libx265")
            self.crf_spin.setValue(16)
            self.preset_combo.setCurrentText("slow")
            self.preset_note_label.setText(
                "已应用\u201c高质 120fps\u201d：目标帧率模式，适合追求流畅和质量的离线处理。"
            )
        elif preset_name == "save_vram_4k":
            self.algorithm_combo.setCurrentText("视频补帧")
            self.backend_combo.setCurrentText("PyTorch")
            self.fps_mode_combo.setCurrentText("目标帧率")
            self.target_fps_spin.setValue(60)
            self.model_combo.setCurrentText("4.25")
            self.scale_spin.setValue(0.5)
            self.fp16_check.setChecked(True)
            self.codec_combo.setCurrentText("libx265")
            self.crf_spin.setValue(20)
            self.preset_combo.setCurrentText("medium")
            self.preset_note_label.setText(
                "已应用\u201c4K 节省显存\u201d：目标帧率模式，优先降低超高分辨率素材的显存压力。"
            )

        self._update_fps_preview()
        self.status_label.setText("已应用快捷预设")
        self._refresh_summary()

    # ---- 启动处理 ----

    def _start_process(self):
        input_path = self.input_path_edit.text().strip()
        if not input_path:
            self._switch_workspace_page(1)
            self.result_label.setText("❌ 请先选择视频文件")
            self.result_label.setStyleSheet("color: #F87171;")
            self.process_state_label.setText("任务尚未开始，因为当前没有输入素材。")
            return

        if not os.path.isfile(input_path):
            self._switch_workspace_page(1)
            self.result_label.setText("❌ 输入文件不存在")
            self.result_label.setStyleSheet("color: #F87171;")
            self.process_state_label.setText("任务尚未开始，因为输入文件路径不可用。")
            return

        algorithm_text = self.algorithm_combo.currentText()
        algorithm = ALGORITHM_MAP.get(algorithm_text, "frame_interpolation")
        backend = "pytorch" if self.backend_combo.currentText() == "PyTorch" else "paddle"
        fps = 60.0  # 保留作为兼容默认值
        fps_mode = self._current_fps_mode()
        target_fps = self._current_target_fps() if fps_mode == "target" else 0.0
        codec = self.codec_combo.currentText()
        crf = self.crf_spin.value()
        preset = self.preset_combo.currentText()
        multi = self._current_multi()
        model = self.model_combo.currentText()
        scale = self.scale_spin.value()
        fp16 = self.fp16_check.isChecked()
        enable_interpolation = False
        enable_super_resolution = False
        process_order = self._current_process_order()
        output = self.output_path_edit.text().strip() or None
        output_dir = self.output_dir_edit.text().strip() or None
        temp_dir = self.temp_dir_edit.text().strip() or None
        sr_scale_factor = self.sr_scale_spin.value()
        sr_algorithm = self.sr_algorithm_combo.currentText()

        if self._supports_combined_processing(algorithm_text):
            enable_interpolation, enable_super_resolution = self._current_processing_switches()
            if not enable_interpolation and not enable_super_resolution:
                self._switch_workspace_page(self._workspace_index("deliver"))
                self.result_label.setText("\u274c 请至少开启\u201c补帧\u201d或\u201c超分\u201d其中一个开关")
                self.result_label.setStyleSheet("color: #F87171;")
                self.process_state_label.setText("任务尚未开始，因为当前没有启用任何增强处理步骤。")
                return
            algorithm = "frame_interpolation" if enable_interpolation else "super_resolution"

        self._processing = True
        self._last_output_path = ""
        self.start_btn.setEnabled(False)
        self.start_btn.setText("处理中...")
        self.progress_bar.setValue(0)
        self.progress_label.setText("0%")
        self.frame_label.setText("等待第一条进度反馈...")
        self.process_state_label.setText("任务已提交到 CLI 后端，窗口会持续同步处理进度。")
        self.result_label.setText("")
        self.result_label.setStyleSheet("color: #CBD5E1;")
        self.status_label.setText("正在处理视频...")

        def _on_progress(current, total, percent):
            self._process_bridge.progress.emit(current, total, percent)

        def _on_completed(result):
            self._process_bridge.completed.emit(result)

        def _on_error(message):
            self._process_bridge.error.emit(message)

        self.cli.process_async(
            input_path=input_path,
            algorithm=algorithm,
            output=output,
            fps=fps,
            fps_mode=fps_mode,
            target_fps=target_fps,
            codec=codec,
            crf=crf,
            preset=preset,
            backend=backend,
            multi=multi,
            model=model,
            scale=scale,
            fp16=fp16,
            enable_interpolation=enable_interpolation,
            enable_super_resolution=enable_super_resolution,
            process_order=process_order,
            output_dir=output_dir,
            temp_dir=temp_dir,
            sr_scale_factor=sr_scale_factor,
            sr_algorithm=sr_algorithm,
            on_progress=_on_progress,
            on_completed=_on_completed,
            on_error=_on_error,
        )

    # ---- 进度/完成/错误回调 ----

    def _on_progress(
        self,
        current: int,
        total: int,
        percent: float,
        stage: str,
        stage_index: int,
        stage_total: int,
    ):
        self.progress_bar.setValue(int(percent))
        self.progress_label.setText(f"{percent:.1f}%")

        if stage_total > 1 and stage:
            self.frame_label.setText(f"阶段 {stage_index}/{stage_total}：{stage} · 第 {current} 帧 / 共 {total} 帧")
            self.process_state_label.setText(f"当前阶段：{stage}（{stage_index}/{stage_total}）")
        else:
            self.frame_label.setText(f"当前进度：第 {current} 帧 / 共 {total} 帧")
            self.process_state_label.setText("CLI 正在持续回传进度，处理期间可以继续查看右侧任务摘要。")

    def _on_completed(self, result: dict):
        self._processing = False
        self.start_btn.setEnabled(True)
        self.start_btn.setText("开始处理")
        self.progress_bar.setValue(100)
        self.progress_label.setText("100%")

        output_path = result.get("output_path", "?")
        frames = result.get("processed_frames", 0)
        time_seconds = result.get("time_seconds", 0)
        self._last_output_path = output_path

        self.frame_label.setText(f"处理完成：共 {frames} 帧")
        self.process_state_label.setText("任务已完成，可以直接根据输出路径确认结果文件。")
        self.result_label.setText(f"✅ 处理完成\n输出文件：{output_path}\n处理帧数：{frames}\n耗时：{time_seconds}s")
        self.result_label.setStyleSheet("color: #4ADE80;")
        self.status_label.setText("处理完成")
        self._refresh_summary()

    def _on_error(self, message: str):
        self._processing = False
        self.start_btn.setEnabled(True)
        self.start_btn.setText("开始处理")
        self.process_state_label.setText("任务执行失败，请优先检查依赖状态和输入参数。")
        self.result_label.setText(f"❌ 处理失败：{message}")
        self.result_label.setStyleSheet("color: #F87171;")
        self.status_label.setText("处理失败")
        self._refresh_summary()

    # ---- 摘要刷新 ----

    def _refresh_summary(self, *_):
        input_path = self.input_path_edit.text().strip()
        output_path = self.output_path_edit.text().strip()
        algorithm_text = self.algorithm_combo.currentText()
        processing_label = self._current_processing_label(algorithm_text)
        input_name = os.path.basename(input_path) if input_path else "未选择素材"

        if input_path:
            parent = os.path.dirname(input_path)
            input_summary = f"{input_name}\n{parent}"
        else:
            input_summary = "拖放或浏览一个视频文件后，这里会显示素材路径。"

        video_summary = self._build_video_summary()
        strategy_summary = self._build_strategy_summary(algorithm_text)
        runtime_summary = self._build_runtime_summary(algorithm_text)
        encode_summary = (
            f"{self.codec_combo.currentText()} · CRF {self.crf_spin.value()} · {self.preset_combo.currentText()}"
        )

        if output_path:
            output_summary = output_path
            self.output_hint_label.setText(f"输出会写入你指定的位置：{os.path.basename(output_path)}")
        elif self._last_output_path and not self._processing:
            output_summary = f"自动生成\n{self._last_output_path}"
            self.output_hint_label.setText("最近一次任务已经生成实际输出路径。")
        else:
            output_summary = "自动生成（由 CLI 决定输出目录和文件名）"
            self.output_hint_label.setText("当前未指定输出路径。")

        self._summary_values["input"].setText(input_summary)
        self._summary_values["video"].setText(video_summary)
        self._summary_values["strategy"].setText(strategy_summary)
        self._summary_values["runtime"].setText(runtime_summary)
        self._summary_values["encode"].setText(encode_summary)
        self._summary_values["output"].setText(output_summary)

        self.process_summary_label.setText(f"当前任务：{processing_label} · {self._format_target_overview()}")
        self.recommend_label.setText(self._build_recommendation())

    def _build_video_summary(self) -> str:
        if not self._video_info:
            return "尚未读取素材信息"

        width = self._video_info.get("width", "?")
        height = self._video_info.get("height", "?")
        fps = self._format_fps(self._video_info.get("fps"))
        frames = self._video_info.get("frames", "?")
        duration = self._format_duration(self._video_info.get("duration"))
        audio = "有音频" if self._video_info.get("has_audio") else "无音频"
        return f"{width} x {height} · {fps} fps · {frames} 帧 · {duration} · {audio}"

    def _build_strategy_summary(self, algorithm_text: str) -> str:
        fps_mode = self._current_fps_mode()
        if fps_mode == "target":
            fps_desc = f"目标 {self._format_fps(self._current_target_fps())} fps"
        else:
            fps_desc = f"{self.multi_combo.currentText()} 补帧"

        if self._supports_combined_processing(algorithm_text):
            enable_interpolation, enable_super_resolution = self._current_processing_switches()
            if enable_interpolation and enable_super_resolution:
                return f"补帧 + 超分 · {self.process_order_combo.currentText()} · {fps_desc}"
            if enable_interpolation:
                return f"视频补帧 · {fps_desc}"
            if enable_super_resolution:
                return "超分辨率 · 强调清晰度提升"
            return "未启用补帧或超分"
        if algorithm_text == "动漫帧优化":
            return f"{algorithm_text} · 更偏向动画素材的过渡优化"
        return f"{algorithm_text} · 重点调整编码与容器"

    def _build_runtime_summary(self, algorithm_text: str) -> str:
        backend = self.backend_combo.currentText()
        if self._supports_combined_processing(algorithm_text):
            enable_interpolation, enable_super_resolution = self._current_processing_switches()
            details = [backend]
            if enable_interpolation:
                fp16 = "开启 FP16" if self.fp16_check.isChecked() else "关闭 FP16"
                details.append(
                    f"RIFE {self.model_combo.currentText()} · "
                    f"{self.multi_combo.currentText()} · 缩放 {self.scale_spin.value():.1f} · {fp16}"
                )
            if enable_super_resolution:
                details.append("超分步骤已启用")
            if enable_interpolation and enable_super_resolution:
                details.append(self.process_order_combo.currentText())
            return " · ".join(details)
        return f"{backend} · 输出编码链保持启用"

    def _build_recommendation(self) -> str:
        input_path = self.input_path_edit.text().strip()
        if not input_path:
            return "先拖入一段素材，系统会自动补全帧率、分辨率和音频信息，再决定是否需要补帧或压缩。"

        if not self._video_info:
            return "素材已选中，建议先读取基础信息，再判断补帧倍率和编码方式是否合适。"

        algorithm_text = self.algorithm_combo.currentText()
        width = self._to_float(self._video_info.get("width"))
        height = self._to_float(self._video_info.get("height"))
        source_fps = self._to_float(self._video_info.get("fps"))
        fps_mode = self._current_fps_mode()
        target_fps = self._current_target_fps() if fps_mode == "target" else None
        multi = self._current_multi()

        if self._supports_combined_processing(algorithm_text):
            enable_interpolation, enable_super_resolution = self._current_processing_switches()
            if not enable_interpolation and not enable_super_resolution:
                return "请先开启补帧或超分开关，再启动组合处理任务。"
            if enable_interpolation and enable_super_resolution:
                if width and height and max(width, height) >= 2160:
                    return "双开模式建议先做一小段测试，观察当前顺序在高分辨率素材上的细节和运动边缘表现。"
                return (
                    f"当前已启用补帧和超分，并按\u201c{self.process_order_combo.currentText()}\u201d执行；"
                    "如果更看重稳定性，建议先用短片段确认顺序效果。"
                )
            if enable_interpolation:
                if width and height and max(width, height) >= 2160 and self.scale_spin.value() >= 1.0:
                    return "检测到高分辨率素材，桌面端补帧时建议把分辨率缩放调到 0.5 并开启 FP16，能明显降低显存压力。"
                if fps_mode == "multi" and source_fps and target_fps is None:
                    # 补帧倍率模式下的建议
                    estimated_fps = source_fps * multi
                    return (
                        f"当前源素材约 {self._format_fps(source_fps)} fps，"
                        f"{multi}x 补帧后约 {self._format_fps(estimated_fps)} fps。"
                    )
                if source_fps and target_fps and target_fps <= source_fps:
                    return "目标帧率没有高于源帧率，补帧收益可能有限；如果只是转码，可以考虑直接用格式转换。"
                if self.codec_combo.currentText() == "copy":
                    return "补帧通常会生成新的视频流，当前编码器设为 copy 可能不适合，建议改为 libx264 或 libx265。"
                return "当前配置比较均衡，适合直接开始处理；如果更重视体积，可以把编码器切到 libx265。"
            return "超分场景通常更依赖编码质量，建议优先使用 libx265 或 AV1，并适当降低 CRF 以保留细节。"

        if algorithm_text == "视频补帧":
            if width and height and max(width, height) >= 2160 and self.scale_spin.value() >= 1.0:
                return "检测到高分辨率素材，桌面端补帧时建议把分辨率缩放调到 0.5 并开启 FP16，能明显降低显存压力。"
            if fps_mode == "multi" and source_fps:
                estimated_fps = source_fps * multi
                return (
                    f"当前源素材约 {self._format_fps(source_fps)} fps，"
                    f"{multi}x 补帧后约 {self._format_fps(estimated_fps)} fps。"
                )
            if fps_mode == "target" and source_fps and target_fps and target_fps <= source_fps:
                return "目标帧率没有高于源帧率，补帧收益可能有限；如果只是转码，可以考虑直接用格式转换。"
            if self.codec_combo.currentText() == "copy":
                return "补帧通常会生成新的视频流，当前编码器设为 copy 可能不适合，建议改为 libx264 或 libx265。"
            return "当前配置比较均衡，适合直接开始处理；如果更重视体积，可以把编码器切到 libx265。"

        if algorithm_text == "格式转换":
            return "如果你的目标只是压缩体积，优先关注编码器、CRF 和预设即可，算法相关参数影响较小。"

        if algorithm_text == "超分辨率":
            return "超分场景通常更依赖编码质量，建议优先使用 libx265 或 AV1，并适当降低 CRF 以保留细节。"

        return "动漫类素材建议先做一小段测试，确认过渡和边缘表现后再处理整段视频。"

    def _format_target_overview(self) -> str:
        algorithm_text = self.algorithm_combo.currentText()
        fps_mode = self._current_fps_mode()
        if fps_mode == "target":
            fps_desc = f"目标 {self._format_fps(self._current_target_fps())} fps"
        else:
            fps_desc = f"{self.multi_combo.currentText()} 补帧"

        if self._supports_combined_processing(algorithm_text):
            enable_interpolation, enable_super_resolution = self._current_processing_switches()
            if enable_interpolation and enable_super_resolution:
                return f"{self.process_order_combo.currentText()} / {self.codec_combo.currentText()}"
            if enable_interpolation:
                return f"{fps_desc} / {self.codec_combo.currentText()}"
            if enable_super_resolution:
                return f"超分优先 / {self.codec_combo.currentText()} / {self.preset_combo.currentText()}"
            return self.codec_combo.currentText()
        if algorithm_text == "视频补帧":
            return f"{fps_desc} / {self.codec_combo.currentText()}"
        return f"{self.codec_combo.currentText()} / {self.preset_combo.currentText()}"

    # ---- 格式化辅助方法 ----

    def _reset_video_metrics(self):
        self._set_video_metrics("--")

    def _set_video_metrics(self, text: str):
        for label in self._info_labels.values():
            label.setText(text)

    def _current_multi(self) -> int:
        return int(self.multi_combo.currentText().replace("x", ""))

    def _format_duration(self, duration) -> str:
        seconds = self._to_float(duration)
        if seconds is None:
            return str(duration) if duration not in (None, "") else "--"
        total_seconds = max(int(seconds), 0)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _format_fps(self, value) -> str:
        numeric = self._to_float(value)
        if numeric is None:
            return str(value) if value not in (None, "") else "--"
        if abs(numeric - round(numeric)) < 0.01:
            return str(int(round(numeric)))
        return f"{numeric:.2f}".rstrip("0").rstrip(".")

    def _to_float(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    # ---- Widget 刷新 / resize / 布局模式 ----

    def _refresh_widget_style(self, widget: QWidget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._update_layout_mode()

    def _update_layout_mode(self):
        wide_mode = self.width() >= 1360
        direction = QBoxLayout.Direction.LeftToRight if wide_mode else QBoxLayout.Direction.TopToBottom
        self.main_columns.setDirection(direction)
        self.nav_panel.setMaximumWidth(260 if wide_mode else 16777215)
        self.nav_panel.setMinimumWidth(220 if wide_mode else 0)
        self.sidebar_panel.setMaximumWidth(440 if wide_mode else 16777215)
