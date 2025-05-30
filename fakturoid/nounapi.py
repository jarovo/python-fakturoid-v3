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
from datetime import datetime

from fakturoid.routing import (
    RouteParamAware,
    RouteParamResolver,
    RouteParamProvider,
    route_param,
)


@dataclass
class FakturoidAuth(httpx.Auth):
    user_agent: str
    jwt_token: api.JWTToken

    async def async_auth_flow(self, request: httpx.Request):
        request.headers["User-Agent"] = self.user_agent
        request.headers["Authorization"] = (
            f"{self.jwt_token.token_type} {self.jwt_token.access_token}"
        )
        yield request


@dataclass
class Fakturoid(RouteParamAware):
    slug: str
    user_agent = "python-fakturoid-v3[nounapi]"
    FAKTUROID_URL = "https://app.fakturoid.cz"
    BASE_PATH = "/api/v3"
    TOKEN_URL = "https://app.fakturoid.cz/api/v3/oauth/token"
    http_client: httpx.AsyncClient = httpx.AsyncClient(base_url=FAKTUROID_URL)

    @staticmethod
    def from_env():
        return dict(
            client_id=environ["FAKTUROID_CLIENT_ID"],
            client_secret=environ["FAKTUROID_CLIENT_SECRET"],
        )

    async def _oauth_token_client_credentials_flow(
        self, client_id: str, client_secret: str
    ):
        credentials = base64.urlsafe_b64encode(
            b":".join((client_id.encode("utf-8"), client_secret.encode("utf-8")))
        )
        headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
            "Authorization": "Basic " + credentials.decode(),
        }
        resp = await self.http_client.post(
            f"{self.TOKEN_URL}",
            headers=headers,
            data={"grant_type": "client_credentials"},
        )
        resp.raise_for_status()
        token = api.JWTToken.model_validate_json(resp.text)
        self.http_client.auth = FakturoidAuth(self.user_agent, jwt_token=token)
        self.http_client.headers.update(
            {"Accept": "application/json", "Content-Type": "application/json"}
        )

    @property
    @route_param("slug")
    def org_slug(self) -> str:
        return self.slug


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
        return fakturoid.FAKTUROID_URL + fakturoid.BASE_PATH + path

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
        query_params: argparse.Namespace = argparse.Namespace(),
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
        params: argparse.Namespace = argparse.Namespace(),
    ):
        response = await super().make_http_call(url, payload, fakturoid, params=params)
        self.expect_response_code(response, 200)
        return TypeAdapter(typing.List[self.model_t]).validate_json(response.text)  # type: ignore[name-defined]

    async def load_all_pages(
        self,
        url: str,
        payload: str,
        fakturoid: Fakturoid,
        params: argparse.Namespace = argparse.Namespace(),
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
            url, self.noun.model_dump_json(), fakturoid
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

    acreate: ClassVar = AsyncCreateHttpVerb[Self](
        Template("/accounts/${slug}/subjects.json")
    )
    aupdate: ClassVar = AsyncUpdateHttpVerb[Self](
        Template("/accounts/${slug}/subjects/${id}.json")
    )
    aindex: ClassVar = AsyncPagedHttpVerb[Self](
        Template("/accounts/${slug}/subjects.json")
    )
    asearch: ClassVar = AsyncPagedHttpVerb[Self](
        Template("/accounts/${slug}/subjects/search.json")
    )
    adetail: ClassVar = AsyncDetailHttpVerb[Self](
        Template("/accounts/${slug}/subjects/${id}.json")
    )
    adelete: ClassVar = AsyncDeleteHttpVerb[Self](
        Template("/accounts/${slug}/subjects/${id}.json")
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

    acreate: ClassVar = AsyncCreateHttpVerb[Self](
        Template("/accounts/${slug}/invoices.json")
    )
    aupdate: ClassVar = AsyncUpdateHttpVerb[Self](
        Template("/accounts/${slug}/invoices/${id}.json")
    )
    aindex: ClassVar = AsyncPagedHttpVerb[Self](
        Template("/accounts/${slug}/invoices.json")
    )
    asearch: ClassVar = AsyncPagedHttpVerb[Self](
        Template("/accounts/${slug}/invoices/search.json")
    )
    adetail: ClassVar = AsyncDetailHttpVerb[Self](
        Template("/accounts/${slug}/invoices/${id}.json")
    )
    adelete: ClassVar = AsyncDeleteHttpVerb[Self](
        Template("/accounts/${slug}/invoices/${id}.json")
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
