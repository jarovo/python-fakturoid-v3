import json
from urllib.parse import parse_qs
import vcr
from datetime import datetime


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
    import pdb

    config.decode_compressed_response = True
    config.filter_headers = ["Authorization"]
    vcr.before_record_request = scrub_authorization_from_requests
    vcr.before_record_response = scrub_token_from_credentials_response
