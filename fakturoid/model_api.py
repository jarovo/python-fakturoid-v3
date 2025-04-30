from typing import TYPE_CHECKING
import requests
import re

if TYPE_CHECKING:
    from fakturoid.api import Fakturoid, APIResponse
    from fakturoid.models import Model


class ModelApi:
    session: 'Fakturoid' = None
    model_type: 'Model' = None
    endpoint: str = None

    def __init__(self, session):
        self.session = session

    def from_response(self, api_response: 'APIResponse'):
        return self.model_type(**api_response.from_json())

    def from_list_response(self, api_response: 'APIResponse'):
        return [self.model_type(**item) for item in api_response.from_json()]
