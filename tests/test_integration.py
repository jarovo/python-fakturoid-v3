import pytest
from fakturoid import Fakturoid, Invoice, Subject, Line, NotFoundError
from fakturoid.api import JWTToken
from datetime import timedelta
from typing import Callable
from decimal import Decimal
from tests import defaults
from pytest import MonkeyPatch
from argparse import Namespace
from typing import List, Callable
from uuid import uuid4
from vcr.cassette import Cassette


@pytest.fixture
def fakturoid_factory(live_fakturoid_creds: Namespace):
    def factory():
        return Fakturoid(
            live_fakturoid_creds.FAKTUROID_SLUG,
            live_fakturoid_creds.FAKTUROID_CLIENT_ID,
            live_fakturoid_creds.FAKTUROID_CLIENT_SECRET,
            user_agent=defaults.TESTS_USER_AGENT,
        )

    return factory


@pytest.fixture
def fcli(
    monkeypatch: MonkeyPatch, vcr: Cassette, fakturoid_factory: Callable[[], Fakturoid]
):
    fa_cli = fakturoid_factory()
    monkeypatch.setattr(
        fa_cli,
        "_token",
        JWTToken(
            token_type="Basic",
            access_token="DUMMY_VALUE",
            expires_in=timedelta(seconds=7200),
        ),
    )
    assert not fa_cli._token.is_expired
    return fa_cli


def test_login(fakturoid_factory: Callable[[], Fakturoid]):
    fa_cli = fakturoid_factory()
    account = fa_cli.account.load()
    assert account
    assert account.name


@pytest.fixture
def name_factory(request: pytest.FixtureRequest):
    names: List[str] = []

    def factory():
        name = f"test-item-{request.function.__name__}-{uuid4()}"
        names.append(name)
        return name

    yield factory

    # Place for chcecking do we have any leftovers in the system


@pytest.fixture
def subject(
    fakturoid_factory: Callable[[], Fakturoid], name_factory: Callable[[], str]
):
    subject = Subject(name=name_factory())
    fcli = fakturoid_factory()
    created_subject = fcli.subjects.create(subject)
    assert created_subject.id
    yield created_subject
    fcli.subjects.delete(created_subject.id)
    with pytest.raises(NotFoundError):
        fcli.subjects.get(id=created_subject.id)


def test_crud_subject(
    fakturoid_factory: Callable[[], Fakturoid], name_factory: Callable[[], str]
):
    subject_name = name_factory()
    fcli = fakturoid_factory()
    created_subject = fcli.subjects.save(Subject(name=subject_name))
    assert created_subject.name == subject_name

    new_subject_name = name_factory()
    created_subject.name = new_subject_name
    updated_subject = fcli.subjects.update(created_subject)
    assert updated_subject.name == new_subject_name

    subject_email = "test@gmail.com"
    updated_subject.email = subject_email
    again_updated_subject = fcli.subjects.update(updated_subject)
    assert again_updated_subject.name == new_subject_name
    assert again_updated_subject.email == subject_email

    found_items = list(fcli.subjects.find(email=subject_email))
    assert found_items
    assert all(found_item.email == subject_email for found_item in found_items)
    assert again_updated_subject.id
    fcli.subjects.delete(again_updated_subject.id)
    found_items = list(fcli.subjects.find(email=subject_email))
    assert not any(
        found_item.id == again_updated_subject.id for found_item in found_items
    )


def test_crud_invoice(
    fakturoid_factory: Callable[[], Fakturoid],
    subject: Subject,
    name_factory: Callable[[], str],
):
    fcli = fakturoid_factory()
    assert subject.id
    created_invoice = fcli.invoices.save(
        Invoice(
            subject_id=subject.id,
            lines=[Line(name=name_factory(), unit_price=Decimal(1))],
        )
    )
    assert created_invoice.id
    by_id_invoice = fcli.invoices.get(id=created_invoice.id)
    by_number_invoice = list(fcli.invoices.find(number=created_invoice.number))[0]
    assert by_id_invoice == by_number_invoice
    assert by_id_invoice.id == by_number_invoice.id
    assert by_id_invoice.number == by_number_invoice.number

    created_invoice.lines.append(
        Line(name=name_factory(), quantity=Decimal(2), unit_price=Decimal(2))
    )
    updated_invoice = fcli.invoices.save(created_invoice)
    assert updated_invoice.lines[1].quantity == 2
    assert fcli.invoices.get(id=created_invoice.id).lines[1].quantity == 2
    fcli.invoices.delete(created_invoice.id)


@pytest.fixture
def pagination_setup(
    fakturoid_factory: Callable[[], Fakturoid], name_factory: Callable[[], str]
):
    TEST_ITEMS_COUNT = 60
    fcli = fakturoid_factory()

    test_subjects = [
        fcli.subjects.create(Subject(name=name_factory()))
        for i in range(TEST_ITEMS_COUNT)
    ]

    yield fcli, test_subjects

    for test_item in test_subjects:
        assert test_item.id
        fcli.subjects.delete(test_item.id)


def test_pagination(pagination_setup: tuple[Fakturoid, list[Subject]]):
    fa_cli, test_subjects = pagination_setup
    found_items = set(i.id for i in fa_cli.subjects.list())
    created_items = set(i.id for i in test_subjects)
    assert created_items <= found_items
