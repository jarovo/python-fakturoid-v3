from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from datetime import date, datetime, timedelta
from functools import wraps
import base64

import requests

from fakturoid.model_api import ModelApi
from fakturoid.models import Model, Account, Subject, Invoice, InventoryItem, Generator, Message, Expense, Unique
from fakturoid.paging import ModelList


__all__ = ['Fakturoid']


LINK_HEADER_PATTERN = re.compile(r'page=(\d+)[^>]*>; rel="last"')

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
        if 'link' in self._requests_response.headers:
            return extract_page_link(self._requests_response.headers['link'])
        else:
            return None


class Fakturoid:
    """Fakturoid API v3 - https://www.fakturoid.cz/api/v3"""
    slug: str
    client_id:str
    client_secret:str
    user_agent: str
    token:str
    renew_token_at: datetime = datetime.now()

    _models_api: dict[Model, ModelApi]

    baseurl = "https://app.fakturoid.cz/api/v3"
    
    def __init__(self, slug:str, client_id:str, client_secret: str, user_agent:str):
        self.slug = slug
        self.user_agent = user_agent
        self.client_id = client_id
        self.client_secret = client_secret
        
        self._models_api = {
            Account: AccountApi(self),
            Subject: SubjectsApi(self),
            Invoice: InvoicesApi(self),
            InventoryItem: InventoryApi(self),
            Expense: ExpensesApi(self),
            Generator: GeneratorsApi(self),
            Message: MessagesApi(self),
        }

        # Hack to expose full search on subjects as
        #
        #     fa.subjects.search()
        #
        # TODO Keep this API but make internal code redesing in future.
        def subjects_find(*args, **kwargs):
            return self._subjects_find(*args, **kwargs)

        def subjects_search(*args, **kwargs):
            return self._subjects_search(*args, **kwargs)
        self.subjects = subjects_find
        self.subjects.search = subjects_search

    def model_api(model_type=None):
        def wrap(fn):
            @wraps(fn)
            def wrapper(self: Fakturoid, *args, **kwargs):
                mt: Model = model_type or type(args[0])
                model_api = self._models_api.get(mt)
                if not model_api:
                    raise TypeError('model expected, got {0}'.format(mt.__name__))
                return fn(self, model_api, *args, **kwargs)
            return wrapper
        return wrap

    def oauth_token_client_credentials_flow(self):
        credentials = base64.urlsafe_b64encode(b':'.join((self.client_id.encode('utf-8'), self.client_secret.encode('utf-8'))))
        headers={'Accept': 'application/json',
                 'User-Agent': self.user_agent,
                 'Authorization': b'Basic ' + credentials}
        resp = requests.post(f'{self.baseurl}/oauth/token', headers=headers, data={"grant_type": "client_credentials"})
        resp.raise_for_status()
        self.token = resp.json()
        self.renew_token_at = datetime.now() + timedelta(seconds=self.token['expires_in'] / 2)

    def account(self):
        return self._models_api[Account].load()

    @model_api(Subject)
    def subject(self, mapi, id):
        return mapi.load(id)

    @model_api(Subject)
    def _subjects_find(self, mapi, *args, **kwargs):
        """call using fa.subjects()"""
        return mapi.find(*args, **kwargs)

    @model_api(Subject)
    def _subjects_search(self, mapi, *args, **kwargs):
        """call using fa.subjects.search()"""
        return mapi.search(*args, **kwargs)

    @model_api(Invoice)
    def invoice(self, mapi, id):
        return mapi.load(id)

    @model_api(Invoice)
    def invoices(self, mapi, *args, **kwargs):
        return mapi.find(*args, **kwargs)

    @model_api(Invoice)
    def fire_invoice_event(self, mapi, id, event, **kwargs):
        return mapi.fire(id, event, **kwargs)

    @model_api(Expense)
    def expense(self, mapi, id):
        return mapi.load(id)

    @model_api(Expense)
    def expenses(self, mapi, *args, **kwargs):
        return mapi.find(*args, **kwargs)

    @model_api(Expense)
    def fire_expense_event(self, mapi, id, event, **kwargs):
        return mapi.fire(id, event, **kwargs)

    @model_api(Generator)
    def generator(self, mapi, id):
        return mapi.load(id)

    @model_api(Generator)
    def generators(self, mapi, *args, **kwargs):
        return mapi.find(*args, **kwargs)

    @model_api(InventoryItem)
    def inventory_item(self, mapi, id):
        return mapi.load(id)

    @model_api(InventoryItem)
    def inventory_items(self, mapi, *args, **kwargs):
        return mapi.find(*args, **kwargs)

    @model_api()
    def save(self, mapi: CrudModelApi, obj, **kwargs):
        mapi.save(obj, **kwargs)

    @model_api()
    def delete(self, mapi, obj):
        """Call with loaded model or use new instance directly.
        s = fa.subject(1234)
        a.delete(s)

        fa.delete(Subject(id=1234))
        """
        mapi.delete(obj)

    def _make_request(self, method, success_status, endpoint, **kwargs):
        if datetime.now() > self.renew_token_at:
            self.oauth_token_client_credentials_flow()

        url = f'{self.baseurl}/accounts/{self.slug}/{endpoint}.json'
        headers = {'User-Agent': self.user_agent, 'Authorization': self.token['token_type'] + ' ' + self.token['access_token']}
        headers.update(kwargs.pop('headers', {}))
        r = getattr(requests, method)(url, headers=headers, **kwargs)
        r.raise_for_status()
    
        api_response = APIResponse(r)
        return api_response
    
    def _get(self, endpoint, params=None):
        return self._make_request('get', 200, endpoint, params=params)

    def _post(self, endpoint, data: Optional[Model]=None, params=None):
        if data:
            return self._make_request('post', 201, endpoint, headers={'Content-Type': 'application/json'}, data=data.model_dump_json(), params=params)
        else:
            return self._make_request('post', 201, endpoint, params=params)


    def _put(self, endpoint, data: Optional[Model] = None):
        if data:
            return self._make_request('put', 200, endpoint, headers={'Content-Type': 'application/json'}, data=data.model_dump_json())
        else:
            return self._make_request('put', 200, endpoint)

    def _delete(self, endpoint):
        return self._make_request('delete', 204, endpoint)


class CrudModelApi(ModelApi):
    def load(self, id: int):
        response = self.session._get('{0}/{1}'.format(self.endpoint, id))
        return self.from_response(response)

    def find(self, params={}, endpoint=None):
        response = self.session._get(endpoint or self.endpoint, params=params)
        return self.from_list_response(response)

    def save(self, obj: Model|Unique):
        if obj.id:
            result = self.session._put('{0}/{1}'.format(self.endpoint, obj.id), obj)
        else:
            result = self.session._post(self.endpoint, obj)
        return self.from_response(result)

    def delete(self, model: Unique):
        self.session._delete('{0}/{1}'.format(self.endpoint, model.id))


class AccountApi(ModelApi):
    model_type = Account
    endpoint = 'account'

    def load(self):
        response = self.session._get(self.endpoint)
        return self.from_response(response)


class SubjectsApi(CrudModelApi):
    model_type = Subject
    endpoint = 'subjects'

    def find(self, since=None, updated_since=None, custom_id=None):
        params = {}
        if since:
            if not isinstance(since, (datetime, date)):
                raise TypeError("'since' parameter must be date or datetime")
            params['since'] = since.isoformat()
        if updated_since:
            if not isinstance(updated_since, (datetime, date)):
                raise TypeError("'updated_since' parameter must be date or datetime")
            params['updated_since'] = updated_since.isoformat()
        if custom_id:
            params['custom_id'] = custom_id
        return super(SubjectsApi, self).find(params)

    def search(self, query: str):
        """Full text search as described in
        https://fakturoid.docs.apiary.io/#reference/subjects/subjects-collection-fulltext-search/fulltextove-vyhledavani-v-kontaktech
        """
        if not isinstance(query, str):
            raise TypeError("'query' parameter must be str")
        response = self.session._get('subjects/search'.format(self.endpoint), {'query': query})
        return self.from_list_response(response)


class InvoicesApi(CrudModelApi):
    """If number argument is given, returns single Invoice object (or None),
    otherwise iterable list of invoices are returned.
    """
    model_type = Invoice
    endpoint = 'invoices'

    STATUSES = ['open', 'sent', 'overdue', 'paid', 'cancelled']
    EVENTS = ['mark_as_sent', 'deliver', 'pay', 'pay_proforma', 'pay_partial_proforma', 'remove_payment', 'deliver_reminder', 'cancel', 'undo_cancel']
    EVENT_ARGS = {
        'pay': {'paid_at', 'paid_amount'}
    }

    def fire(self, invoice_id, event, **kwargs):
        if not isinstance(invoice_id, int):
            raise TypeError('invoice_id must be int')
        if event not in self.EVENTS:
            raise ValueError('invalid event, expected one of {0}'.format(', '.join(self.EVENTS)))

        allowed_args = self.EVENT_ARGS.get(event, set())
        if not set(kwargs.keys()).issubset(allowed_args):
            msg = "invalid event arguments, only {0} can be used with {1}".format(', '.join(allowed_args), event)
            raise ValueError(msg)

        params = {'event': event}
        params.update(kwargs)

        if 'paid_at' in params:
            if not isinstance(params['paid_at'], date):
                raise TypeError("'paid_at' argument must be date")
            params['paid_at'] = params['paid_at'].isoformat()

        self.session._post('invoices/{0}/fire'.format(invoice_id), params=params)

    def find(self, proforma=None, subject_id=None, since=None, updated_since=None, number=None, status=None, custom_id=None):
        params = {}
        if subject_id:
            if not isinstance(subject_id, int):
                raise TypeError("'subject_id' parameter must be int")
            params['subject_id'] = subject_id
        if since:
            if not isinstance(since, (datetime, date)):
                raise TypeError("'since' parameter must be date or datetime")
            params['since'] = since.isoformat()
        if updated_since:
            if not isinstance(updated_since, (datetime, date)):
                raise TypeError("'updated_since' parameter must be date or datetime")
            params['updated_since'] = updated_since.isoformat()
        if number:
            params['number'] = number
        if custom_id:
            params['custom_id'] = custom_id
        if status:
            if status not in self.STATUSES:
                raise ValueError('invalid invoice status, expected one of {0}'.format(', '.join(self.STATUSES)))
            params['status'] = status

        if proforma is None:
            endpoint = self.endpoint
        elif proforma:
            endpoint = '{0}/proforma'.format(self.endpoint)
        else:
            endpoint = '{0}/regular'.format(self.endpoint)

        return ModelList(self, endpoint, params)


class ExpensesApi(CrudModelApi):
    """If number argument is givent returms single Expense object (or None),
    otherwise iterable list of expenses are returned.
    """
    model_type = Expense
    endpoint = 'expenses'

    STATUSES = ['open', 'overdue', 'paid']
    EVENTS = ['remove_payment', 'deliver', 'pay', 'lock', 'unlock']
    EVENT_ARGS = {
        'pay': {'paid_on', 'paid_amount', 'variable_symbol', 'bank_account_id'}
    }

    def fire(self, expense_id: int, event, **kwargs):
        if not isinstance(expense_id, int):
            raise TypeError('expense_id must be int')
        if event not in self.EVENTS:
            raise ValueError('invalid event, expected one of {0}'.format(', '.join(self.EVENTS)))

        allowed_args = self.EVENT_ARGS.get(event, set())
        if not set(kwargs.keys()).issubset(allowed_args):
            msg = "invalid event arguments, only {0} can be used with {1}".format(', '.join(allowed_args), event)
            raise ValueError(msg)

        params = {'event': event}
        params.update(kwargs)

        if 'paid_on' in params:
            if not isinstance(params['paid_on'], date):
                raise TypeError("'paid_on' argument must be date")
            params['paid_on'] = params['paid_on'].isoformat()

        self.session._post('expenses/{0}/fire'.format(expense_id), params=params)

    def find(self, subject_id=None, since=None, updated_since=None, number=None, status=None, custom_id=None, variable_symbol=None):
        params = {}
        if subject_id:
            if not isinstance(subject_id, int):
                raise TypeError("'subject_id' parameter must be int")
            params['subject_id'] = subject_id
        if since:
            if not isinstance(since, (datetime, date)):
                raise TypeError("'since' parameter must be date or datetime")
            params['since'] = since.isoformat()
        if updated_since:
            if not isinstance(updated_since, (datetime, date)):
                raise TypeError("'updated_since' parameter must be date or datetime")
            params['updated_since'] = updated_since.isoformat()
        if number:
            params['number'] = number
        if custom_id:
            params['custom_id'] = custom_id
        if status:
            if status not in self.STATUSES:
                raise ValueError('invalid invoice status, expected one of {0}'.format(', '.join(self.STATUSES)))
            params['status'] = status
        if variable_symbol:
            params['variable_symbol'] = variable_symbol

        return ModelList(self, self.endpoint, params)


class GeneratorsApi(CrudModelApi):
    model_type = Generator
    endpoint = 'generators'

    def find(self, recurring=None, subject_id=None, since=None):
        params = {}
        if subject_id:
            if not isinstance(subject_id, int):
                raise TypeError("'subject_id' parameter must be int")
            params['subject_id'] = subject_id
        if since:
            if not isinstance(since, (datetime, date)):
                raise TypeError("'since' parameter must be date or datetime")
            params['since'] = since.isoformat()

        if recurring is None:
            endpoint = self.endpoint
        elif recurring:
            endpoint = '{0}/recurring'.format(self.endpoint)
        else:
            endpoint = '{0}/template'.format(self.endpoint)

        return super(GeneratorsApi, self).find(params, endpoint)


class InventoryApi(CrudModelApi):
    model_type = InventoryItem
    endpoint = 'inventory_items'

    def find(self, name=None, article_number=None, sku=None):
        params = {}
        if name:
            params['name'] = name

        return ModelList(self, self.endpoint, params)


class MessagesApi(ModelApi):
    model_type = Message
    endpoint = 'message'

    def save(self, model, **kwargs):
        invoice_id = kwargs.get('invoice_id')
        if not isinstance(invoice_id, int):
            raise TypeError("invoice_id must be int")
        result = self.session._post('invoices/{0}/{1}'.format(invoice_id, self.endpoint), model.get_fields())
        model.update(result['json'])
