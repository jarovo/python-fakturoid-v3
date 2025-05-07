from __future__ import annotations

import re
from dataclasses import dataclass, field
import typing
from typing import Optional, Final, TypeVar, Any, Generic, Type, List
from datetime import datetime, timedelta
from functools import wraps
from pydantic import TypeAdapter
import base64
import logging


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

    def from_json(self):
        return self._requests_response.json()

    def page_count(self):
        if "link" in self._requests_response.headers:
            return extract_page_link(self._requests_response.headers["link"])
        else:
            return None


class RequestMethod(StrEnum):
    Get = "get"
    Post = "post"
    Put = "put"
    Delete = "delete"


@dataclass
class APIRequest:
    method: RequestMethod
    expected_response_code: int
    baseurl: str
    endpoint: str
    slug: Optional[str] = None
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    data: Optional[Model] = None
    api_response: Optional[APIResponse] = field(init=False, default=None)

    @property
    def url(self):
        if self.slug:
            return f"{self.baseurl}/accounts/{self.slug}/{self.endpoint}.json"
        else:
            return f"{self.baseurl}/{self.endpoint}.json"

    def send(self):
        LOGGER.debug(f"Sending request {self}")

        lib_response: requests.Response = getattr(requests, self.method.value)(
            self.url, headers=self.headers, params=self.params, data=self.data
        )
        lib_response.raise_for_status()

        if lib_response.status_code != self.expected_response_code:
            LOGGER.warning(
                f"Expected response code: {self.expected_response_code}, got f{lib_response.status_code} for request {self}"
            )

        self.api_response = APIResponse(lib_response)
        return self.api_response

    def set_authorization(self, user_agent: str, jwt_token: JWTToken):
        self.headers.update(
            {
                "User-Agent": user_agent,
                "Authorization": jwt_token.token_type + " " + jwt_token.access_token,
            }
        )


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


class LoadableClient(Generic[M]):
    def __init__(self, client: Fakturoid, base_path: str, model_cls: Type[M]):
        self.client = client
        self.base_path = base_path
        self.model_cls = model_cls

    def load(self) -> M:
        self.client._ensure_authenticated()
        raw = self.client._get(f"{self.base_path}.json")
        return self.model_cls.model_validate(raw)


class CollectionClient(Generic[U]):
    PER_PAGE: Final[int] = 40

    def __init__(self, client: Fakturoid, base_path: str, model_cls: Type[U]):
        self.client = client
        self.base_path = base_path
        self.model_cls = model_cls

    def get(self, id: int) -> U:
        self.client._ensure_authenticated()
        raw = self.client._get(f"{self.base_path}/{id}.json")
        return self._bind(self.model_cls.model_validate(raw))

    def _bind(self, obj: U) -> U:
        if isinstance(obj, Model):
            obj.__resource_path__ = self.base_path
        return obj

    def list(self, **params) -> List[U]:
        return list(self._paginated(f"{self.base_path}.json", **params))

    def search(self, **params) -> List[U]:
        return list(self._paginated(f"{self.base_path}/search.json", **params))

    def _paginated(self, path, **params) -> typing.Generator[U, None, None]:
        self.client._ensure_authenticated()
        page = 1
        per_page = 40  # Fixed number of items per page

        while True:
            # Include the `page` parameter in the request
            paged_params = {**params, "page": page}
            response = list(
                self.client._get(f"{self.base_path}.json", params=paged_params)
            )

            # Yield each item from the current page
            for item in response:
                yield self._bind(self.model_cls.model_validate(item))

            if per_page > len(response):
                break  # Stop if no results are returned

            page += 1  # Increment page number to fetch the next page

    def create(self, instance: U) -> U:
        self.client._ensure_authenticated()
        json_str = instance.model_dump_json(exclude_unset=True)
        raw = self.client._post(f"{self.base_path}.json", json_str)
        return self.model_cls.model_validate(raw)

    def delete(self, instance_id: int) -> None:
        self.client._ensure_authenticated()
        response = self.client.session.delete(
            f"{self.client.base_url}/{self.base_path}/{instance_id}.json"
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
        raw = self.client._patch(
            f"{self.base_path}/{instance.id}.json",
            payload.model_dump_json(exclude_unset=True),
        )
        return self.model_cls.model_validate(raw)

    def save(self, instance: U) -> U:
        if instance.id:
            return self.update(instance)
        else:
            return self.create(instance)


class Fakturoid:
    """Fakturoid API v3 - https://www.fakturoid.cz/api/v3"""

    slug: str
    client_id: str
    client_secret: str
    user_agent: str
    _token: JWTToken

    base_url = "https://app.fakturoid.cz/api/v3"

    def __init__(self, slug: str, client_id: str, client_secret: str, user_agent: str):
        self.slug = slug
        self.user_agent = user_agent
        self.client_id = client_id
        self.client_secret = client_secret

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

        self.current_user = LoadableClient[User](self, "user", User)
        self.account = LoadableClient[Account](
            self, f"accounts/{self.slug}/account", Account
        )
        self.users = CollectionClient[User](self, f"accounts/{self.slug}/users", User)
        self.bank_accounts = CollectionClient[BankAccount](
            self, f"accounts/{self.slug}/bank_accounts", BankAccount
        )
        self.subjects = CollectionClient[Subject](
            self, f"accounts/{self.slug}/subjects", Subject
        )
        self.invoices = CollectionClient[Invoice](
            self, f"accounts/{self.slug}/invoices", Invoice
        )
        self.inventory_items = CollectionClient[InventoryItem](
            self, f"accounts/{self.slug}/inventory_items", InventoryItem
        )
        self.expenses = CollectionClient[Expense](
            self, f"accounts/{self.slug}/expenses", Expense
        )
        self.generators = CollectionClient[Generator](
            self, f"accounts/{self.slug}/generators", Generator
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
        self._token = JWTToken(**resp.json())

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

    def _get(self, path: str, params=None) -> dict:
        url = f"{self.base_url}/{path}"
        response = self.session.get(url, params=params)
        if response.status_code == 404:
            raise NotFoundError(f"url={url}")
        else:
            response.raise_for_status()
        return response.json()

    def _post(self, path: str, data: str) -> dict:
        url = f"{self.base_url}/{path}"
        response = self.session.post(url, data=data)
        response.raise_for_status()
        return response.json()

    def _patch(self, path: str, json_str: str) -> dict:
        self._ensure_authenticated()
        response = self.session.patch(f"{self.base_url}/{path}", data=json_str)
        response.raise_for_status()
        return response.json()
