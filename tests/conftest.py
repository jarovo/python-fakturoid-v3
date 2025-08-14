import pytest
from os import environ
from argparse import Namespace
from uuid import uuid4
import typing


def requires_env(*envs: str):
    env = environ.get("FAKTUROID_SLUG", "unit-tests")

    return pytest.mark.skipif(
        env not in list(envs), reason=f"Not suitable environment {env} for current test"
    )


@requires_env("fakturcalldev")
@pytest.fixture
def live_fakturoid_creds():
    namespace = Namespace()
    namespace.TESTS_OBJECTS_NAME_PREFIX = "python-fakturoid-v3-test"
    namespace.FAKTUROID_SLUG = environ["FAKTUROID_SLUG"]
    namespace.FAKTUROID_CLIENT_ID = environ["FAKTUROID_CLIENT_ID"]
    namespace.FAKTUROID_CLIENT_SECRET = environ["FAKTUROID_CLIENT_SECRET"]
    return namespace


@pytest.fixture
def name_factory(request: pytest.FixtureRequest):
    names: typing.List[str] = []

    def factory():
        name = f"test-item-{request.function.__name__}-{uuid4()}"
        names.append(name)
        return name

    yield factory

    # Place for chcecking do we have any leftovers in the system
