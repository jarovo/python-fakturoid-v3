from __future__ import annotations
from abc import ABC
import re
from dataclasses import dataclass, field
import typing
from typing import Optional, Final, Type, List, Mapping, Dict, Any
from datetime import datetime, timedelta
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
    Payment,
    InvoicePayment,
    ExpensePayment,
)
from fakturoid.strenum import StrEnum


__all__ = ["Fakturoid", "NotFoundError"]


LOGGER: Final = logging.getLogger("python-fakturoid-v3")
LINK_HEADER_PATTERN: Final = re.compile(r'page=(\d+)[^>]*>; rel="last"')


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


class APIBase(ABC):
    _fakturoid: Optional["Fakturoid"]
    base_path_template: Template

    def __init__(self, base_path_context: Optional[dict[str, str]] = None):
        self.base_path_context = base_path_context or {}

    @property
    def fakturoid(self) -> "Fakturoid":
        assert self._fakturoid
        return self._fakturoid

    def base_path(self, **kwargs: str) -> str:
        return self.base_path_template.substitute(
            slug=self.fakturoid.slug, **self.base_path_context, **kwargs
        )

    def __get__(self, obj: Fakturoid, objtype: Optional[Type[Fakturoid]] = None):
        self._fakturoid = obj
        return self


class LoadableAPI[M: Model](APIBase):
    _model_type: Type[M]

    @property
    def _model_type_(self) -> Type[M]:
        raise NotImplementedError("Subclasses must implement this method.")

    def load(self) -> M:
        self.fakturoid.ensure_authenticated()
        response = self.fakturoid.get(f"{self.base_path()}.json")
        return self._model_type.model_validate_json(response.text)


class AbstractCollectionAPI[T_UniqueMixin: UniqueMixin](APIBase):
    PER_PAGE: Final[int] = 40
    _model_type: Type[T_UniqueMixin]
    _page_type_adapter: TypeAdapter[List[T_UniqueMixin]]

    def get(self, id: int) -> T_UniqueMixin:
        self.fakturoid.ensure_authenticated()
        response = self.fakturoid.get(f"{self.base_path()}/{id}.json")
        return self._bind(self._model_type.model_validate_json(response.text))

    def _bind(self, obj: T_UniqueMixin) -> T_UniqueMixin:
        assert isinstance(obj, Model)
        obj.__resource_path__ = self.base_path()
        return obj

    def list(self, **params: str) -> typing.Iterable[T_UniqueMixin]:
        """
        Deprecated. Use index.
        """
        return list(self.index(**params))

    def index(self, **params: str) -> typing.Iterator[T_UniqueMixin]:
        """
        Returns iterator over all items in collection.
        """
        return self._paginated(f"{self.base_path()}.json", **params)

    def find(self, **kwargs: Any) -> typing.Iterator[T_UniqueMixin]:
        all_items = self.index(**kwargs)
        for item in all_items:
            if all(getattr(item, k) == v for k, v in kwargs.items()):
                yield item

    def search(self, **params: str) -> typing.Iterator[T_UniqueMixin]:
        """
        Does fulltext search
        """
        return self._paginated(f"{self.base_path()}/search.json", **params)

    def _paginated(self, path: str, **params: str) -> typing.Iterator[T_UniqueMixin]:
        self.fakturoid.ensure_authenticated()
        page_no = 1

        while True:
            # Include the `page` parameter in the request
            paged_params: Dict[str, str] = {**params, "page": str(page_no)}
            response = self.fakturoid.get(
                f"{self.base_path()}.json", params=paged_params
            )
            results_page = self._page_type_adapter.validate_json(response.text)
            # Yield each item from the current page
            for item in results_page:
                yield self._bind(item)

            if self.PER_PAGE > len(results_page):
                break  # Stop if no results are returned

            page_no += 1  # Increment page number to fetch the next page

    def create(self, instance: T_UniqueMixin) -> T_UniqueMixin:
        self.fakturoid.ensure_authenticated()
        json_str = instance.model_dump_json(exclude_unset=True)
        response = self.fakturoid.post(f"{self.base_path()}.json", json_str)
        return self._model_type.model_validate_json(response.text)

    def delete(self, instance_id: int) -> None:
        self.fakturoid.ensure_authenticated()
        response = self.fakturoid.session.delete(
            f"{self.fakturoid.base_url}/{self.base_path()}/{instance_id}.json"
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as err:
            fakturoid_error = FakturoidError(
                f"Couldn't delete {instance_id}. {response.text}"
            )
            raise fakturoid_error from err

    def update(self, instance: T_UniqueMixin) -> T_UniqueMixin:
        payload = instance.to_patch_payload()
        self.fakturoid.ensure_authenticated()
        response = self.fakturoid.patch(
            f"{self.base_path()}/{instance.id}.json",
            payload.model_dump_json(exclude_unset=True),
        )
        return self._model_type.model_validate_json(response.text)

    def save(self, instance: T_UniqueMixin) -> T_UniqueMixin:
        if instance.id:
            return self.update(instance)
        else:
            return self.create(instance)


class ActionAPI[A: StrEnum](APIBase):
    base_path_template: Template
    slug: str

    def fire(self, id: int, action: A):
        path = self.base_path(id=str(id))
        self.fakturoid.post(path, data=None, params={"event": action.value})


class PaymentsAPI[T_UniqueMixin: UniqueMixin, T_Payment: Payment](APIBase):
    model: type[T_Payment]

    def create(self, payable: T_UniqueMixin, payment: T_Payment) -> T_Payment:
        assert payable.id
        response = self._create(payable_id=payable.id, payment=payment)
        return self.model.model_validate_json(response.text)

    def _create(self, payable_id: int, payment: T_Payment):
        path = self.base_path(payable_id=str(payable_id)) + ".json"
        self.fakturoid.ensure_authenticated()
        response = self.fakturoid.post(path, data=payment.model_dump_json())
        return response

    def delete(self, payable: T_UniqueMixin, payment: T_Payment):
        assert payable.id
        assert payment.id
        path = self.base_path(payable_id=str(payable.id)) + f"/{payment.id}.json"
        self.fakturoid.delete(path)


class InvoicePaymentsAPI(PaymentsAPI[Invoice, InvoicePayment]):
    model = InvoicePayment
    base_path_template = Template(r"accounts/${slug}/invoices/${payable_id}/payments")

    def create_tax_document(self, invoice: Invoice, payment: InvoicePayment):
        assert invoice.id
        assert payment.id
        path = (
            self.base_path(payble_id=str(invoice.id))
            + f"/{payment.id}/create_tax_document.json"
        )
        response = self.fakturoid.post(path, data=payment.model_dump_json())
        return InvoicePayment.model_validate_json(response.text)


class ExpensePaymentsAPI(PaymentsAPI[Expense, ExpensePayment]):
    model = ExpensePayment
    base_path_template = Template(r"accounts/${slug}/expenses/${payable_id}/payments")


def create_collection_api_class[T_UniqueMixin: UniqueMixin](
    model_t: Type[T_UniqueMixin],
    base_path_template_: Template,
) -> type[AbstractCollectionAPI[T_UniqueMixin]]:

    class _AutoAPI(AbstractCollectionAPI[T_UniqueMixin]):
        _model_type = model_t
        base_path_template = base_path_template_
        _page_type_adapter = TypeAdapter(List[model_t])  # type: ignore[valid-type]

    _AutoAPI.__name__ = f"{model_t.__name__}sCollectionAPI"

    # Cast the return type for static type checkers
    # return cast(type[CollectionAPI[T]], _AutoAPI)
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

    invoice_action = InvoiceActionAPI()

    invoice_payment = InvoicePaymentsAPI()

    inventory_items = create_collection_api_class(
        InventoryItem, Template("accounts/${slug}/inventory_items")
    )()
    expenses = create_collection_api_class(
        Expense, Template("accounts/${slug}/expenses")
    )()

    class ExpenseActionAPI(ActionAPI[LockableAction]):
        base_path_template = Template("accounts/${slug}/invoices/${id}/fire.json")

    expense_action = ExpenseActionAPI()
    expense_payment = ExpensePaymentsAPI()

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

    def ensure_authenticated(self):
        self._ensure_token()
        self._set_authorization(self.user_agent, self._token)

    def _set_authorization(self, user_agent: str, jwt_token: JWTToken):
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Authorization": jwt_token.token_type + " " + jwt_token.access_token,
            }
        )

    def get(self, path: str, params: Optional[Mapping[str, str]] = None) -> APIResponse:
        url = f"{self.base_url}/{path}"
        response = self.session.get(url, params=params)
        if response.status_code == 404:
            raise NotFoundError(f"url={url}, reason={response.text}")
        else:
            response.raise_for_status()
        return APIResponse(response)

    def post(
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

    def patch(self, path: str, json_str: str) -> APIResponse:
        self.ensure_authenticated()
        response = self.session.patch(f"{self.base_url}/{path}", data=json_str)
        response.raise_for_status()
        return APIResponse(response)

    def delete(self, path: str):
        self.ensure_authenticated()
        response = self.session.delete(f"{self.base_url}/{path}")
        try:
            response.raise_for_status()
        except requests.HTTPError as err:
            new_err = FakturoidError(response.text)
            raise new_err from err
        return APIResponse(response)
