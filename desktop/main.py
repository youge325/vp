"""桌面应用入口 — PyQt6 图形界面。"""

import sys
import os

# 将项目根目录添加到导入路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from desktop.api_client import CliClient
from desktop.views.main_window import MainWindow


def main():
    """启动桌面应用。"""
    app = QApplication(sys.argv)
    app.setApplicationName("视频补帧与超分软件")
    app.setApplicationVersion("1.0.0")

    # 设置默认字体
    font = app.font()
    font.setFamily("Microsoft YaHei")
    font.setPointSize(10)
    app.setFont(font)

    # 创建 CLI 客户端和主窗口
    cli = CliClient()
    window = MainWindow(cli)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
