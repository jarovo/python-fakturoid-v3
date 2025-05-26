import freezegun
import unittest
from datetime import date
from unittest.mock import patch, MagicMock
from decimal import Decimal

from fakturoid.api import Fakturoid
from fakturoid.models import InvoiceAction, LockableAction

from tests.mock import response, FakeResponse
from pytest import fixture
from typing import cast
from datetime import datetime


@fixture
def frozen_time():
    with freezegun.freeze_time("2025-05-01 18:50:00") as frozen_time:
        yield frozen_time


def test_oauth_credentials_flow(frozen_time: freezegun.api.FrozenDateTimeFactory):
    fa = Fakturoid(
        "unit_tests_slug",
        "CLIENT_ID",
        "CLIENT_SECRET",
        "python-fakturoid-v3-tests (https://github.com/jarovo/python-fakturoid-v3)",
    )
    with (
        patch.object(
            fa.session, "get", return_value=response("invoice_9.json")
        ) as get_mock,
        patch("requests.post", return_value=response("token.json")) as post_mock,
    ):
        get_mock = cast(MagicMock, get_mock)
        post_mock = cast(MagicMock, post_mock)

        assert fa._token.is_expired == True
        assert fa._token.to_be_renewed == True
        fa._ensure_token()
        assert post_mock.call_count == 1

        fa.invoices.get(1)
        assert get_mock.call_count == 1

        assert fa.invoices.get(id=1)
        assert post_mock.call_count == 1
        assert get_mock.call_count == 2

        frozen_time.move_to("2025-05-01 19:50:00")
        # The token should be renewed
        assert fa._token.to_be_renewed == True
        assert fa._token.is_expired == False
        assert fa.invoices.get(1)
        assert post_mock.call_count == 2
        assert get_mock.call_count == 3


class FakturoidTestCase(unittest.TestCase):
    @patch("requests.post", return_value=response("token.json"))
    def setUp(self, post_mock: MagicMock):
        self.fa = Fakturoid(
            "myslug",
            "CLIENT_ID",
            "CLIENT_SECRET",
            "python-fakturoid-v3-tests (https://github.com/jarovo/python-fakturoid-v3)",
        )

        self.fa._oauth_token_client_credentials_flow()
        return super().setUp()


class AccountTestCase(FakturoidTestCase):
    def test_load(self):
        with patch.object(
            self.fa.session, "get", return_value=response("account.json")
        ) as mock:
            account = self.fa.account.load()

        mock.assert_called_once()
        self.assertEqual(
            "https://app.fakturoid.cz/api/v3/accounts/myslug/account.json",
            mock.call_args[0][0],
        )
        self.assertEqual("Alexandr Hejsek", account.name)
        self.assertEqual("testdph@test.cz", account.invoice_email)


class SubjectTestCase(FakturoidTestCase):
    def test_load(self):
        with patch.object(
            self.fa.session, "get", return_value=response("subject_28.json")
        ) as mock:
            subject = self.fa.subjects.get(28)

        mock.assert_called_once()
        self.assertEqual(
            "https://app.fakturoid.cz/api/v3/accounts/myslug/subjects/28.json",
            mock.call_args[0][0],
        )
        self.assertEqual(28, subject.id)
        self.assertEqual("47123737", subject.registration_no)
        self.assertEqual(
            "2012-06-02T09:34:47+02:00", cast(datetime, subject.updated_at).isoformat()
        )

    def test_find(self):
        with patch.object(
            self.fa.session, "get", return_value=response("subjects.json")
        ) as mock:
            subjects = self.fa.subjects.list()
        mock.assert_called_once()
        self.assertEqual(
            "https://app.fakturoid.cz/api/v3/accounts/myslug/subjects.json",
            mock.call_args[0][0],
        )
        self.assertEqual(2, len(subjects))
        self.assertEqual("Apple Czech s.r.o.", subjects[0].name)


class InvoiceTestCase(FakturoidTestCase):
    def test_get(self):
        with patch.object(
            self.fa.session, "get", return_value=response("invoice_9.json")
        ) as mock:
            invoice = self.fa.invoices.get(9)
        mock.assert_called_once()
        self.assertEqual(
            "https://app.fakturoid.cz/api/v3/accounts/myslug/invoices/9.json",
            mock.call_args[0][0],
        )
        self.assertEqual("2012-0004", invoice.number)
        self.assertEqual("PC", invoice.lines[0].name)
        self.assertEqual("Notebook", invoice.lines[1].name)

    def test_fire(self):
        with patch.object(
            self.fa.session, "post", return_value=FakeResponse("")
        ) as mock:
            self.fa.invoice_event.fire(9, InvoiceAction.Cancel)

        mock.assert_called_once_with(
            "https://app.fakturoid.cz/api/v3/accounts/myslug/invoices/9/fire.json",
            data=None,
            params={"event": "cancel"},
        )

    def test_save_update_line(self):
        get_response_text = '{"id":1,"subject_id":1,"number":"2025-01-01","lines":[{"id":1000,"name":"Nails","quantity":"10","unit_name":"ks","unit_price":"1.2"}]}'
        new_response_text = '{"id":1,"subject_id":1,"number":"2025-01-01","lines":[{"id":1000,"name":"Wire","unit_price":"13.2","unit_name":"meter","quantity":"10"}]}'

        with patch.object(
            self.fa.session, "get", return_value=FakeResponse(get_response_text)
        ) as get_mock:
            invoice = self.fa.invoices.get(1)
        get_mock.assert_called_once_with(
            "https://app.fakturoid.cz/api/v3/accounts/myslug/invoices/1.json",
            params=None,
        )

        invoice.lines[0].name = "Wire"
        invoice.lines[0].unit_name = "meter"
        invoice.lines[0].unit_price = Decimal("13.2")

        with patch.object(
            self.fa.session, "patch", return_value=FakeResponse(new_response_text)
        ) as put_mock:
            self.fa.invoices.save(invoice)
        put_mock.assert_called_once_with(
            "https://app.fakturoid.cz/api/v3/accounts/myslug/invoices/1.json",
            data=new_response_text,
        )

    def test_list(self):
        with patch.object(
            self.fa.session, "get", return_value=response("invoices.json")
        ) as mock:
            self.fa.invoices.list()[:10]
        mock.assert_called_once_with(
            "https://app.fakturoid.cz/api/v3/accounts/myslug/invoices.json",
            params={"page": "1"},
        )
        self.assertEqual(
            "https://app.fakturoid.cz/api/v3/accounts/myslug/invoices.json",
            mock.call_args[0][0],
        )
        # TODO paging test


class InventoryTestCase(FakturoidTestCase):
    def test_find(self):
        with patch.object(
            self.fa.session, "get", return_value=response("inventory_items.json")
        ) as mock:
            inventory_items = self.fa.inventory_items.list()
        mock.assert_called_once()
        self.assertEqual(
            "https://app.fakturoid.cz/api/v3/accounts/myslug/inventory_items.json",
            mock.call_args[0][0],
        )
        self.assertEqual(4, len(inventory_items))

    def test_get(self):
        with patch.object(
            self.fa.session, "get", return_value=response("inventory_items_203140.json")
        ) as mock:
            inventory_item = self.fa.inventory_items.get(203140)
        mock.assert_called_once()
        self.assertEqual(
            "https://app.fakturoid.cz/api/v3/accounts/myslug/inventory_items/203140.json",
            mock.call_args[0][0],
        )
        self.assertEqual(203140, inventory_item.id)


class GeneratorTestCase(FakturoidTestCase):
    def test_load(self):
        with patch.object(
            self.fa.session, "get", return_value=response("generator_4.json")
        ) as mock:
            g = self.fa.generators.get(4)

        self.assertEqual(
            "https://app.fakturoid.cz/api/v3/accounts/myslug/generators/4.json",
            mock.call_args[0][0],
        )
        self.assertEqual("Podpora", g.name)

    def test_find(self):
        with patch.object(
            self.fa.session, "get", return_value=response("generators.json")
        ) as mock:
            generators = self.fa.generators.list()

        self.assertEqual(
            "https://app.fakturoid.cz/api/v3/accounts/myslug/generators.json",
            mock.call_args[0][0],
        )
        self.assertEqual(2, len(generators))


if __name__ == "__main__":
    unittest.main()
