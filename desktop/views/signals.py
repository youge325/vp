"""桌面端信号桥接类。"""

from PyQt6.QtCore import QObject, pyqtSignal


class EnvCheckBridge(QObject):
    """环境检查结果信号桥接。"""

    result_ready = pyqtSignal(dict)


class VideoInfoBridge(QObject):
    """视频信息查询结果信号桥接。"""

    result_ready = pyqtSignal(dict)


class ProcessBridge(QObject):
    """视频处理进度/完成/错误信号桥接。"""

    progress = pyqtSignal(int, int, float, str, int, int)
    completed = pyqtSignal(dict)
    error = pyqtSignal(str)
