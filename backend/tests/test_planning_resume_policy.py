from app.planning.resume_policy import decide_output_action


def test_resume_policy_covers_conflict_fresh_and_resume() -> None:
    assert (
        decide_output_action(
            final_exists=True,
            sidecar_exists=True,
            signature_match=True,
            has_progress=True,
            mode="auto",
        )
        == "conflict"
    )
    assert (
        decide_output_action(
            final_exists=True,
            sidecar_exists=True,
            signature_match=True,
            has_progress=True,
            mode="force-fresh",
        )
        == "fresh"
    )
    assert (
        decide_output_action(
            final_exists=False,
            sidecar_exists=True,
            signature_match=True,
            has_progress=True,
            mode="auto",
        )
        == "resume"
    )
    assert (
        decide_output_action(
            final_exists=False,
            sidecar_exists=True,
            signature_match=False,
            has_progress=True,
            mode="force-resume",
        )
        == "fresh"
    )
