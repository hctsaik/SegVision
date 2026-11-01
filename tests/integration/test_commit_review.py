import pytest

from segvision.core.errors import AcceptValidationError
from tests.e2e.helpers import make_session


def test_commit_requires_a_selected_committable_candidate():
    session, _ = make_session(count=0)
    with pytest.raises(AcceptValidationError):
        session.accept()
