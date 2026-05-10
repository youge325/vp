"""FFmpeg constants and regex patterns."""

import re

ENCODER_CANDIDATES = (
    {"name": "libx264", "label": "CPU H.264", "family": "cpu", "codec": "h264"},
    {"name": "libx265", "label": "CPU H.265", "family": "cpu", "codec": "hevc"},
    {"name": "libaom-av1", "label": "CPU AV1", "family": "cpu", "codec": "av1"},
    {"name": "libsvtav1", "label": "CPU SVT-AV1", "family": "cpu", "codec": "av1"},
    {"name": "h264_nvenc", "label": "NVENC H.264", "family": "nvidia", "codec": "h264"},
    {"name": "hevc_nvenc", "label": "NVENC H.265", "family": "nvidia", "codec": "hevc"},
    {"name": "av1_nvenc", "label": "NVENC AV1", "family": "nvidia", "codec": "av1"},
    {"name": "h264_qsv", "label": "QSV H.264", "family": "intel", "codec": "h264"},
    {"name": "hevc_qsv", "label": "QSV H.265", "family": "intel", "codec": "hevc"},
    {"name": "av1_qsv", "label": "QSV AV1", "family": "intel", "codec": "av1"},
)

DECODER_CANDIDATES = (
    {"name": "h264_cuvid", "label": "NVDEC H.264", "family": "nvidia", "codec": "h264"},
    {"name": "hevc_cuvid", "label": "NVDEC H.265", "family": "nvidia", "codec": "hevc"},
    {"name": "av1_cuvid", "label": "NVDEC AV1", "family": "nvidia", "codec": "av1"},
    {"name": "h264_qsv", "label": "QSV H.264", "family": "intel", "codec": "h264"},
    {"name": "hevc_qsv", "label": "QSV H.265", "family": "intel", "codec": "hevc"},
    {"name": "av1_qsv", "label": "QSV AV1", "family": "intel", "codec": "av1"},
)

OPTION_LINE_RE = re.compile(
    r"^\s{2}-(?P<name>[\w\-]+)\s+<(?P<kind>[^>]+)>\s+.*?"
    r"(?:\(from (?P<min>[^ ]+) to (?P<max>[^)]+)\))?"
    r"(?: \(default (?P<default>[^)]+)\))?$"
)
CHOICE_LINE_RE = re.compile(r"^\s{5,}(?P<value>\S+)\s+\S+\s+")
CODEC_LIST_RE = re.compile(r"^\s*[A-Z\.]{6}\s+(?P<name>[\w\-]+)\s+")
FFMPEG_PROGRESS_KEYS = {
    "bitrate",
    "drop_frames",
    "dup_frames",
    "fps",
    "frame",
    "out_time",
    "out_time_ms",
    "out_time_us",
    "progress",
    "speed",
    "total_size",
}
