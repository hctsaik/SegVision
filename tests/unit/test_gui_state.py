from segvision.gui.controller import WorkflowState


def test_gui_state():
    assert WorkflowState.IMAGE_OPEN.value == "IMAGE_OPEN"
