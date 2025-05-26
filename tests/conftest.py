import json
from urllib.parse import parse_qs
from datetime import datetime
import pytest
from os import environ
from argparse import Namespace


from sybil import Sybil
from sybil.parsers.codeblock import PythonCodeBlockParser
from sybil.parsers.doctest import DocTestParser


def requires_env(*envs: str):
    env = environ.get("FAKTUROID_SLUG", "unit-tests")

    return pytest.mark.skipif(
        env not in list(envs), reason=f"Not suitable envrionment {env} for current test"
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
