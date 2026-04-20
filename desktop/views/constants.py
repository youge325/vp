"""桌面端主窗口常量定义。"""

__all__ = [
    "VIDEO_FILTER",
    "ALGORITHM_MAP",
    "ALGORITHM_HINTS",
    "COMBINED_TASK_TYPES",
    "PROCESS_ORDER_MAP",
    "WORKSPACE_PAGES",
    "PAGE_ALGORITHM_MAP",
    "RIFE_VERSIONS",
    "FPS_MODE_MAP",
]

VIDEO_FILTER = "视频文件 (*.mp4 *.avi *.mkv *.mov *.flv *.webm *.wmv);;所有文件 (*)"

ALGORITHM_MAP = {
    "视频补帧": "frame_interpolation",
    "超分辨率": "super_resolution",
    "动漫帧优化": "anime_optimization",
    "格式转换": "format_conversion",
}

ALGORITHM_HINTS = {
    "视频补帧": "通过 RIFE 生成中间帧，适合把低帧率素材提升到更顺滑的观感。",
    "超分辨率": "优先提升画面细节和清晰度，适合旧素材放大或恢复边缘信息。",
    "动漫帧优化": "更偏向动漫场景的过渡优化与重复帧修正，适合番剧或二维动画内容。",
    "格式转换": "保留处理链最小化介入，重点在输出编码器、封装格式和压缩质量控制。",
}

COMBINED_TASK_TYPES = {"视频补帧", "超分辨率"}

FPS_MODE_MAP = {
    "补帧倍率": "multi",
    "目标帧率": "target",
}

PROCESS_ORDER_MAP = {
    "先超分后补帧": "super_resolution_then_interpolation",
    "先补帧后超分": "frame_interpolation_then_super_resolution",
}

WORKSPACE_PAGES = [
    ("workspace", "工作台", "环境状态、素材概览与执行建议"),
    ("source", "素材", "输入视频、路径与基础信息"),
    ("interpolation", "视频补帧", "RIFE 参数、倍速与补帧预设"),
    ("super_resolution", "超分辨率", "超分流程说明与联动入口"),
    ("anime", "动漫帧优化", "动画向处理说明与使用建议"),
    ("format", "格式转换", "转码交付与封装策略说明"),
    ("deliver", "导出", "流程编排、编码与结果交付"),
]

PAGE_ALGORITHM_MAP = {
    "interpolation": "视频补帧",
    "super_resolution": "超分辨率",
    "anime": "动漫帧优化",
    "format": "格式转换",
}

RIFE_VERSIONS = [
    "4.0",
    "4.1",
    "4.2",
    "4.3",
    "4.4",
    "4.5",
    "4.6",
    "4.7",
    "4.8",
    "4.9",
    "4.10",
    "4.11",
    "4.12",
    "4.12.lite",
    "4.13",
    "4.13.lite",
    "4.14",
    "4.14.lite",
    "4.15",
    "4.15.lite",
    "4.16.lite",
    "4.17",
    "4.17.lite",
    "4.18",
    "4.19",
    "4.20",
    "4.21",
    "4.22",
    "4.22.lite",
    "4.23",
    "4.24",
    "4.25",
    "4.25.lite",
    "4.25.heavy",
    "4.26",
    "4.26.heavy",
]
