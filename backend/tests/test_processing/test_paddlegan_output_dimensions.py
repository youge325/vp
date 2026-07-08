from app.planning import ProcessingStep, StagePlan
from app.processing.streaming.pipeline_rules import resolved_output_dimensions


def test_output_dimensions_scale_for_paddlegan_super_resolution_independent_of_global_backend():
    stage_plan = StagePlan(
        pre_steps=[
            ProcessingStep(
                algorithm_type="super_resolution",
                algorithm_kwargs={
                    "sr_algorithm": "ppmsvsr",
                    "scale_factor": 4,
                    "tensor_backend": "paddle",
                },
                stage_name="01_super_resolution",
            )
        ],
        interpolation_step=None,
        post_steps=[],
        total_output_frames=10,
        total_encoded_frames=10,
        total_pairs=9,
    )

    assert resolved_output_dimensions(
        video_info={"width": 320, "height": 180},
        stage_plan=stage_plan,
        tensor_backend_name="onnx",
    ) == (1280, 720)
