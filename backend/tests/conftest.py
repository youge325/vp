"""Pytest 配置和共享夹具。"""

import os
import sys

# 确保 backend app 可被导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
