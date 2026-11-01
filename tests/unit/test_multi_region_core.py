import numpy as np
import pytest

from segvision.core.errors import InvalidPoint
from tests.e2e.helpers import make_session


def _selected_session():
    session, backend = make_session(count=1)
    proposal = session.propose()
    selected = session.select(proposal.candidates[0].candidate_id)
    return session, backend, selected


def _full_point(session, crop_x: int, crop_y: int) -> tuple[int, int]:
    x0, y0, _, _ = session.context.crop_rect_full
    return x0 + crop_x, y0 + crop_y


def test_prompt_ids_support_arbitrary_delete_replay_and_undo():
    session, backend, selected = _selected_session()
    foreground = _full_point(session, 6, 6)
    background = _full_point(session, 20, 20)

    first = session.refine(selected.candidate_id, foreground, 1)
    second = session.refine(first.candidate_id, background, 0)
    first_id = second.prompt_points[0].point_id
    second_id = second.prompt_points[1].point_id

    assert first_id and second_id and first_id != second_id
    decode_before = backend.decode_calls
    replayed = session.delete_prompt(first_id)

    assert backend.decode_calls == decode_before + 1
    assert [point.point_id for point in replayed.prompt_points] == [second_id]
    assert backend.ledger[-1]["points"] == [
        {"x": background[0] - session.context.crop_rect_full[0],
         "y": background[1] - session.context.crop_rect_full[1],
         "label": 0}
    ]

    restored = session.undo()
    assert restored is not None
    assert [point.point_id for point in restored.prompt_points] == [first_id, second_id]


def test_unknown_prompt_delete_is_non_destructive():
    session, backend, selected = _selected_session()
    refined = session.refine(selected.candidate_id, _full_point(session, 6, 6), 1)
    decode_before = backend.decode_calls

    with pytest.raises(InvalidPoint):
        session.delete_prompt("point-missing")

    assert backend.decode_calls == decode_before
    assert session.selected_candidate is refined


def test_component_lock_clips_local_edits_and_next_region_reopens_sam():
    session, backend, selected = _selected_session()
    region = session.lock_component(_full_point(session, 6, 6), 1)
    locked = session.locked_foreground.copy()
    decode_before = backend.decode_calls

    assert region.label == 1
    assert locked.sum() == selected.mask.sum()
    edited = session.edit("erase", points=[(6, 6)], radius=3)
    assert edited.mask[locked].all()
    assert backend.decode_calls == decode_before

    next_candidate = session.next_region()
    assert session.pass_index == 2
    assert session.revision == 2
    assert next_candidate is None
    assert session.selected_candidate is None
    assert session.locked_foreground[locked].all()
    assert session.prompt_points == ()
    assert backend.decode_calls == decode_before

    restored = session.undo()
    assert restored is not None
    assert session.revision == 1
    assert session.selected_candidate is restored
    assert session.locked_foreground[locked].all()


def test_background_lock_unlock_and_undo_restore_exact_composite():
    session, _, selected = _selected_session()
    pixel = np.zeros(session.context.shape, dtype=np.bool_)
    pixel[6, 6] = True

    region = session.lock_region(pixel, 0)
    assert not session.selected_candidate.mask[6, 6]
    assert session.locked_background[6, 6]

    unlocked = session.unlock_region(region.region_id)
    assert unlocked is not None and unlocked.mask[6, 6] == selected.mask[6, 6]
    assert not session.locked_background.any()

    restored = session.undo()
    assert restored is not None
    assert session.locked_background[6, 6]
    assert not restored.mask[6, 6]


def test_merge_flattens_locked_foreground_and_preserves_background_with_undo():
    session, backend, selected = _selected_session()
    foreground = session.lock_component(_full_point(session, 6, 6), 1)
    background_mask = np.zeros(session.context.shape, dtype=np.bool_)
    background_mask[20, 20] = True
    background = session.lock_region(background_mask, 0)
    before_decode = backend.decode_calls

    merged = session.edit("merge")

    assert merged.source.value == "manual_edit"
    assert merged.can_local_edit
    assert session.frozen_regions == (background,)
    assert session.locked_foreground.sum() == 0
    assert session.locked_background[20, 20]
    assert merged.mask[6, 6]
    assert not merged.mask[20, 20]
    assert backend.decode_calls == before_decode
    assert session.events[-1]["event"] == "regions_merged"
    assert session._operations[-1]["kind"] == "merge_regions"

    restored = session.undo()
    assert restored is not None
    assert restored.source == selected.source
    assert session.frozen_regions == (foreground, background)
    assert session.locked_foreground[6, 6]
    assert session.locked_background[20, 20]


def test_accept_records_active_frozen_region_provenance():
    session, _, _ = _selected_session()
    region = session.lock_component(_full_point(session, 6, 6), 1)
    result = session.accept(
        acknowledge_warnings=[warning.code for warning in session.selected_candidate.warnings]
    )

    assert result.provenance["pass_index"] == 1
    assert result.provenance["frozen_regions"][0]["region_id"] == region.region_id
    assert any(op["kind"] == "lock_region" for op in result.provenance["operations"])


def test_locked_region_survives_roi_change_and_is_committed_full_image():
    session, _, _ = _selected_session()
    region = session.lock_component(_full_point(session, 6, 6), 1)
    locked_full = session.locked_foreground_full.copy()

    # Shift to another ROI with the same padded crop resolution so the fake
    # backend remains shape-compatible while exercising full-image lock
    # persistence across region changes.
    session.update_roi((11, 8, 39, 36))
    assert session.frozen_regions[0].region_id == region.region_id
    assert np.array_equal(session.locked_foreground_full, locked_full)

    proposal = session.propose()
    session.select(proposal.candidates[0].candidate_id)
    result = session.accept(
        acknowledge_warnings=[warning.code for warning in session.selected_candidate.warnings]
    )
    assert np.all(result.full_image_mask[locked_full])
