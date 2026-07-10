from app.planning import ProcessingStep, StagePlan
from app.processing.streaming.pipeline_rules import resolved_output_dimensions


def test_output_dimensions_scale_for_paddlegan_super_resolution_from_stage_plan():
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
        total_encoded_frames=10,
    )

    assert resolved_output_dimensions(
        video_info={"width": 320, "height": 180},
        stage_plan=stage_plan,
    ) == (1280, 720)
