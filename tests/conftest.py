import json
from urllib.parse import parse_qs
import vcr
from datetime import datetime
import pytest
from os import environ
from argparse import Namespace


from sybil import Sybil
from sybil.parsers.codeblock import PythonCodeBlockParser
from sybil.parsers.doctest import DocTestParser


@pytest.fixture
def live_fakturoid_creds():
    namespace = Namespace()
    namespace.TESTS_OBJECTS_NAME_PREFIX = "python-fakturoid-v3-test"
    try:
        namespace.FAKTUROID_SLUG = environ["FAKTUROID_SLUG"]
        namespace.FAKTUROID_CLIENT_ID = environ["FAKTUROID_CLIENT_ID"]
        namespace.FAKTUROID_CLIENT_SECRET = environ["FAKTUROID_CLIENT_SECRET"]
    except KeyError as err:
        pytest.mark.skip(f"Missing env variable {err}")
    else:
        return namespace


def scrub_authorization_from_requests(request):
    authorization = request.headers.get("Authorization", "")
    if authorization:
        request.headers["Authorization"] = "Basic DUMMY_VALUE"
    return request


def scrub_token_from_credentials_response(response):
    response = vcr.filters.decode_response(response)
    body_string = response["body"]["string"].decode("utf-8")
    if not body_string:
        return response
    body = json.loads(body_string)
    if "access_token" in body:
        body["access_token"] = "DUMMY_TOKEN"
        response["body"]["string"] = json.dumps(body).encode("utf-8")
    return response


# This fixture tells pytest-recording how to configure VCR
def pytest_recording_configure(config, vcr: vcr.VCR):
    config.decode_compressed_response = True
    config.filter_headers = ["Authorization"]
    vcr.before_record_request = scrub_authorization_from_requests
    vcr.before_record_response = scrub_token_from_credentials_response
