import ops
import ops.testing
import pytest

from charm import GithubProfilesAutomatorCharm


@pytest.fixture
def harness():
    harness = ops.testing.Harness(GithubProfilesAutomatorCharm)
    harness.begin()
    yield harness
    harness.cleanup()
