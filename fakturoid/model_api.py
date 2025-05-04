from typing import TYPE_CHECKING, Mapping, Any, TypeVar, Generic

if TYPE_CHECKING:
    from fakturoid.api import Fakturoid, APIResponse
    from fakturoid.models import Model

T = TypeVar('T', bound='Model')


def make(from_type: type[T], from_mapping: Mapping[str, Any]):
    return from_type.model_validate(from_mapping)


class ModelApi(Generic[T]):
    session: 'Fakturoid'
    model_type: type[T]

    def __init__(self, session):
        self.session = session

    def from_response(self, api_response: 'APIResponse'):
        api_response_dict = api_response.from_json()
        obj = make(self.model_type, api_response_dict)
        return obj

    def from_list_response(self, api_response: 'APIResponse'):
        return [make(self.model_type, item) for item in api_response.from_json()]
