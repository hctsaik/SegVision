import pytest

from segvision.acceptance.domain import validate_reviewer_records
from segvision.core.errors import ConfigurationError


def test_domain_validation():
    with pytest.raises(ConfigurationError):
        validate_reviewer_records([])
