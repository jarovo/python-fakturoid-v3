from __future__ import annotations

from abc import ABC, abstractmethod
import re
from dataclasses import dataclass, field
import typing
from typing import Optional, Final, TypeVar, Generic, Type, List
from datetime import datetime, timedelta
from functools import wraps
from pydantic import TypeAdapter
import base64
import logging
from string import Template
from os import environ

import requests

from fakturoid.models import (
    Model,
    Account,
    User,
    BankAccount,
    Subject,
    Invoice,
    InventoryItem,
    Generator,
    Expense,
    UniqueMixin,
    InvoiceAction,
    LockableAction,
)
from fakturoid.strenum import StrEnum

__all__ = ["Fakturoid", "NotFoundError"]


LOGGER: Final = logging.getLogger("python-fakturoid-v3")
LINK_HEADER_PATTERN: Final = re.compile(r'page=(\d+)[^>]*>; rel="last"')


def extract_page_link(header):
    m = LINK_HEADER_PATTERN.search(header)
    if m:
        return int(m.group(1))
    return None


class APIResponse:
    _requests_response: requests.Response

    def __init__(self, requests_response: requests.Response):
        self._requests_response = requests_response

    @property
    def text(self):
        return self._requests_response.text

    def json(self):
        return self._requests_response.json()


class JWTToken(Model):
    token_type: str
    access_token: str

    # Default token is expired and is gonna be renewed upon next request.
    expires_in: timedelta = field(default_factory=lambda: timedelta(seconds=-1))
    created_at: datetime = field(default_factory=lambda: datetime.now())

    @property
    def renew_after(self):
        """Token is to be renewed sooner than it expires to provide a buffer time for the renewal."""
        return self.created_at + self.expires_in / 2

    @property
    def to_be_renewed(self):
        now = datetime.now()
        return self.renew_after <= now

    @property
    def expiration_time(self):
        return self.created_at + self.expires_in

    @property
    def is_expired(self):
        """Returns True when token had expired."""
        now = datetime.now()
        assert (
            self.created_at <= now
        ), f"Token should be created in the past, got {self.created_at}, now is {now}"
        return self.expiration_time < now


class FakturoidError(Exception):
    pass


class NotFoundError(FakturoidError):
    pass


M = TypeVar("M", bound=Model)
U = TypeVar("U", bound=UniqueMixin)


class APIBase(ABC):
    _client: Optional[Fakturoid]

    def __init__(self, base_path_context: Optional[dict[str, str]] = None):
        self.base_path_context = base_path_context or {}

    @property
    def client(self) -> Fakturoid:
        assert self._client
        return self._client

    @property
    @abstractmethod
    def base_path_template(self) -> Template:
        raise NotImplementedError("Subclasses must implement this method.")

    def base_path(self, **kwargs) -> str:
        return self.base_path_template.substitute(
            slug=self.client.slug, **self.base_path_context, **kwargs
        )

    def __get__(self, obj, objtype=None):
        self._client = obj
        return self


class LoadableAPI(APIBase, Generic[M]):
    @property
    def _model_type(self) -> Type[M]:
        raise NotImplementedError("Subclasses must implement this method.")

    def load(self) -> M:
        self.client._ensure_authenticated()
        response = self.client._get(f"{self.base_path()}.json")
        return self._model_type.model_validate_json(response.text)


class CollectionAPI(APIBase, Generic[U]):
    PER_PAGE: Final[int] = 40
    _model_type: Type[U]
    _page_type_adapter: TypeAdapter[List[U]]

    def get(self, id: int) -> U:
        self.client._ensure_authenticated()
        response = self.client._get(f"{self.base_path()}/{id}.json")
        return self._bind(self._model_type.model_validate_json(response.text))

    def _bind(self, obj: U) -> U:
        assert isinstance(obj, Model)
        obj.__resource_path__ = self.base_path()
        return obj

    def list(self, **params) -> List[U]:
        return list(self._paginated(f"{self.base_path()}.json", **params))

    def search(self, **params) -> List[U]:
        return list(self._paginated(f"{self.base_path()}/search.json", **params))

    def _paginated(self, path, **params) -> typing.Generator[U, None, None]:
        self.client._ensure_authenticated()
        page_no = 1

        while True:
            # Include the `page` parameter in the request
            paged_params = {**params, "page": page_no}
            response = self.client._get(f"{self.base_path()}.json", params=paged_params)
            results_page = self._page_type_adapter.validate_json(response.text)
            # Yield each item from the current page
            for item in results_page:
                yield self._bind(item)

            if self.PER_PAGE > len(results_page):
                break  # Stop if no results are returned

            page_no += 1  # Increment page number to fetch the next page

    def create(self, instance: U) -> U:
        self.client._ensure_authenticated()
        json_str = instance.model_dump_json(exclude_unset=True)
        response = self.client._post(f"{self.base_path()}.json", json_str)
        return self._model_type.model_validate_json(response.text)

    def delete(self, instance_id: int) -> None:
        self.client._ensure_authenticated()
        response = self.client.session.delete(
            f"{self.client.base_url}/{self.base_path()}/{instance_id}.json"
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as err:
            fakturoid_error = FakturoidError(
                f"Couldn't delete {instance_id}. {response.text}"
            )
            raise fakturoid_error from err

    def find(self, **kwargs) -> typing.Generator[U]:
        all_items = self.list(**kwargs)
        for item in all_items:
            if all(getattr(item, k, None) == v for k, v in kwargs.items()):
                yield item

    def update(self, instance: U) -> U:
        payload = instance.to_patch_payload()
        self.client._ensure_authenticated()
        response = self.client._patch(
            f"{self.base_path()}/{instance.id}.json",
            payload.model_dump_json(exclude_unset=True),
        )
        return self._model_type.model_validate_json(response.text)

    def save(self, instance: U) -> U:
        if instance.id:
            return self.update(instance)
        else:
            return self.create(instance)


A = TypeVar("A", bound=StrEnum)


class ActionAPI(APIBase, Generic[A]):
    path_template: Template
    slug: str

    def fire(self, id: int, action: A):
        url = self.base_path(id=id)
        self.client._post(url, data=None, params={"event": action.value})


def create_collection_api_class(
    model: Type[U], _base_path_template: Template
) -> type[CollectionAPI[U]]:
    class _AutoAPI(CollectionAPI[U]):
        base_path_template = _base_path_template
        _model_type = model
        _page_type_adapter = TypeAdapter(list[model])  # type: ignore[valid-type]

    _AutoAPI.__name__ = f"{model.__name__}sCollectionAPI"
    return _AutoAPI


@dataclass
class Fakturoid:
    """Fakturoid API v3 - https://www.fakturoid.cz/api/v3"""

    slug: str
    client_id: str
    client_secret: str
    user_agent: str = (
        "python-fakturoid-v3 (https://github.com/jarovo/python-fakturoid-v3)"
    )
    _token: JWTToken = field(init=False)
    session: requests.Session = field(init=False)

    @classmethod
    def from_env(cls):
        return cls(
            slug=environ["FAKTUROID_SLUG"],
            client_id=environ["FAKTUROID_CLIENT_ID"],
            client_secret=environ["FAKTUROID_CLIENT_SECRET"],
        )

    subjects = create_collection_api_class(
        Subject, Template("accounts/${slug}/subjects")
    )()
    invoices = create_collection_api_class(
        Invoice, Template("accounts/${slug}/invoices")
    )()

    class UserAPI(LoadableAPI[User]):
        base_path_template = Template("user")
        _model_type = User

    current_user = UserAPI()

    class AccountApi(LoadableAPI[Account]):
        base_path_template = Template("accounts/${slug}/account")
        _model_type = Account

    account = AccountApi()

    users = create_collection_api_class(User, Template("accounts/${slug}/users"))()
    bank_accounts = create_collection_api_class(
        BankAccount, Template("accounts/${slug}/bank_accounts")
    )()

    class InvoiceActionAPI(ActionAPI[InvoiceAction]):
        base_path_template = Template("accounts/${slug}/invoices/${id}/fire.json")

    invoice_event = InvoiceActionAPI()

    inventory_items = create_collection_api_class(
        InventoryItem, Template("accounts/${slug}/inventory_items")
    )()
    expenses = create_collection_api_class(
        Expense, Template("accounts/${slug}/expenses")
    )()

    class ExpenseActionAPI(ActionAPI[LockableAction]):
        base_path_template = Template("accounts/${slug}/invoices/${id}/fire.json")

    expense_event = ExpenseActionAPI()

    generators = create_collection_api_class(
        Generator, Template("accounts/${slug}/generators")
    )()

    base_url = "https://app.fakturoid.cz/api/v3"

    def __post_init__(self):
        # Init to dummy expired token that is about to lazy renewal.
        self._token = JWTToken(
            token_type="placeholder_token", access_token="", expires_in=timedelta(-1)
        )

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def _ensure_token(self):
        if self._token.to_be_renewed:
            LOGGER.debug("Renewing _token.")
            self._oauth_token_client_credentials_flow()
            LOGGER.debug(f"Got new _token. {self._token}")
        return self._token

    def _oauth_token_client_credentials_flow(self):
        credentials = base64.urlsafe_b64encode(
            b":".join(
                (self.client_id.encode("utf-8"), self.client_secret.encode("utf-8"))
            )
        )
        headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
            "Authorization": "Basic " + credentials.decode(),
        }
        resp = requests.post(
            f"{self.base_url}/oauth/token",
            headers=headers,
            data={"grant_type": "client_credentials"},
        )
        resp.raise_for_status()
        self._token = JWTToken.model_validate_json(resp.text)

    def _ensure_authenticated(self):
        self._ensure_token()
        self._set_authorization(self.user_agent, self._token)

    def _set_authorization(self, user_agent: str, jwt_token: JWTToken):
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Authorization": jwt_token.token_type + " " + jwt_token.access_token,
            }
        )

    def _get(self, path: str, params=None) -> APIResponse:
        url = f"{self.base_url}/{path}"
        response = self.session.get(url, params=params)
        if response.status_code == 404:
            raise NotFoundError(f"url={url}")
        else:
            response.raise_for_status()
        return APIResponse(response)

    def _post(
        self, path: str, data: str | None, params: Optional[dict[str, str]] = None
    ) -> APIResponse:
        url = f"{self.base_url}/{path}"
        response = self.session.post(url, data=data, params=params)
        try:
            response.raise_for_status()
        except requests.HTTPError as err:
            new_err = FakturoidError(response.text)
            raise new_err from err
        return APIResponse(response)

    def _patch(self, path: str, json_str: str) -> APIResponse:
        self._ensure_authenticated()
        response = self.session.patch(f"{self.base_url}/{path}", data=json_str)
        response.raise_for_status()
        return APIResponse(response)
