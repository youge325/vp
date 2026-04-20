"""桌面应用主窗口 - 视频补帧与超分软件完整功能界面。

MainWindow 继承 MainWindowUIBuilder 和 MainWindowLogic 两个 Mixin，
前者负责 UI 构建，后者负责业务逻辑，本文件只保留 __init__ 初始化。
"""

from PyQt6.QtWidgets import QMainWindow

from desktop.api_client import CliClient

from .business_logic import MainWindowLogic
from .signals import EnvCheckBridge, ProcessBridge, VideoInfoBridge
from .ui_builders import MainWindowUIBuilder


class MainWindow(MainWindowUIBuilder, MainWindowLogic, QMainWindow):
    """主应用窗口 - 视频补帧与超分软件。

    继承关系：MainWindow → MainWindowUIBuilder(Mixin) + MainWindowLogic(Mixin) + QMainWindow
    - MainWindowUIBuilder: 所有 _build_* 方法和 UI 组装
    - MainWindowLogic: 所有业务逻辑方法（环境检查、文件操作、视频信息、算法/预设、处理流程等）
    - QMainWindow: Qt 基类
    """

    def __init__(self, cli_client: CliClient = None):
        super().__init__()
        self.cli = cli_client or CliClient()
        self._processing = False
        self._video_info = {}
        self._last_output_path = ""
        self._env_badges = {}
        self._summary_values = {}

        self._env_bridge = EnvCheckBridge()
        self._env_bridge.result_ready.connect(self._show_env_result)
        self._info_bridge = VideoInfoBridge()
        self._info_bridge.result_ready.connect(self._show_video_info)
        self._process_bridge = ProcessBridge()
        self._process_bridge.progress.connect(self._on_progress)
        self._process_bridge.completed.connect(self._on_completed)
        self._process_bridge.error.connect(self._on_error)

        self._init_ui()
        self._init_statusbar()
        self._switch_workspace_page(self.workspace_stack.currentIndex())
        self._connect_live_updates()
        self._on_algorithm_changed(self.algorithm_combo.currentText())
        self._refresh_summary()
        self._update_layout_mode()
        self._check_environment()

        self.setAcceptDrops(True)
