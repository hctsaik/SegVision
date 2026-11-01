import numpy as np

from segvision.gui.canvas import AnnotationCanvasModel, CanvasTransform
from segvision.gui.controller import AnnotationController
from segvision.gui.panels import AnnotationPanels, candidate_cards
from tests.e2e.helpers import make_session


def test_canvas_transform_round_trip_and_layers():
    transform = CanvasTransform(100, 50, 800, 600)
    view = transform.image_to_view(25, 10)
    assert transform.view_to_pixel(*view) == (25, 10)
    session, _ = make_session(count=2)
    controller = AnnotationController(session)
    controller.lock_roi()
    model = AnnotationCanvasModel(controller)
    layers = model.layers()
    assert layers.candidate_count == 2
    assert layers.selected_mask_roi.dtype == np.bool_
    assert layers.user_roi_full != layers.crop_rect_full


def test_canvas_clicks_route_full_image_points_and_cards_are_compact():
    session, _ = make_session()
    controller = AnnotationController(session)
    controller.lock_roi()
    model = AnnotationCanvasModel(controller, viewport_size=(500, 500))
    x, y = model.transform.image_to_view(15, 15)
    refined = model.mouse_press(x, y, "left")
    assert refined.prompt_points[-1].label == 1
    cards = candidate_cards(controller.visible_candidates, session.selected_candidate.candidate_id)
    assert cards and sum(card.selected for card in cards) == 1
    assert AnnotationPanels(controller).state.controls["accept"]
