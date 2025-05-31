from abc import ABC
from dataclasses import dataclass, field
from fakturoid import api
from fakturoid import models
from pydantic import TypeAdapter
from typing import ClassVar, Self, Iterable

import typing

import httpx
from os import environ
from string import Template
import base64
import argparse
from enum import StrEnum, auto
import copy
from datetime import datetime, timedelta

from fakturoid.routing import (
    RouteParamAware,
    RouteParamResolver,
    RouteParamProvider,
    route_param,
)


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
class Fakturoid(RouteParamAware):
    slug: str = environ["FAKTUROID_SLUG"]
    user_agent = "python-fakturoid-v3-tests (jaroslav.henner@gmail.com)"
    fakturoid_url = "https://app.fakturoid.cz"
    base_path = "/api/v3"
    token_url = "https://app.fakturoid.cz/api/v3/oauth/token"
    http_client: httpx.AsyncClient = field(init=False)

    @property
    @route_param("slug")
    def org_slug(self) -> str:
        return self.slug

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

    async def __aexit__(self, exc_type, exc_val, exc_tb):
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
class AsyncHTTPVerb[T: RouteParamProvider](Verb):
    http_method: ClassVar[HttpMethod]
    path_template: Template
    model_t: type[T] = field(init=False)
    noun: T = field(init=False)

    def __get__(self, obj: T, objtype: type[T]):
        self.noun = obj
        self.model_t = type(self.noun)
        return self

    def build_url(self, fakturoid: Fakturoid):
        resolver = RouteParamResolver([fakturoid, self.noun])
        path = resolver.substitute(self.path_template)
        return fakturoid.base_path + path

    async def make_http_call(
        self,
        url: str,
        payload: str,
        fakturoid: Fakturoid,
        params: argparse.Namespace = argparse.Namespace(),
    ):
        return await fakturoid.http_client.request(
            method=self.http_method, url=url, params=params.__dict__, content=payload
        )

    @staticmethod
    def expect_response_code(response: httpx.Response, code: int):
        if response.status_code == code:
            return
        else:
            raise FakturoidApiError(response)


class AsyncDetailHttpVerb[T: models.Model](AsyncHTTPVerb[T]):
    http_method = HttpMethod.GET

    async def __call__(self, fakturoid: Fakturoid):
        url = self.build_url(fakturoid)
        response = await self.make_http_call(
            url=url, payload=self.noun.model_dump_json(), fakturoid=fakturoid
        )
        self.expect_response_code(response, 200)
        return TypeAdapter(self.model_t).validate_json(response.content)


class AsyncPagedHttpVerb[T: models.Model](AsyncHTTPVerb[T]):
    PER_PAGE = 40
    http_method = HttpMethod.GET

    async def __call__(
        self,
        fakturoid: Fakturoid,
        query_params: argparse.Namespace = argparse.Namespace(page=1),
    ) -> typing.AsyncGenerator[T, None]:
        url = self.build_url(fakturoid)
        return self.load_all_pages(
            url=url, payload="", fakturoid=fakturoid, params=query_params
        )

    async def get_page(
        self,
        url: str,
        payload: str,
        fakturoid: Fakturoid,
        params: argparse.Namespace,
    ):
        response = await super().make_http_call(url, payload, fakturoid, params=params)
        self.expect_response_code(response, 200)
        return TypeAdapter(typing.List[self.model_t]).validate_json(response.text)  # type: ignore[name-defined]

    async def load_all_pages(
        self,
        url: str,
        payload: str,
        fakturoid: Fakturoid,
        params: argparse.Namespace,
    ):
        params = copy.copy(params)
        while True:
            results_page = await self.get_page(
                url=url, payload=payload, fakturoid=fakturoid, params=params
            )
            for item in results_page:
                yield item

            if self.PER_PAGE > len(results_page):
                break  # Stop if no results are returned

            params.page += 1  # Increment page number to fetch the next page


class AsyncCreateHttpVerb[T: models.Model](AsyncHTTPVerb[T]):
    http_method = HttpMethod.POST

    async def __call__(self, fakturoid: Fakturoid) -> T:
        url = self.build_url(fakturoid)
        response = await self.make_http_call(
            url, self.noun.model_dump_json(exclude_unset=True), fakturoid
        )
        self.expect_response_code(response, 201)  # Created
        return self.model_t.model_validate_json(response.content)


class AsyncUpdateHttpVerb[T: models.Model](AsyncHTTPVerb[T]):
    http_method = HttpMethod.PATCH

    async def __call__(self, fakturoid: Fakturoid) -> T:
        payload = self.noun.to_patch_payload()
        url = self.build_url(fakturoid)
        response = await self.make_http_call(
            url, self.model_t.model_dump_json(payload), fakturoid
        )
        self.expect_response_code(response, 200)
        return self.model_t.model_validate_json(response.content)


class AsyncDeleteHttpVerb[T: models.Model](AsyncHTTPVerb[T]):
    http_method = HttpMethod.DELETE

    async def __call__(self, fakturoid: Fakturoid):
        url = self.build_url(fakturoid)
        response = await self.make_http_call(
            url, self.noun.model_dump_json(), fakturoid
        )
        self.expect_response_code(response, 204)  # No content


class User(models.User, RouteParamAware):
    acurrent: ClassVar = AsyncDetailHttpVerb[Self](Template("/accounts/user.json"))
    aindex: ClassVar = AsyncPagedHttpVerb[Self](
        Template("/accounts/${slug}/users.json")
    )


class Account(models.Account):
    adetail: ClassVar = AsyncDetailHttpVerb[Self](
        Template("/accounts/${slug}/account.json")
    )


class BankAccount(models.BankAccount):
    adetail: ClassVar = AsyncDetailHttpVerb[Self](
        Template("/accounts/${slug}/bankaccount.json")
    )


class NumberFormat(models.NumberFormat):
    adetail: ClassVar = AsyncPagedHttpVerb[Self](
        Template("/accounts/${slug}/number_formats/invoices.json")
    )


class Subject(models.Subject):
    @property
    @route_param("id")
    def subject_id(self) -> str:
        return str(self.id)

    @property
    @route_param("resource")
    def resource(self):
        return "subjects"

    a_create: ClassVar = AsyncCreateHttpVerb[Self](
        Template("/accounts/${slug}/${resource}.json")
    )
    a_update: ClassVar = AsyncUpdateHttpVerb[Self](
        Template("/accounts/${slug}/${resource}/${id}.json")
    )
    a_index: ClassVar = AsyncPagedHttpVerb[Self](
        Template("/accounts/${slug}/${resource}.json")
    )
    a_search: ClassVar = AsyncPagedHttpVerb[Self](
        Template("/accounts/${slug}/${resource}/search.json")
    )
    a_detail: ClassVar = AsyncDetailHttpVerb[Self](
        Template("/accounts/${slug}/${resource}/${id}.json")
    )
    a_delete: ClassVar = AsyncDeleteHttpVerb[Self](
        Template("/accounts/${slug}/${resource}/${id}.json")
    )

    class IndexQueryParameters(QueryParameters):
        since: datetime
        updated_since: datetime
        custom_id: str
        page: int = 1

    class SearchQueryParameters(QueryParameters):
        query: str
        page: int = 1


class Invoice(models.Invoice):
    @property
    @route_param("id")
    def invoice_id(self) -> str:
        return str(self.id)

    @property
    @route_param("resource")
    def resource(self):
        return "invoices"

    a_create: ClassVar = AsyncCreateHttpVerb[Self](
        Template("/accounts/${slug}/${resource}.json")
    )
    a_update: ClassVar = AsyncUpdateHttpVerb[Self](
        Template("/accounts/${slug}/${resource}/${id}.json")
    )
    a_index: ClassVar = AsyncPagedHttpVerb[Self](
        Template("/accounts/${slug}/${resource}.json")
    )
    a_search: ClassVar = AsyncPagedHttpVerb[Self](
        Template("/accounts/${slug}/${resource}/search.json")
    )
    a_detail: ClassVar = AsyncDetailHttpVerb[Self](
        Template("/accounts/${slug}/${resource}/${id}.json")
    )
    a_delete: ClassVar = AsyncDeleteHttpVerb[Self](
        Template("/accounts/${slug}/${resource}/${id}.json")
    )

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
