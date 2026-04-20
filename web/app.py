"""Gradio 前端：按处理方式拆分页面的工作台布局。"""

import gradio as gr

from api_client import client


TASK_TYPE_MAP = {
    "视频补帧": "frame_interpolation",
    "超分辨率": "super_resolution",
    "动漫帧优化": "anime_optimization",
    "格式转换": "format_conversion",
}

COMBINED_TASK_TYPES = {"视频补帧", "超分辨率"}

PROCESS_ORDER_MAP = {
    "先超分后补帧": "super_resolution_then_interpolation",
    "先补帧后超分": "frame_interpolation_then_super_resolution",
}


def _default_processing_switches(task_type_label: str) -> tuple[bool, bool]:
    if task_type_label == "超分辨率":
        return False, True
    return True, False


def _workflow_markdown(task_type_label: str) -> str:
    return (
        "### 当前主流程\n"
        f"已选中：`{task_type_label}`\n\n"
        "左侧和各方法页用于切换主流程，导出页负责统一确认联动、编码和输出。"
    )


def _combo_hint_text(task_type_label: str) -> str:
    if task_type_label in COMBINED_TASK_TYPES:
        return "补帧和超分可以分别控制；两者同时开启时，可以在这里决定先超后补或先补后超。"
    return "当前流程不需要补帧 / 超分联动，直接在下方确认编码和输出参数即可。"


def select_workflow(task_type_label: str):
    is_combined = task_type_label in COMBINED_TASK_TYPES
    enable_interpolation, enable_super_resolution = (
        _default_processing_switches(task_type_label) if is_combined else (False, False)
    )
    workflow_text = _workflow_markdown(task_type_label)
    return (
        task_type_label,
        workflow_text,
        workflow_text,
        gr.update(visible=is_combined, value=enable_interpolation),
        gr.update(visible=is_combined, value=enable_super_resolution),
        gr.update(
            visible=is_combined and enable_interpolation and enable_super_resolution,
            value="先超分后补帧",
        ),
        _combo_hint_text(task_type_label),
    )


def update_process_order_visibility(
    task_type_label: str,
    enable_interpolation: bool,
    enable_super_resolution: bool,
):
    return gr.update(
        visible=(task_type_label in COMBINED_TASK_TYPES and enable_interpolation and enable_super_resolution)
    )


def check_environment():
    result = client.check_environment()
    if result.get("type") == "error":
        return f"环境检查失败：{result['message']}"

    ffmpeg = result.get("ffmpeg", {})
    gpu = result.get("gpu", {})
    tb = result.get("tensor_backends", {})

    lines = [
        f"FFmpeg: {'可用' if ffmpeg.get('available') else '不可用'}",
        f"GPU: {', '.join(gpu.get('devices', [])) if gpu.get('available') else '未检测到'}",
        f"PyTorch: {'可用' if tb.get('pytorch') else '不可用'}",
        f"PaddlePaddle: {'可用' if tb.get('paddle') else '不可用'}",
    ]
    return "\n".join(lines)


def get_video_info(video_file):
    if not video_file:
        return "请先上传视频文件"

    input_path = video_file if isinstance(video_file, str) else video_file.name
    result = client.get_video_info(input_path)
    if result.get("type") == "error":
        return f"读取失败：{result['message']}"

    info = result
    lines = [
        f"FPS: {info.get('fps', '?')}",
        f"帧数: {info.get('frames', '?')}",
        f"时长: {info.get('duration', 0):.1f}s",
        f"分辨率: {info.get('width', '?')}x{info.get('height', '?')}",
        f"音频: {'有' if info.get('has_audio') else '无'}",
    ]
    return "\n".join(lines)


def submit_task(
    video_file,
    task_type_label,
    enable_interpolation,
    enable_super_resolution,
    process_order_label,
    target_fps,
    tensor_backend,
    codec,
    crf,
    preset,
):
    if not video_file:
        return "请先上传视频文件"

    task_type = TASK_TYPE_MAP.get(task_type_label)
    if not task_type:
        return "请选择处理类型"

    input_path = video_file if isinstance(video_file, str) else video_file.name
    process_order = PROCESS_ORDER_MAP.get(process_order_label, "super_resolution_then_interpolation")

    if task_type_label in COMBINED_TASK_TYPES:
        if not enable_interpolation and not enable_super_resolution:
            return "请至少开启“补帧”或“超分”其中一个开关"
        task_type = "frame_interpolation" if enable_interpolation else "super_resolution"
    else:
        enable_interpolation = False
        enable_super_resolution = False

    result = client.process(
        input_path=input_path,
        algorithm=task_type,
        fps=target_fps,
        codec=codec,
        crf=int(crf),
        preset=preset,
        backend=tensor_backend.lower(),
        enable_interpolation=enable_interpolation,
        enable_super_resolution=enable_super_resolution,
        process_order=process_order,
    )

    if result.get("type") == "completed":
        output = result.get("output_path", "?")
        frames = result.get("processed_frames", 0)
        time_s = result.get("time_seconds", 0)
        return f"处理完成\n输出: {output}\n处理帧数: {frames}\n耗时: {time_s}s"
    if result.get("type") == "error":
        return f"处理失败: {result.get('message', '未知错误')}"
    return f"未预期的结果: {result}"


def build_app() -> gr.Blocks:
    with gr.Blocks(title="视频帧处理工作台") as app:
        task_type_state = gr.State("视频补帧")

        gr.Markdown(
            "# 视频帧处理工作台\n参考 SVFI 的操作顺序和 VSET 的分页面布局，把每种不同的帧处理方式拆成单独页面。"
        )

        with gr.Row(equal_height=False):
            with gr.Column(scale=1, min_width=260, elem_id="workbenchRail"):
                gr.Markdown(
                    "### 工作流\n"
                    "**01 工作台**  查看环境和使用方式  \n"
                    "**02 素材**  导入视频并读取信息  \n"
                    "**03 视频补帧**  专注补帧参数  \n"
                    "**04 超分辨率**  专注超分流程  \n"
                    "**05 动漫帧优化**  动画向处理说明  \n"
                    "**06 格式转换**  转码与封装说明  \n"
                    "**07 导出与执行**  统一确认流程、编码和输出"
                )
                workflow_status_md = gr.Markdown(_workflow_markdown("视频补帧"))
                check_btn = gr.Button("检查环境", variant="secondary")
                env_text = gr.Textbox(label="环境状态", interactive=False, lines=5)

            with gr.Column(scale=3, min_width=760):
                with gr.Tabs():
                    with gr.Tab("工作台"):
                        gr.Markdown(
                            "### 概览\n现在不再把所有模式塞进一个“增强”页，而是让每种帧处理方式都有自己的入口。"
                        )
                        gr.Markdown(
                            "1. 先检查环境，确认 FFmpeg 和推理后端可用。\n"
                            "2. 在“素材”页导入视频并读取基础信息。\n"
                            "3. 进入对应的方法页，确定当前主流程。\n"
                            "4. 最后在“导出与执行”页统一确认联动、编码和输出。"
                        )

                    with gr.Tab("素材"):
                        gr.Markdown("### 素材导入")
                        video_input = gr.File(
                            label="上传视频",
                            file_types=[
                                ".mp4",
                                ".avi",
                                ".mkv",
                                ".mov",
                                ".flv",
                                ".webm",
                                ".wmv",
                            ],
                        )
                        info_btn = gr.Button("读取视频信息")
                        info_text = gr.Textbox(label="视频信息", interactive=False, lines=6)

                    with gr.Tab("视频补帧"):
                        gr.Markdown(
                            "### 视频补帧\n这个页面只负责补帧流程本身。需要和超分串联时，到导出页打开联动开关。"
                        )
                        use_interpolation_btn = gr.Button("使用视频补帧流程", variant="secondary")
                        gr.Markdown(
                            "- 当前 Web 端把流程选择和编码交付拆开，避免一个页面承载所有设置。\n"
                            "- 目标帧率和 Tensor 后端在导出页统一设置。"
                        )

                    with gr.Tab("超分辨率"):
                        gr.Markdown(
                            "### 超分辨率\n这个页面专门承接超分流程。需要补帧 + 超分时，同样在导出页统一编排顺序。"
                        )
                        use_super_resolution_btn = gr.Button("使用超分辨率流程", variant="secondary")
                        gr.Markdown(
                            "- 当前超分后端仍是占位实现，但页面结构已经独立出来。\n"
                            "- 后续接真实 SR 参数时，可以直接扩展这一页。"
                        )

                    with gr.Tab("动漫帧优化"):
                        gr.Markdown("### 动漫帧优化\n动画向处理也单独占页，避免和补帧、超分混在同一个配置区。")
                        use_anime_btn = gr.Button("使用动漫帧优化流程", variant="secondary")
                        gr.Markdown("- 适合先做短片段测试，再决定是否整段处理。\n- 编码和输出仍然在导出页统一确认。")

                    with gr.Tab("格式转换"):
                        gr.Markdown("### 格式转换\n格式转换页用于轻量转码和封装交付场景，重点放在输出阶段。")
                        use_format_btn = gr.Button("使用格式转换流程", variant="secondary")
                        gr.Markdown(
                            "- 当前主流程切到格式转换后，不再显示补帧 / 超分联动开关。\n"
                            "- 真正的编码参数和输出路径都在导出页统一设置。"
                        )

                    with gr.Tab("导出与执行"):
                        deliver_workflow_md = gr.Markdown(_workflow_markdown("视频补帧"))
                        gr.Markdown("### 流程编排\n方法页负责决定主流程，这里负责把联动、编码与输出一起确认。")
                        with gr.Row():
                            tensor_dd = gr.Dropdown(
                                choices=["PyTorch", "PaddlePaddle"],
                                value="PyTorch",
                                label="Tensor 后端",
                            )
                            fps_slider = gr.Slider(24, 120, value=60, step=1, label="目标帧率")

                        combo_hint = gr.Markdown(_combo_hint_text("视频补帧"))
                        with gr.Row():
                            enable_interpolation_check = gr.Checkbox(label="启用补帧", value=True)
                            enable_super_resolution_check = gr.Checkbox(label="启用超分", value=False)
                        process_order_dd = gr.Dropdown(
                            choices=list(PROCESS_ORDER_MAP.keys()),
                            value="先超分后补帧",
                            label="执行顺序",
                            visible=False,
                        )

                        gr.Markdown("### 编码与输出")
                        with gr.Row():
                            codec_dd = gr.Dropdown(
                                choices=[
                                    "libx264",
                                    "libx265",
                                    "libvpx-vp9",
                                    "libaom-av1",
                                    "copy",
                                ],
                                value="libx264",
                                label="编码器",
                            )
                            preset_dd = gr.Dropdown(
                                choices=[
                                    "ultrafast",
                                    "superfast",
                                    "veryfast",
                                    "faster",
                                    "fast",
                                    "medium",
                                    "slow",
                                    "slower",
                                    "veryslow",
                                ],
                                value="medium",
                                label="编码预设",
                            )
                        crf_slider = gr.Slider(0, 51, value=18, step=1, label="CRF 质量")
                        submit_btn = gr.Button("提交任务", variant="primary")
                        submit_result = gr.Textbox(label="执行结果", interactive=False, lines=5)

        workflow_outputs = [
            task_type_state,
            workflow_status_md,
            deliver_workflow_md,
            enable_interpolation_check,
            enable_super_resolution_check,
            process_order_dd,
            combo_hint,
        ]

        check_btn.click(fn=check_environment, outputs=[env_text])
        info_btn.click(fn=get_video_info, inputs=[video_input], outputs=[info_text])

        use_interpolation_btn.click(
            fn=lambda: select_workflow("视频补帧"),
            outputs=workflow_outputs,
        )
        use_super_resolution_btn.click(
            fn=lambda: select_workflow("超分辨率"),
            outputs=workflow_outputs,
        )
        use_anime_btn.click(
            fn=lambda: select_workflow("动漫帧优化"),
            outputs=workflow_outputs,
        )
        use_format_btn.click(
            fn=lambda: select_workflow("格式转换"),
            outputs=workflow_outputs,
        )

        enable_interpolation_check.change(
            fn=update_process_order_visibility,
            inputs=[
                task_type_state,
                enable_interpolation_check,
                enable_super_resolution_check,
            ],
            outputs=[process_order_dd],
        )
        enable_super_resolution_check.change(
            fn=update_process_order_visibility,
            inputs=[
                task_type_state,
                enable_interpolation_check,
                enable_super_resolution_check,
            ],
            outputs=[process_order_dd],
        )

        submit_btn.click(
            fn=submit_task,
            inputs=[
                video_input,
                task_type_state,
                enable_interpolation_check,
                enable_super_resolution_check,
                process_order_dd,
                fps_slider,
                tensor_dd,
                codec_dd,
                crf_slider,
                preset_dd,
            ],
            outputs=[submit_result],
        )

    return app


if __name__ == "__main__":
    app = build_app()
    app.launch(
        server_name="127.0.0.1",
        server_port=7860,
        show_error=True,
        theme=gr.themes.Soft(
            primary_hue="teal",
            secondary_hue="cyan",
            neutral_hue="slate",
        ),
        css="""
        footer { display: none !important; }
        #workbenchRail {
            background: linear-gradient(180deg, #0f1a2c 0%, #0b1727 100%);
            border: 1px solid #22324b;
            border-radius: 18px;
            padding: 18px;
        }
        """,
    )
