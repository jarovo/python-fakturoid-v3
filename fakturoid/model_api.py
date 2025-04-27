from typing import TYPE_CHECKING
import requests
import re

if TYPE_CHECKING:
    from fakturoid.api import Fakturoid
    from fakturoid.models import Model


LINK_HEADER_PATTERN = re.compile(r'page=(\d+)[^>]*>; rel="last"')

def extract_page_link(header):
    m = LINK_HEADER_PATTERN.search(header)
    if m:
        return int(m.group(1))
    return None


class APIResponse:
    _requests_response: requests.Response

    def __init__(self, requests_response: requests.Response):
        self._requests_response = requests_response

    def from_json(self):
        return self._requests_response.json()

    def page_count(self):
        if 'link' in self._requests_response.headers:
            return extract_page_link(self._requests_response.headers['link'])
        else:
            return None


class ModelApi:
    session: 'Fakturoid' = None
    model_type: 'Model' = None
    endpoint: str = None

    def __init__(self, session):
        self.session = session

    def extract_id(self, value):
        if isinstance(value, int):
            return value
        if not isinstance(value, self.model_type):
            raise TypeError("int or {0} expected".format(self.model_type.__name__.lower()))
        if not getattr(value, 'id', None):
            raise ValueError("object wit unassigned id")
        return value.id

    def from_response(self, api_response: APIResponse):
        return self.model_type(**api_response.from_json())

    def from_list_response(self, api_response: APIResponse):
        return [self.model_type(**item) for item in api_response.from_json()]
