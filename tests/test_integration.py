import pytest
from os import environ
from fakturoid import Fakturoid, Invoice, Subject, Line, NotFoundError
import uuid
from decimal import Decimal
from tests import conf
from unittest import TestCase


@pytest.fixture(scope="module")
def vcr_config():
    return {"decode_compressed_response": True, "filter_headers": ["authorization"]}


def login():
    fa = Fakturoid(
        conf.FAKTUROID_SLUG,
        conf.FAKTUROID_CLIENT_ID,
        conf.FAKTUROID_CLIENT_SECRET,
        conf.TESTS_OBJECTS_NAME_PREFIX,
    )
    return fa


def test_login():
    fa = login()
    account = fa.account.load()
    assert account
    assert account.name


def prefixed_name(counter=0):
    counter += 1
    return f"{conf.TESTS_OBJECTS_NAME_PREFIX}-{counter}"


@pytest.fixture
def fa_cli():
    return login()


@pytest.fixture
def subject(fa_cli: Fakturoid):
    subject = Subject(name=prefixed_name())
    created_subject = fa_cli.subjects.create(subject)
    assert created_subject.id
    yield created_subject
    fa_cli.subjects.delete(created_subject.id)
    with pytest.raises(NotFoundError):
        fa_cli.subjects.get(id=created_subject.id)


@pytest.mark.vcr
def test_crud_subject(fa_cli: Fakturoid):
    subject_name = prefixed_name()
    created_subject = fa_cli.subjects.save(Subject(name=subject_name))
    assert created_subject.name == subject_name

    new_subject_name = prefixed_name()
    created_subject.name = new_subject_name
    updated_subject = fa_cli.subjects.update(created_subject)
    assert updated_subject.name == new_subject_name

    subject_email = "test@gmail.com"
    updated_subject.email = subject_email
    again_updated_subject = fa_cli.subjects.update(updated_subject)
    assert again_updated_subject.name == new_subject_name
    assert again_updated_subject.email == subject_email

    found_items = list(fa_cli.subjects.find(email=subject_email))
    assert found_items
    assert all(found_item.email == subject_email for found_item in found_items)
    assert again_updated_subject.id
    fa_cli.subjects.delete(again_updated_subject.id)
    found_items = list(fa_cli.subjects.find(email=subject_email))
    assert not any(
        found_item.id == again_updated_subject.id for found_item in found_items
    )


@pytest.mark.vcr
def test_crud_invoice(fa_cli: Fakturoid, subject: Subject):
    assert subject.id
    created_invoice = fa_cli.invoices.save(
        Invoice(
            subject_id=subject.id,
            lines=[Line(name=prefixed_name(), unit_price=Decimal(1))],
        )
    )
    assert created_invoice.id
    by_id_invoice = fa_cli.invoices.get(id=created_invoice.id)
    by_number_invoice = list(fa_cli.invoices.find(number=created_invoice.number))[0]
    assert by_id_invoice == by_number_invoice
    assert by_id_invoice.id == by_number_invoice.id
    assert by_id_invoice.number == by_number_invoice.number

    created_invoice.lines.append(
        Line(name=prefixed_name(), quantity=Decimal(2), unit_price=Decimal(2))
    )
    updated_invoice = fa_cli.invoices.save(created_invoice)
    assert updated_invoice.lines[1].quantity == 2
    assert fa_cli.invoices.get(id=created_invoice.id).lines[1].quantity == 2
    fa_cli.invoices.delete(created_invoice.id)


class PaginationTest(TestCase):
    def setUp(self):
        self.fa_cli = login()
        self.TEST_ITEMS_COUNT = 60
        self.tag = f"{prefixed_name()}-test-subjects"
        self.test_subjects = [
            self.fa_cli.subjects.create(Subject(name=prefixed_name()))
            for i in range(self.TEST_ITEMS_COUNT)
        ]

    def tearDown(self):
        for test_item in self.test_subjects:
            self.fa_cli.subjects.delete(test_item.id)

    @pytest.mark.vcr
    def test_pagination(self):
        found_items = set(i.id for i in self.fa_cli.subjects.list())
        created_items = set(i.id for i in self.test_subjects)
        assert found_items == created_items
