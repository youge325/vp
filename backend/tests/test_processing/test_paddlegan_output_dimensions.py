from app.planning.processing_steps import ProcessingStep
from app.planning.stage_plan import StagePlan
from app.planning.stage_projection import StageProjection
from app.ports.media import VideoMetadata
from app.processing.streaming.pipeline_rules import resolved_output_dimensions


def test_output_dimensions_scale_for_paddlegan_super_resolution_from_stage_plan():
    stage_plan = StagePlan(
        projection=StageProjection(
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
        source_frames=10,
        source_duration=10 / 24,
        output_fps=None,
    )

    assert resolved_output_dimensions(
        video_info=VideoMetadata(
            width=320,
            height=180,
            source_fps=24.0,
            source_frames=5,
            duration=5 / 24,
            has_audio=False,
        ),
        stage_plan=stage_plan,
    ) == (1280, 720)
