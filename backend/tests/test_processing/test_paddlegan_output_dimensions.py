from app.planning.processing_steps import ProcessingStep
from app.planning.stage_plan import build_stage_plan
from app.planning.stage_projection import StageProjection
from tests.support.video_metadata import make_video_metadata


def test_output_dimensions_scale_for_paddlegan_super_resolution_from_stage_plan():
    stage_plan = build_stage_plan(
        StageProjection(
            (
                ProcessingStep(
                    algorithm_type="super_resolution",
                    algorithm_kwargs={
                        "sr_algorithm": "ppmsvsr",
                        "scale_factor": 4,
                        "tensor_backend": "paddle",
                    },
                    stage_name="01_super_resolution",
                ),
            )
        ),
        make_video_metadata(10, duration=10 / 24),
        output_fps=None,
    )

    assert stage_plan.output_dimensions == (1280, 720)
