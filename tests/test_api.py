from __future__ import absolute_import

import freezegun
import json
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch
from decimal import Decimal

from fakturoid import Fakturoid, Invoice, Line

from tests.mock import response, FakeResponse


class FakturoidTestCase(unittest.TestCase):

    @patch('requests.post', return_value=response("token.json"))
    def setUp(self, mock):
        self.fa = Fakturoid('myslug', 'CLIENT_ID', 'CLIENT_SECRET', 'python-fakturoid-v3-tests (https://github.com/jarovo/python-fakturoid-v3)')
        self.fa.oauth_token_client_credentials_flow()


class OAuthTestCase(FakturoidTestCase):
    new_token_request_time = datetime.now()
    past_token_request_time = new_token_request_time - timedelta(seconds=7200)

    @patch('requests.get', return_value=response('invoices.json'))
    @patch('requests.post', return_value=response('token.json'))
    def test_oauth_credentials_flow(self, post_mock, get_mock):
        with freezegun.freeze_time(self.past_token_request_time) as freezer:
            self.fa.oauth_token_client_credentials_flow()
            assert self.fa.invoices()
            assert post_mock.call_count == 1
            assert get_mock.call_count == 1

            assert self.fa.invoices()
            assert post_mock.call_count == 1
            assert get_mock.call_count == 2
        
        with freezegun.freeze_time(self.new_token_request_time) as freezer:
            assert self.fa.renew_token_at < datetime.now()
            assert self.fa.invoices()
            assert post_mock.call_count == 2
            assert get_mock.call_count == 3


class AccountTestCase(FakturoidTestCase):
    @patch('requests.get', return_value=response('account.json'))
    def test_load(self, mock):
        account = self.fa.account()

        mock.assert_called_once()
        self.assertEqual('https://app.fakturoid.cz/api/v3/accounts/myslug/account.json', mock.call_args[0][0])
        self.assertEqual("Alexandr Hejsek", account.name)
        self.assertEqual("testdph@test.cz", account.invoice_email)


class SubjectTestCase(FakturoidTestCase):

    @patch('requests.get', return_value=response('subject_28.json'))
    def test_load(self, mock):
        subject = self.fa.subject(28)

        mock.assert_called_once()
        self.assertEqual('https://app.fakturoid.cz/api/v3/accounts/myslug/subjects/28.json', mock.call_args[0][0])
        self.assertEqual(28, subject.id)
        self.assertEqual('47123737', subject.registration_no)
        self.assertEqual('2012-06-02T09:34:47+02:00', subject.updated_at.isoformat())

    @patch('requests.get', return_value=response('subjects.json'))
    def test_find(self, mock):
        subjects = self.fa.subjects()

        mock.assert_called_once()
        self.assertEqual('https://app.fakturoid.cz/api/v3/accounts/myslug/subjects.json', mock.call_args[0][0])
        self.assertEqual(2, len(subjects))
        self.assertEqual('Apple Czech s.r.o.', subjects[0].name)


class InvoiceTestCase(FakturoidTestCase):

    @patch('requests.get', return_value=response('invoice_9.json'))
    def test_load(self, mock):
        invoice = self.fa.invoice(9)
        mock.assert_called_once()
        self.assertEqual('https://app.fakturoid.cz/api/v3/accounts/myslug/invoices/9.json', mock.call_args[0][0])
        self.assertEqual('2012-0004', invoice.number)
        self.assertEqual('PC', invoice.lines[0].name)
        self.assertEqual('Notebook', invoice.lines[1].name)

    @patch('requests.post', return_value=FakeResponse(''))
    def test_fire(self, mock):
        self.fa.fire_invoice_event(9, 'pay')

        mock.assert_called_once_with('https://app.fakturoid.cz/api/v3/accounts/myslug/invoices/9/fire.json',
                                     headers={'User-Agent': self.fa.user_agent,
                                              'Authorization': 'Bearer 63cfcf07492268ab0e3c58e9fa48096dc5bf0a9b7bbd2f6f45e0a6fa9fc2074a4523af3538f0df5c'},
                                     params={'event': 'pay'})

    get_response_text = '{"id":1,"lines":[{"id":1000,"name":"Nails","quantity":"10","unit_name":"ks","unit_price":"1.2"}],"number":"2025-01-01"}'
    new_response_text = '{"id":1,"lines":[{"id":1000,"name":"Wire","quantity":"10","unit_name":"meter","unit_price":"13.2"}],"number":"2025-01-01"}'
    @patch('requests.get', return_value=FakeResponse(get_response_text))
    @patch('requests.put', return_value=FakeResponse(new_response_text))
    def test_save_update_line(self, put_mock, get_mock):
        invoice = self.fa.invoice(1)
        invoice.lines[0].name = "Wire"
        invoice.lines[0].unit_name = "meter"
        invoice.lines[0].unit_price = Decimal("13.2")
        self.fa.save(invoice)

        get_mock.assert_called_once_with('https://app.fakturoid.cz/api/v3/accounts/myslug/invoices/1.json',
                                     headers={'User-Agent': self.fa.user_agent,
                                              'Authorization': 'Bearer 63cfcf07492268ab0e3c58e9fa48096dc5bf0a9b7bbd2f6f45e0a6fa9fc2074a4523af3538f0df5c',
                                     },
                                     params=None)

        put_mock.assert_called_once_with('https://app.fakturoid.cz/api/v3/accounts/myslug/invoices/1.json',
                                     headers={'User-Agent': self.fa.user_agent,
                                              'Authorization': 'Bearer 63cfcf07492268ab0e3c58e9fa48096dc5bf0a9b7bbd2f6f45e0a6fa9fc2074a4523af3538f0df5c',
                                              'Content-Type': 'application/json'},
                                     data=self.new_response_text)


    @patch('requests.post', return_value=FakeResponse(''))
    def test_fire_with_args(self, mock):
        self.fa.fire_invoice_event(9, 'pay', paid_at=date(2018, 11, 19))

        mock.assert_called_once_with('https://app.fakturoid.cz/api/v3/accounts/myslug/invoices/9/fire.json',
                                     headers={'User-Agent': self.fa.user_agent,
                                              'Authorization': 'Bearer 63cfcf07492268ab0e3c58e9fa48096dc5bf0a9b7bbd2f6f45e0a6fa9fc2074a4523af3538f0df5c'},
                                     params={'event': 'pay', 'paid_at': '2018-11-19'})

    @patch('requests.get', return_value=response('invoices.json'))
    def test_find(self, mock):
        self.fa.invoices()[:10]
        mock.assert_called_once_with('https://app.fakturoid.cz/api/v3/accounts/myslug/invoices.json',
                                     headers={'User-Agent': self.fa.user_agent,
                                              'Authorization': 'Bearer 63cfcf07492268ab0e3c58e9fa48096dc5bf0a9b7bbd2f6f45e0a6fa9fc2074a4523af3538f0df5c'},
                                     params={'page': 1})
        self.assertEqual('https://app.fakturoid.cz/api/v3/accounts/myslug/invoices.json', mock.call_args[0][0])
        # TODO paging test


class InventoryTestCase(FakturoidTestCase):

    @patch('requests.get', return_value=response('inventory_items.json'))
    def test_find(self, mock):
        inventory_items = list(self.fa.inventory_items())
        mock.assert_called_once()
        self.assertEqual('https://app.fakturoid.cz/api/v3/accounts/myslug/inventory_items.json', mock.call_args[0][0])
        self.assertEqual(4, len(inventory_items))

    @patch('requests.get', return_value=response('inventory_items_203140.json'))
    def test_load(self, mock):
        inventory_item = self.fa.inventory_item(203140)
        mock.assert_called_once()
        self.assertEqual('https://app.fakturoid.cz/api/v3/accounts/myslug/inventory_items/203140.json', mock.call_args[0][0])
        self.assertEqual(203140, inventory_item.id)


class GeneratorTestCase(FakturoidTestCase):

    @patch('requests.get', return_value=response('generator_4.json'))
    def test_load(self, mock):
        g = self.fa.generator(4)

        self.assertEqual('https://app.fakturoid.cz/api/v3/accounts/myslug/generators/4.json', mock.call_args[0][0])
        self.assertEqual('Podpora', g.name)

    @patch('requests.get', return_value=response('generators.json'))
    def test_find(self, mock):
        generators = self.fa.generators()

        self.assertEqual('https://app.fakturoid.cz/api/v3/accounts/myslug/generators.json', mock.call_args[0][0])
        self.assertEqual(2, len(generators))


if __name__ == '__main__':
    unittest.main()
