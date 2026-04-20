"""MainWindow UI 构建 Mixin — 所有 _build_* 方法、_init_ui、_init_statusbar 及工具方法。"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .constants import (
    ALGORITHM_MAP,
    FPS_MODE_MAP,
    PROCESS_ORDER_MAP,
    RIFE_VERSIONS,
    WORKSPACE_PAGES,
)
from .stylesheet import DARK_STYLESHEET


class MainWindowUIBuilder:
    """UI 构建 Mixin：所有界面组装方法。

    不定义 __init__，所有属性在 MainWindow.__init__ 中初始化。
    通过 self 访问 MainWindow 实例属性。
    """

    def _init_ui(self):
        self.setWindowTitle("视频补帧与超分软件")
        self.setMinimumSize(1160, 820)
        self.resize(1380, 920)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.setCentralWidget(scroll)

        central = QWidget()
        central.setObjectName("rootPanel")
        scroll.setWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setSpacing(18)
        root_layout.setContentsMargins(28, 24, 28, 24)

        root_layout.addWidget(self._build_hero_section())

        workspace = QWidget()
        self.main_columns = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.main_columns.setSpacing(18)
        workspace.setLayout(self.main_columns)

        # 处理类型由左侧方法页驱动，这个控件仅作为统一状态源使用。
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems(ALGORITHM_MAP.keys())
        self.algorithm_combo.setCurrentText("视频补帧")

        self.nav_panel = self._build_navigation_panel()

        self.workspace_stack = QStackedWidget()
        self.workspace_stack.setObjectName("workspaceStack")
        self.workspace_stack.addWidget(
            self._build_workspace_page(
                "OVERVIEW",
                "工作台总览",
                "参考 SVFI 的工作台感和 VSET 的步骤分层，把环境、素材概览和执行建议放到最前面。",
                [
                    self._build_env_section(),
                    self._build_info_section(),
                ],
            )
        )
        self.workspace_stack.addWidget(
            self._build_workspace_page(
                "SOURCE",
                "素材与路径",
                "先确定输入文件和素材基础信息，再进入不同处理方式的独立页面。",
                [
                    self._build_file_section(),
                    self._build_source_guide_section(),
                ],
            )
        )
        self.workspace_stack.addWidget(
            self._build_workspace_page(
                "INTERPOLATION",
                "视频补帧",
                "这里专门放 RIFE 相关参数和补帧预设；进入本页会自动把当前主流程切到'视频补帧'。",
                [
                    self._build_interpolation_workspace_section(),
                ],
            )
        )
        self.workspace_stack.addWidget(
            self._build_workspace_page(
                "SUPER RESOLUTION",
                "超分辨率",
                "这里专注超分流程说明；进入本页会自动把当前主流程切到'超分辨率'，联动补帧可在导出页统一编排。",
                [
                    self._build_super_resolution_workspace_section(),
                ],
            )
        )
        self.workspace_stack.addWidget(
            self._build_workspace_page(
                "ANIME",
                "动漫帧优化",
                "动画素材单独成页，先看适用建议，再到导出页统一完成编码与输出设置。",
                [
                    self._build_anime_workspace_section(),
                ],
            )
        )
        self.workspace_stack.addWidget(
            self._build_workspace_page(
                "FORMAT",
                "格式转换",
                "格式转换也单独占页，方法页负责说明当前策略，导出页负责真正的编码交付。",
                [
                    self._build_format_workspace_section(),
                ],
            )
        )
        self.workspace_stack.addWidget(
            self._build_workspace_page(
                "DELIVER",
                "导出与交付",
                "在这里统一确认主流程、补帧/超分联动、编码参数和输出路径，然后直接启动处理。",
                [
                    self._build_delivery_flow_section(),
                    self._build_encode_section(),
                    self._build_output_review_section(),
                ],
            )
        )

        self.content_panel = QWidget()
        content_layout = QVBoxLayout(self.content_panel)
        content_layout.setSpacing(0)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.workspace_stack)

        self.sidebar_panel = QWidget()
        sidebar_layout = QVBoxLayout(self.sidebar_panel)
        sidebar_layout.setSpacing(16)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.addWidget(self._build_process_section())
        sidebar_layout.addWidget(self._build_summary_section())
        sidebar_layout.addStretch()

        self.main_columns.addWidget(self.nav_panel, 2)
        self.main_columns.addWidget(self.content_panel, 6)
        self.main_columns.addWidget(self.sidebar_panel, 3)
        root_layout.addWidget(workspace)
        root_layout.addStretch()

        self._switch_workspace_page(0)
        self._apply_stylesheet()

    def _build_hero_section(self) -> QFrame:
        card = QFrame()
        card.setObjectName("heroCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        left = QVBoxLayout()
        left.setSpacing(10)

        eyebrow = QLabel("DESKTOP WORKBENCH")
        eyebrow.setObjectName("heroEyebrow")
        left.addWidget(eyebrow, alignment=Qt.AlignmentFlag.AlignLeft)

        title = QLabel("视频补帧与超分桌面工作台")
        title.setObjectName("heroTitle")
        left.addWidget(title)

        subtitle = QLabel(
            "把素材导入、参数配置、进度跟踪和结果确认收拢到同一块桌面工作区，更适合长时间处理任务和高分辨率素材。"
        )
        subtitle.setObjectName("heroSubtitle")
        subtitle.setWordWrap(True)
        left.addWidget(subtitle)

        steps = QLabel("1 选择素材  ·  2 应用预设或微调参数  ·  3 启动处理并在右侧追踪结果")
        steps.setObjectName("heroSteps")
        left.addWidget(steps)

        layout.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(12)
        right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        self.hero_state_badge = QLabel("环境检测中")
        self.hero_state_badge.setObjectName("heroStateBadge")
        self.hero_state_badge.setProperty("state", "pending")
        right.addWidget(self.hero_state_badge, alignment=Qt.AlignmentFlag.AlignRight)

        tag_row = QHBoxLayout()
        tag_row.setSpacing(8)
        for text in ("拖放导入", "RIFE 系列模型', '桌面侧栏摘要"):
            tag = QLabel(text)
            tag.setObjectName("heroTag")
            tag_row.addWidget(tag)
        right.addLayout(tag_row)

        layout.addLayout(right)
        return card

    def _build_navigation_panel(self) -> QFrame:
        rail = QFrame()
        rail.setObjectName("navRail")

        layout = QVBoxLayout(rail)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        badge = QLabel("WORKFLOW")
        badge.setObjectName("navBadge")
        layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignLeft)

        title = QLabel("参考型前端布局")
        title.setObjectName("navTitle")
        layout.addWidget(title)

        description = QLabel(
            "左侧按素材、处理方式和导出编排切页；每种帧处理方式独立占一页，右侧固定显示任务状态和执行摘要。"
        )
        description.setObjectName("navNote")
        description.setWordWrap(True)
        layout.addWidget(description)

        self._workspace_nav_buttons = []
        for index, (_, title_text, subtitle) in enumerate(WORKSPACE_PAGES, start=1):
            button = QPushButton(f"{index:02d}  {title_text}\n{subtitle}")
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, i=index - 1: self._switch_workspace_page(i))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(button)
            self._workspace_nav_buttons.append(button)

        layout.addStretch()

        footer = QLabel("像 VSET 一样把流程拆成独立页面，也像 SVFI 一样把关键执行反馈固定在同一工作台。")
        footer.setObjectName("navFooter")
        footer.setWordWrap(True)
        layout.addWidget(footer)
        return rail

    def _build_workspace_page(
        self,
        eyebrow: str,
        title: str,
        description: str,
        sections: list[QWidget],
    ) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        layout.setContentsMargins(0, 0, 0, 0)

        intro = QFrame()
        intro.setObjectName("pageIntroCard")
        intro_layout = QVBoxLayout(intro)
        intro_layout.setContentsMargins(20, 18, 20, 18)
        intro_layout.setSpacing(8)

        eyebrow_label = QLabel(eyebrow)
        eyebrow_label.setObjectName("pageIntroEyebrow")
        intro_layout.addWidget(eyebrow_label)

        title_label = QLabel(title)
        title_label.setObjectName("pageIntroTitle")
        intro_layout.addWidget(title_label)

        desc_label = QLabel(description)
        desc_label.setObjectName("pageIntroText")
        desc_label.setWordWrap(True)
        intro_layout.addWidget(desc_label)

        layout.addWidget(intro)
        for section in sections:
            layout.addWidget(section)
        layout.addStretch()
        return page

    def _build_output_review_section(self) -> QGroupBox:
        group = QGroupBox("导出前检查")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        note = QLabel("这里汇总输出相关的最后一步确认。方法页负责算法参数，导出页负责把流程、编码和落盘统一确认。")
        note.setObjectName("cardNote")
        note.setWordWrap(True)
        layout.addWidget(note)

        checklist = QFrame()
        checklist.setObjectName("hintBanner")
        checklist_layout = QVBoxLayout(checklist)
        checklist_layout.setContentsMargins(14, 12, 14, 12)
        checklist_layout.setSpacing(8)

        for text in (
            "1. 确认输入素材已经读取到帧率、分辨率和音频信息。",
            "2. 确认你刚刚进入过正确的处理方式页面，当前主流程会跟随方法页切换。",
            "3. 如果同时启用补帧和超分，确认执行顺序符合当前素材目标。",
            "4. 如需固定输出位置，请在下方指定输出路径；否则由 CLI 自动生成。",
        ):
            label = QLabel(text)
            label.setObjectName("hintText")
            label.setWordWrap(True)
            checklist_layout.addWidget(label)

        layout.addWidget(checklist)
        layout.addWidget(self._build_output_section())
        return group

    def _build_source_guide_section(self) -> QGroupBox:
        group = QGroupBox("素材准备建议")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        note = QLabel(
            "SVFI 的主界面会先把\u201c输入视频\u201d和\u201c输出位置\u201d放在最显眼的位置。这里把素材准备和处理方式拆开，让每种帧处理方案都单独占页。"
        )
        note.setObjectName("cardNote")
        note.setWordWrap(True)
        layout.addWidget(note)

        steps = QFrame()
        steps.setObjectName("hintBanner")
        steps_layout = QVBoxLayout(steps)
        steps_layout.setContentsMargins(14, 12, 14, 12)
        steps_layout.setSpacing(8)

        for text in (
            "1. 导入视频后先读取基础信息，确认源帧率和分辨率是否正常。",
            "2. 再切到对应处理页完成方法参数配置，例如'视频补帧'或'超分辨率'。",
            "3. 最后进入'导出'页统一编排流程、设置编码和输出路径。",
        ):
            label = QLabel(text)
            label.setObjectName("hintText")
            label.setWordWrap(True)
            steps_layout.addWidget(label)

        layout.addWidget(steps)
        return group

    def _build_env_section(self) -> QGroupBox:
        group = QGroupBox("运行环境")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        note = QLabel("关键依赖状态会直接影响桌面端是否能够顺利调用 CLI 后端。")
        note.setObjectName("cardNote")
        note.setWordWrap(True)
        layout.addWidget(note)

        badge_grid = QGridLayout()
        badge_grid.setHorizontalSpacing(10)
        badge_grid.setVerticalSpacing(10)

        for index, (key, title) in enumerate(
            [
                ("ffmpeg", "FFmpeg"),
                ("gpu", "GPU"),
                ("pytorch", "PyTorch"),
                ("paddle", "Paddle"),
                ("rife", "RIFE"),
            ]
        ):
            badge, value_label = self._create_env_badge(title)
            badge_grid.addWidget(badge, index // 3, index % 3)
            self._env_badges[key] = (badge, value_label)

        layout.addLayout(badge_grid)

        footer = QHBoxLayout()
        footer.setSpacing(12)

        self.env_label = QLabel("正在检测 FFmpeg、GPU 和 Tensor 后端...")
        self.env_label.setObjectName("cardNote")
        self.env_label.setWordWrap(True)
        footer.addWidget(self.env_label, 1)

        check_btn = QPushButton("重新检查")
        check_btn.setObjectName("secondaryButton")
        check_btn.clicked.connect(self._check_environment)
        footer.addWidget(check_btn)

        layout.addLayout(footer)
        return group

    def _build_file_section(self) -> QGroupBox:
        group = QGroupBox("素材导入")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        note = QLabel("支持拖放视频文件到窗口任意位置，导入后会自动读取基础信息并刷新右侧摘要。")
        note.setObjectName("cardNote")
        note.setWordWrap(True)
        layout.addWidget(note)

        row = QHBoxLayout()
        row.setSpacing(10)

        self.input_path_edit = QLineEdit()
        self.input_path_edit.setPlaceholderText("点击'浏览'或直接拖放视频文件到窗口中...")
        self.input_path_edit.setReadOnly(True)
        row.addWidget(self.input_path_edit, 1)

        browse_btn = QPushButton("浏览文件")
        browse_btn.clicked.connect(self._browse_input)
        row.addWidget(browse_btn)
        layout.addLayout(row)

        self.file_meta_label = QLabel("还没有选择素材。")
        self.file_meta_label.setObjectName("cardNote")
        self.file_meta_label.setWordWrap(True)
        layout.addWidget(self.file_meta_label)
        return group

    def _build_info_section(self) -> QGroupBox:
        group = QGroupBox("素材概览")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        note = QLabel("读取成功后会展示源视频的核心指标，方便你判断补帧倍率和输出编码方案。")
        note.setObjectName("cardNote")
        note.setWordWrap(True)
        layout.addWidget(note)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        self._info_labels = {}

        metrics = [
            ("fps", "源帧率"),
            ("frames", "总帧数"),
            ("duration", "时长"),
            ("resolution", "分辨率"),
            ("audio", "音频"),
        ]
        for index, (key, title) in enumerate(metrics):
            card, value_label = self._create_metric_card(title)
            grid.addWidget(card, index // 3, index % 3)
            self._info_labels[key] = value_label

        layout.addLayout(grid)

        footer = QHBoxLayout()
        footer.setSpacing(12)

        self.info_hint_label = QLabel("选择素材后会自动查询，也可以手动重新读取一次。")
        self.info_hint_label.setObjectName("cardNote")
        self.info_hint_label.setWordWrap(True)
        footer.addWidget(self.info_hint_label, 1)

        info_btn = QPushButton("重新读取信息")
        info_btn.setObjectName("secondaryButton")
        info_btn.clicked.connect(self._query_video_info)
        footer.addWidget(info_btn)

        layout.addLayout(footer)
        return group

    def _build_preset_section(self) -> QGroupBox:
        group = QGroupBox("快捷预设")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        note = QLabel("预设会帮你快速落到常见桌面处理场景，后续仍然可以继续微调。")
        note.setObjectName("cardNote")
        note.setWordWrap(True)
        layout.addWidget(note)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        smooth_btn = QPushButton("流畅 60fps")
        smooth_btn.setObjectName("secondaryButton")
        smooth_btn.clicked.connect(lambda: self._apply_preset("smooth_60"))
        btn_row.addWidget(smooth_btn)

        high_btn = QPushButton("高质 120fps")
        high_btn.setObjectName("secondaryButton")
        high_btn.clicked.connect(lambda: self._apply_preset("high_quality_120"))
        btn_row.addWidget(high_btn)

        vram_btn = QPushButton("4K 节省显存")
        vram_btn.setObjectName("secondaryButton")
        vram_btn.clicked.connect(lambda: self._apply_preset("save_vram_4k"))
        btn_row.addWidget(vram_btn)

        layout.addLayout(btn_row)

        self.preset_note_label = QLabel("建议先应用一个接近场景的预设，再按素材情况微调模型、倍率和编码器。")
        self.preset_note_label.setObjectName("cardNote")
        self.preset_note_label.setWordWrap(True)
        layout.addWidget(self.preset_note_label)
        return group

    def _build_method_context_section(
        self,
        title: str,
        description: str,
        bullets: tuple[str, ...],
        emphasis: str = "",
    ) -> QGroupBox:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        note = QLabel(description)
        note.setObjectName("cardNote")
        note.setWordWrap(True)
        layout.addWidget(note)

        banner = QFrame()
        banner.setObjectName("hintBanner")
        banner_layout = QVBoxLayout(banner)
        banner_layout.setContentsMargins(14, 12, 14, 12)
        banner_layout.setSpacing(8)

        for text in bullets:
            label = QLabel(text)
            label.setObjectName("hintText")
            label.setWordWrap(True)
            banner_layout.addWidget(label)

        layout.addWidget(banner)

        if emphasis:
            footer = QLabel(emphasis)
            footer.setObjectName("cardNote")
            footer.setWordWrap(True)
            layout.addWidget(footer)

        return group

    def _build_interpolation_workspace_section(self) -> QGroupBox:
        group = QGroupBox("补帧方法页")
        layout = QVBoxLayout(group)
        layout.setSpacing(14)

        layout.addWidget(
            self._build_method_context_section(
                "补帧页说明",
                "这个页面只负责'视频补帧'本身的参数。进入本页时，会把当前主流程切到视频补帧。",
                (
                    "1. 先在这里选择帧率模式（补帧倍率或目标帧率），再调整 RIFE 参数。",
                    "2. 目标帧率模式下，系统自动计算最小倍率，补帧后若超过目标帧率会用 FFmpeg 压制。",
                    "3. 如果需要同时做超分，请到'导出'页打开超分联动。",
                    "4. 编码器、CRF 和输出路径统一在'导出'页确认。",
                ),
                "这样可以保持每种帧处理方式都有自己的独立页面，同时又不会丢掉补帧 + 超分的组合能力。",
            )
        )
        layout.addWidget(self._build_preset_section())

        # 帧率模式组
        fps_mode_group = QGroupBox("帧率模式")
        fps_mode_layout = QGridLayout(fps_mode_group)
        fps_mode_layout.setHorizontalSpacing(14)
        fps_mode_layout.setVerticalSpacing(12)

        fps_mode_layout.addWidget(QLabel("模式选择"), 0, 0)
        self.fps_mode_combo = QComboBox()
        self.fps_mode_combo.addItems(FPS_MODE_MAP.keys())
        self.fps_mode_combo.setCurrentText("补帧倍率")
        fps_mode_layout.addWidget(self.fps_mode_combo, 0, 1)

        # 目标帧率控件（仅目标帧率模式可见）
        fps_mode_layout.addWidget(QLabel("目标帧率"), 0, 2)
        self.target_fps_spin = QSpinBox()
        self.target_fps_spin.setRange(1, 240)
        self.target_fps_spin.setValue(60)
        self.target_fps_spin.setSuffix(" fps")
        self.target_fps_spin.setVisible(False)
        fps_mode_layout.addWidget(self.target_fps_spin, 0, 3)

        # 帧率预览标签
        self.fps_preview_label = QLabel("")
        self.fps_preview_label.setObjectName("cardNote")
        self.fps_preview_label.setWordWrap(True)
        fps_mode_layout.addWidget(self.fps_preview_label, 1, 0, 1, 4)

        layout.addWidget(fps_mode_group)

        self.rife_group = QGroupBox("RIFE 补帧细节")
        rife_layout = QGridLayout(self.rife_group)
        rife_layout.setHorizontalSpacing(14)
        rife_layout.setVerticalSpacing(12)

        rife_layout.addWidget(QLabel("模型版本"), 0, 0)
        self.model_combo = QComboBox()
        self.model_combo.addItems(RIFE_VERSIONS)
        self.model_combo.setCurrentText("4.25")
        self.model_combo.setEditable(True)
        rife_layout.addWidget(self.model_combo, 0, 1)

        rife_layout.addWidget(QLabel("补帧倍率"), 0, 2)
        self.multi_combo = QComboBox()
        self.multi_combo.addItems(["2x", "4x"])
        self.multi_combo.setCurrentText("2x")
        rife_layout.addWidget(self.multi_combo, 0, 3)

        rife_layout.addWidget(QLabel("分辨率缩放"), 1, 0)
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.1, 2.0)
        self.scale_spin.setValue(1.0)
        self.scale_spin.setSingleStep(0.1)
        self.scale_spin.setDecimals(1)
        rife_layout.addWidget(self.scale_spin, 1, 1)

        self.fp16_check = QCheckBox("启用半精度推理(FP16)")
        rife_layout.addWidget(self.fp16_check, 1, 2, 1, 2)

        layout.addWidget(self.rife_group)
        return group

    def _build_super_resolution_workspace_section(self) -> QGroupBox:
        group = QGroupBox("超分方法页")
        layout = QVBoxLayout(group)
        layout.setSpacing(14)

        layout.addWidget(
            self._build_method_context_section(
                "超分页说明",
                "这个页面只负责'超分辨率'流程本身。进入本页时，会把当前主流程切到超分辨率。",
                (
                    "1. 当前桌面端已经把超分拆成独立页面，方便后续继续接入真实 SR 参数。",
                    "2. 如果你想和补帧串联，请到'导出'页勾选补帧联动，并选择先后顺序。",
                    "3. 编码与输出位置仍然统一放在'导出'页处理。",
                ),
                "现在的超分后端仍是占位实现，这一页先把流程结构和交互位置稳定下来，后续接入真实模型时可以直接扩展。",
            )
        )

        self.sr_param_group = QGroupBox("超分参数（实验性）")
        sr_layout = QGridLayout(self.sr_param_group)
        sr_layout.setHorizontalSpacing(14)
        sr_layout.setVerticalSpacing(12)

        sr_layout.addWidget(QLabel("放大倍率"), 0, 0)
        self.sr_scale_spin = QDoubleSpinBox()
        self.sr_scale_spin.setRange(0.5, 4.0)
        self.sr_scale_spin.setValue(2.0)
        self.sr_scale_spin.setSingleStep(0.5)
        self.sr_scale_spin.setDecimals(1)
        sr_layout.addWidget(self.sr_scale_spin, 0, 1)

        sr_layout.addWidget(QLabel("超分算法"), 0, 2)
        self.sr_algorithm_combo = QComboBox()
        self.sr_algorithm_combo.addItems(["placeholder"])
        self.sr_algorithm_combo.setEditable(True)
        sr_layout.addWidget(self.sr_algorithm_combo, 0, 3)

        sr_note = QLabel("当前超分后端为占位实现，参数暂时不会影响实际输出。后续接入真实模型后会自动生效。")
        sr_note.setObjectName("cardNote")
        sr_note.setWordWrap(True)
        sr_layout.addWidget(sr_note, 1, 0, 1, 4)

        layout.addWidget(self.sr_param_group)
        return group

    def _build_anime_workspace_section(self) -> QGroupBox:
        group = QGroupBox("动漫优化方法页")
        layout = QVBoxLayout(group)
        layout.setSpacing(14)

        layout.addWidget(
            self._build_method_context_section(
                "动漫页说明",
                "动画向处理也单独占页，避免和补帧、超分混在一起。",
                (
                    "1. 本页用于确认当前任务是'动漫帧优化'。",
                    "2. 如果素材边缘、过渡或重复帧较多，建议先做短片段测试。",
                    "3. 编码、输出路径和最终启动入口都统一放在'导出'页。",
                ),
                "把动漫类素材从综合页拆出来后，后续如果要补充专门的动画参数，也不需要再和其他算法抢空间。",
            )
        )
        return group

    def _build_format_workspace_section(self) -> QGroupBox:
        group = QGroupBox("格式转换方法页")
        layout = QVBoxLayout(group)
        layout.setSpacing(14)

        layout.addWidget(
            self._build_method_context_section(
                "格式转换页说明",
                "格式转换现在也有自己的页面，用来承接转码、封装和轻量交付场景。",
                (
                    "1. 进入本页时，会把当前主流程切到'格式转换'。",
                    "2. 这个流程更关注编码器、CRF 和封装方式，而不是帧级算法参数。",
                    "3. 真正的编码设置和输出目标统一放在'导出'页确认。",
                ),
                "这样在左侧导航里，所有处理方式的入口都保持一致，不再把转码逻辑塞在补帧页里。",
            )
        )
        return group

    def _build_delivery_flow_section(self) -> QGroupBox:
        group = QGroupBox("流程编排")
        layout = QVBoxLayout(group)
        layout.setSpacing(14)

        note = QLabel("每种处理方式已经拆成独立页面；这里负责把当前主流程、补帧/超分联动和运行目标统一收口。")
        note.setObjectName("cardNote")
        note.setWordWrap(True)
        layout.addWidget(note)

        focus_frame = QFrame()
        focus_frame.setObjectName("hintBanner")
        focus_layout = QVBoxLayout(focus_frame)
        focus_layout.setContentsMargins(14, 12, 14, 12)
        focus_layout.setSpacing(8)

        self.delivery_focus_label = QLabel("")
        self.delivery_focus_label.setObjectName("hintText")
        self.delivery_focus_label.setWordWrap(True)
        focus_layout.addWidget(self.delivery_focus_label)
        layout.addWidget(focus_frame)

        runtime_group = QGroupBox("运行目标")
        runtime_layout = QGridLayout(runtime_group)
        runtime_layout.setHorizontalSpacing(14)
        runtime_layout.setVerticalSpacing(12)

        runtime_layout.addWidget(QLabel("Tensor 后端"), 0, 0)
        self.backend_combo = QComboBox()
        self.backend_combo.addItems(["PyTorch", "PaddlePaddle"])
        self.backend_combo.setCurrentText("PyTorch")
        runtime_layout.addWidget(self.backend_combo, 0, 1)

        runtime_note = QLabel("帧率设置已移至'补帧'页面，可按倍率补帧或指定目标帧率。")
        runtime_note.setObjectName("cardNote")
        runtime_note.setWordWrap(True)
        runtime_layout.addWidget(runtime_note, 1, 0, 1, 2)

        layout.addWidget(runtime_group)

        self.processing_switch_group = QGroupBox("补帧 / 超分联动")
        switch_layout = QGridLayout(self.processing_switch_group)
        switch_layout.setHorizontalSpacing(14)
        switch_layout.setVerticalSpacing(12)

        self.enable_interpolation_check = QCheckBox("启用补帧")
        self.enable_interpolation_check.setChecked(True)
        switch_layout.addWidget(self.enable_interpolation_check, 0, 0)

        self.enable_super_resolution_check = QCheckBox("启用超分")
        switch_layout.addWidget(self.enable_super_resolution_check, 0, 1)

        self.process_order_label = QLabel("执行顺序")
        switch_layout.addWidget(self.process_order_label, 1, 0)

        self.process_order_combo = QComboBox()
        self.process_order_combo.addItems(PROCESS_ORDER_MAP.keys())
        self.process_order_combo.setCurrentText("先超分后补帧")
        switch_layout.addWidget(self.process_order_combo, 1, 1, 1, 3)

        self.processing_switch_note = QLabel(
            "只有当前主流程是\u201c视频补帧\u201d或\u201c超分辨率\u201d时，才需要在这里决定是否双开以及先后顺序。"
        )
        self.processing_switch_note.setObjectName("cardNote")
        self.processing_switch_note.setWordWrap(True)
        switch_layout.addWidget(self.processing_switch_note, 2, 0, 1, 4)

        layout.addWidget(self.processing_switch_group)

        hint_frame = QFrame()
        hint_frame.setObjectName("hintBanner")
        hint_layout = QHBoxLayout(hint_frame)
        hint_layout.setContentsMargins(14, 12, 14, 12)
        hint_layout.setSpacing(0)

        self.algorithm_hint_label = QLabel("")
        self.algorithm_hint_label.setObjectName("hintText")
        self.algorithm_hint_label.setWordWrap(True)
        hint_layout.addWidget(self.algorithm_hint_label)
        layout.addWidget(hint_frame)

        return group

    def _build_encode_section(self) -> QGroupBox:
        encode_group = QGroupBox("输出编码")
        encode_layout = QGridLayout(encode_group)
        encode_layout.setHorizontalSpacing(14)
        encode_layout.setVerticalSpacing(12)

        encode_layout.addWidget(QLabel("编码器"), 0, 0)
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["libx264", "libx265", "libvpx-vp9", "libaom-av1", "copy"])
        self.codec_combo.setCurrentText("libx264")
        encode_layout.addWidget(self.codec_combo, 0, 1)

        encode_layout.addWidget(QLabel("CRF 质量"), 0, 2)
        self.crf_spin = QSpinBox()
        self.crf_spin.setRange(0, 51)
        self.crf_spin.setValue(18)
        encode_layout.addWidget(self.crf_spin, 0, 3)

        encode_layout.addWidget(QLabel("编码预设"), 1, 0)
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(
            [
                "ultrafast",
                "superfast",
                "veryfast",
                "faster",
                "fast",
                "medium",
                "slow",
                "slower",
                "veryslow",
            ]
        )
        self.preset_combo.setCurrentText("medium")
        encode_layout.addWidget(self.preset_combo, 1, 1, 1, 3)
        return encode_group

    def _build_output_section(self) -> QGroupBox:
        group = QGroupBox("输出目标")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        note = QLabel("你可以手动指定输出文件路径；留空时由 CLI 自动决定输出位置和文件名。")
        note.setObjectName("cardNote")
        note.setWordWrap(True)
        layout.addWidget(note)

        # 输出文件路径
        output_label = QLabel("输出文件")
        layout.addWidget(output_label)
        row = QHBoxLayout()
        row.setSpacing(10)

        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("留空则自动生成输出文件")
        row.addWidget(self.output_path_edit, 1)

        browse_btn = QPushButton("选择路径")
        browse_btn.setObjectName("secondaryButton")
        browse_btn.clicked.connect(self._browse_output)
        row.addWidget(browse_btn)
        layout.addLayout(row)

        # 输出目录
        output_dir_label = QLabel("输出目录")
        layout.addWidget(output_dir_label)
        dir_row = QHBoxLayout()
        dir_row.setSpacing(10)

        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("留空则使用 CLI 默认输出目录")
        dir_row.addWidget(self.output_dir_edit, 1)

        output_dir_btn = QPushButton("选择目录")
        output_dir_btn.setObjectName("secondaryButton")
        output_dir_btn.clicked.connect(self._browse_output_dir)
        dir_row.addWidget(output_dir_btn)
        layout.addLayout(dir_row)

        # 临时目录
        temp_label = QLabel("临时目录")
        layout.addWidget(temp_label)
        temp_row = QHBoxLayout()
        temp_row.setSpacing(10)

        self.temp_dir_edit = QLineEdit()
        self.temp_dir_edit.setPlaceholderText("留空则使用 CLI 默认临时目录")
        temp_row.addWidget(self.temp_dir_edit, 1)

        temp_dir_btn = QPushButton("选择目录")
        temp_dir_btn.setObjectName("secondaryButton")
        temp_dir_btn.clicked.connect(self._browse_temp_dir)
        temp_row.addWidget(temp_dir_btn)
        layout.addLayout(temp_row)

        self.output_hint_label = QLabel("当前未指定输出路径。")
        self.output_hint_label.setObjectName("cardNote")
        self.output_hint_label.setWordWrap(True)
        layout.addWidget(self.output_hint_label)
        return group

    def _build_process_section(self) -> QGroupBox:
        group = QGroupBox("执行面板")
        layout = QVBoxLayout(group)
        layout.setSpacing(14)

        self.process_summary_label = QLabel("当前任务：等待配置")
        self.process_summary_label.setObjectName("processSummary")
        self.process_summary_label.setWordWrap(True)
        layout.addWidget(self.process_summary_label)

        self.start_btn = QPushButton("开始处理")
        self.start_btn.setObjectName("startPrimaryButton")
        self.start_btn.setFixedHeight(48)
        self.start_btn.clicked.connect(self._start_process)
        layout.addWidget(self.start_btn)

        progress_row = QHBoxLayout()
        progress_row.setSpacing(10)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        progress_row.addWidget(self.progress_bar, 1)

        self.progress_label = QLabel("0%")
        self.progress_label.setObjectName("progressValue")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.setFixedWidth(60)
        progress_row.addWidget(self.progress_label)

        layout.addLayout(progress_row)

        self.frame_label = QLabel("等待任务开始")
        self.frame_label.setObjectName("cardNote")
        layout.addWidget(self.frame_label)

        self.process_state_label = QLabel("准备就绪，可以直接开始处理。")
        self.process_state_label.setObjectName("cardNote")
        self.process_state_label.setWordWrap(True)
        layout.addWidget(self.process_state_label)

        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)
        return group

    def _build_summary_section(self) -> QGroupBox:
        group = QGroupBox("任务摘要")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        note = QLabel("右侧摘要会持续同步你当前的输入素材、处理策略和输出方式。")
        note.setObjectName("cardNote")
        note.setWordWrap(True)
        layout.addWidget(note)

        for title, key in (
            ("输入素材", "input"),
            ("视频概览", "video"),
            ("处理策略", "strategy"),
            ("推理配置", "runtime"),
            ("输出编码", "encode"),
            ("输出路径", "output"),
        ):
            layout.addWidget(self._create_summary_row(title, key))

        hint_frame = QFrame()
        hint_frame.setObjectName("hintBanner")
        hint_layout = QVBoxLayout(hint_frame)
        hint_layout.setContentsMargins(14, 12, 14, 12)
        hint_layout.setSpacing(6)

        hint_title = QLabel("桌面端建议")
        hint_title.setObjectName("summaryKey")
        hint_layout.addWidget(hint_title)

        self.recommend_label = QLabel("拖入一段素材后，我会根据分辨率和目标帧率给出更具体的建议。")
        self.recommend_label.setObjectName("hintText")
        self.recommend_label.setWordWrap(True)
        hint_layout.addWidget(self.recommend_label)

        layout.addWidget(hint_frame)
        return group

    def _init_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel("就绪")
        self.status_bar.addWidget(self.status_label)

        self.mode_label = QLabel("桌面工作台")
        self.mode_label.setObjectName("statusPill")
        self.status_bar.addPermanentWidget(self.mode_label)

    # ---- 工具方法 ----

    def _create_env_badge(self, title: str) -> tuple[QFrame, QLabel]:
        badge = QFrame()
        badge.setObjectName("envBadge")
        badge.setProperty("state", "pending")

        layout = QVBoxLayout(badge)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("envBadgeTitle")
        layout.addWidget(title_label)

        value_label = QLabel("检测中")
        value_label.setObjectName("envBadgeValue")
        layout.addWidget(value_label)
        return badge, value_label

    def _create_metric_card(self, title: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("metricCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        caption = QLabel(title)
        caption.setObjectName("metricCaption")
        layout.addWidget(caption)

        value = QLabel("--")
        value.setObjectName("metricValue")
        layout.addWidget(value)
        return card, value

    def _create_summary_row(self, title: str, key: str) -> QFrame:
        row = QFrame()
        row.setObjectName("summaryRow")

        layout = QVBoxLayout(row)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("summaryKey")
        layout.addWidget(title_label)

        value_label = QLabel("--")
        value_label.setObjectName("summaryValue")
        value_label.setWordWrap(True)
        layout.addWidget(value_label)

        self._summary_values[key] = value_label
        return row

    def _apply_stylesheet(self):
        self.setStyleSheet(DARK_STYLESHEET)
