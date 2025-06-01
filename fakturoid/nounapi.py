from abc import ABC
from dataclasses import dataclass, field
from fakturoid import api
from fakturoid import models
from pydantic import TypeAdapter
from typing import ClassVar, Self, Iterable
import types

import typing

import httpx
from os import environ
from string import Template
import base64
import argparse
from enum import StrEnum, auto
from datetime import datetime

from fakturoid.routing import Router


@dataclass
class FakturoidOAuth2CredsFlowAuth(httpx.Auth):
    token_url: str
    client_id: str
    client_secret: str
    user_agent: str
    jwt_token: api.JWTToken | None = None

    async def async_auth_flow(
        self, request: httpx.Request
    ) -> typing.AsyncGenerator[httpx.Request, httpx.Response]:
        if not self.jwt_token:
            await self.authenticate()
        assert self.jwt_token

        request.headers["User-Agent"] = self.user_agent
        request.headers["Authorization"] = (
            f"{self.jwt_token.token_type} {self.jwt_token.access_token}"
        )
        response = yield request

        if response.status_code == 401:
            # If the server issues a 401 response, then issue a request to
            # refresh tokens, and resend the request.
            await self.authenticate()
            request.headers["Authorization"] = (
                f"{self.jwt_token.token_type} {self.jwt_token.access_token}"
            )
            yield request

    async def authenticate(self):
        credentials = base64.urlsafe_b64encode(
            b":".join(
                (self.client_id.encode("utf-8"), self.client_secret.encode("utf-8"))
            )
        )
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": self.user_agent,
            "Authorization": "Basic " + credentials.decode(),
        }
        resp = await httpx.AsyncClient().post(
            f"{self.token_url}",
            headers=headers,
            content=r'{"grant_type": "client_credentials"}',
        )
        if resp.is_error:
            raise FakturoidApiError(resp)
        self.jwt_token = api.JWTToken.model_validate_json(resp.text)


@dataclass
class Fakturoid:
    slug: str = field(default_factory=lambda: environ.get("FAKTUROID_SLUG")) or ""
    user_agent: str = "python-fakturoid-v3-tests (jaroslav.henner@gmail.com)"
    fakturoid_url = "https://app.fakturoid.cz"

    def __post_init__(self):
        if not self.slug:
            raise ValueError("FAKTUROID_SLUG environment variable is required")

    base_path = "/api/v3"
    token_url = "https://app.fakturoid.cz/api/v3/oauth/token"
    http_client: httpx.AsyncClient = field(init=False)

    async def __aenter__(self):
        http_client = httpx.AsyncClient(
            base_url=self.fakturoid_url,
            auth=FakturoidOAuth2CredsFlowAuth(
                self.token_url,
                client_id=environ["FAKTUROID_CLIENT_ID"],
                client_secret=environ["FAKTUROID_CLIENT_SECRET"],
                user_agent=self.user_agent,
            ),
        )
        http_client.headers.update(
            {"Accept": "application/json", "Content-Type": "application/json"}
        )
        self.http_client = http_client
        return self

    async def __aexit__(
        self,
        exc_type: typing.Type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        if self.http_client:
            await self.http_client.aclose()


class FakturoidApiError(api.FakturoidError):
    def __init__(self, response: httpx.Response):
        self.response = response

    def __str__(self):
        return f"Error code: {self.response.status_code}, Response text: {self.response.text}"


@dataclass
class Verb(ABC):
    pass


class HttpMethod(StrEnum):
    GET = auto()
    OPTIONS = auto()
    HEAD = auto()
    POST = auto()
    PUT = auto()
    PATCH = auto()
    DELETE = auto()


class QueryParameters(argparse.Namespace):
    pass


@dataclass
class SimpleHttpVerb[T: models.Model]:
    router: Router
    response_model: type[T] = field(init=False)
    noun: T | type[T] = field(init=False)

    def __set_name__(self, owner: type[T], name: str) -> None:
        self.response_model = owner

    def __get__(self, obj: T | None, objtype: type[T] | None = None) -> Self:
        if obj is not None:
            self.noun = obj
        elif objtype is not None:
            self.noun = objtype
        else:
            raise AttributeError("Both obj and objtype are None in __get__")
        return self

    def _build_url(self, fakturoid: Fakturoid, path: str) -> str:
        return fakturoid.base_path + Template(path).substitute(slug=fakturoid.slug)


@dataclass
class AsyncCreateHttpVerb[T: models.Model](SimpleHttpVerb[T]):
    async def __call__(self, fakturoid: Fakturoid) -> T:
        assert isinstance(self.noun, models.Model), "Create requires model instance"

        url = self._build_url(fakturoid, self.router.create())
        response = await fakturoid.http_client.request(
            "POST",
            url,
            content=self.noun.model_dump_json(exclude_unset=True, round_trip=True),
        )
        if response.status_code != 201:
            raise FakturoidApiError(response)
        return self.response_model.model_validate_json(response.content)


@dataclass
class AsyncUpdateHttpVerb[T: models.UniqueMixin](SimpleHttpVerb[T]):
    async def __call__(self, fakturoid: Fakturoid) -> T:
        assert (
            isinstance(self.noun, models.UniqueMixin) and self.noun.id
        ), "Update requires model with id"

        url = self._build_url(fakturoid, self.router.detail(self.noun.id))
        response = await fakturoid.http_client.request(
            "PATCH",
            url,
            content=self.noun.model_dump_json(exclude_unset=True, round_trip=True),
        )
        if response.status_code != 200:
            raise FakturoidApiError(response)
        return self.response_model.model_validate_json(response.content)


@dataclass
class AsyncLoadHttpVerb[T: models.Model](SimpleHttpVerb[T]):
    async def __call__(self, fakturoid: Fakturoid) -> T:
        assert isinstance(self.noun, models.Model)
        url = self._build_url(fakturoid, self.router.load())
        response = await fakturoid.http_client.request("GET", url)
        if response.status_code != 200:
            raise FakturoidApiError(response)
        return self.response_model.model_validate_json(response.content)


@dataclass
class AsyncDetailHttpVerb[T: models.UniqueMixin](SimpleHttpVerb[T]):
    async def __call__(self, fakturoid: Fakturoid) -> T:
        assert (
            isinstance(self.noun, models.UniqueMixin) and self.noun.id
        ), "Detail requires model with id"

        url = self._build_url(fakturoid, self.router.detail(self.noun.id))
        response = await fakturoid.http_client.request("GET", url)
        if response.status_code != 200:
            raise FakturoidApiError(response)
        return self.response_model.model_validate_json(response.content)


@dataclass
class AsyncPagedHttpVerb[T: models.Model](SimpleHttpVerb[T]):
    PER_PAGE: ClassVar[int] = 40

    async def __call__(
        self, fakturoid: Fakturoid, query_params: QueryParameters | None = None
    ) -> typing.AsyncGenerator[T, None]:
        params = query_params.__dict__ if query_params else {}
        params.setdefault("page", 1)

        while True:
            url = self._build_url(fakturoid, self.router.index())
            response = await fakturoid.http_client.request("GET", url, params=params)
            if response.status_code != 200:
                raise FakturoidApiError(response)

            ta = TypeAdapter(list[self.response_model])  # type: ignore[name-defined]
            # Validate the response as a list of items
            # and yield each item
            items = ta.validate_python(response.json())
            for item in items:
                yield item

            if len(items) < self.PER_PAGE:
                break
            params["page"] += 1


@dataclass
class AsyncDeleteHttpVerb[T: models.UniqueMixin](SimpleHttpVerb[T]):
    async def __call__(self, fakturoid: Fakturoid) -> None:
        assert (
            isinstance(self.noun, models.UniqueMixin) and self.noun.id
        ), "Delete requires model with id"
        url = self._build_url(fakturoid, self.router.delete(self.noun.id))
        response = await fakturoid.http_client.request("DELETE", url)
        if response.status_code != 204:
            raise FakturoidApiError(response)


class Account(models.Account):
    router: ClassVar = Router("accounts")

    a_detail: ClassVar = AsyncLoadHttpVerb[Self](router)


class Subject(models.Subject):
    router: ClassVar = Router("subjects")

    a_create: ClassVar = AsyncCreateHttpVerb[Self](router)
    a_update: ClassVar = AsyncUpdateHttpVerb[Self](router)
    a_index: ClassVar = AsyncPagedHttpVerb[Self](router)
    a_search: ClassVar = AsyncPagedHttpVerb[Self](router)  # Will use search() method
    a_detail: ClassVar = AsyncDetailHttpVerb[Self](router)
    a_delete: ClassVar = AsyncDeleteHttpVerb[Self](router)

    class IndexQueryParameters(QueryParameters):
        since: datetime
        updated_since: datetime
        custom_id: str
        page: int = 1

    class SearchQueryParameters(QueryParameters):
        query: str
        page: int = 1


@dataclass
class AsyncActionHttpVerb[T: models.UniqueMixin](SimpleHttpVerb[T]):
    async def __call__(
        self, action: models.InvoiceAction, fakturoid: Fakturoid
    ) -> None:
        assert (
            isinstance(self.noun, models.UniqueMixin) and self.noun.id
        ), "Action requires model with id"

        url = self._build_url(fakturoid, self.router.fire_action(self.noun.id))
        response = await fakturoid.http_client.request(
            "POST", url, params={"event": action.value}
        )
        if response.status_code != 200:
            raise FakturoidApiError(response)


class Invoice(models.Invoice):
    router: ClassVar = Router("invoices")

    a_create: ClassVar = AsyncCreateHttpVerb[Self](router)
    a_update: ClassVar = AsyncUpdateHttpVerb[Self](router)
    a_index: ClassVar = AsyncPagedHttpVerb[Self](router)
    a_search: ClassVar = AsyncPagedHttpVerb[Self](router)
    a_detail: ClassVar = AsyncDetailHttpVerb[Self](router)
    a_delete: ClassVar = AsyncDeleteHttpVerb[Self](router)
    a_fire_action: ClassVar = AsyncActionHttpVerb[Self](router)

    class IndexQueryParameters(QueryParameters):
        since: datetime
        updated_since: datetime
        page: int = 1
        subject_id: int
        custom_id: str
        number: str
        variable_symbol: str
        status: str

    class SearchQueryParameters(QueryParameters):
        query: str
        tags: Iterable[str]
        page: int = 1
