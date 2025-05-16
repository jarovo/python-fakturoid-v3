# fakturoid.cz Python API

The Python interface to online accounting service [Fakturoid](http://fakturoid.cz/) using Fakturoid's v3 api.

This library is developed and maintained by Jaroslav Henner ([jaroslav.henner@gmail.com](mailto:jaroslav.henner@gmail.com)).


## Installation

Install from PyPI

    pip install fakturoid-v3

or alternatively install development version directly from github

    pip install -e git+git://github.com/jarovo/python-fakturoid-v3#egg=fakturoid-v3


Tested with Python >= 3.9


## Quickstart

Generate the Client ID and Client Secret from your Fakturoid user screen: Settings → User account.

### Create subject and  invoice
```python
>>> from fakturoid import Fakturoid, Invoice, Line, Subject
>>> from datetime import date
>>> from os import getenv
>>> fa = Fakturoid(getenv('FAKTUROID_SLUG'), getenv('FAKTUROID_CLIENT_ID'), getenv('FAKTUROID_CLIENT_SECRET'), 'YourApp')
>>> subject = Subject(name="foo", tags=("test",))
>>> saved_subject = fa.subjects.save(subject)
>>> line = Line(name='Hard work', unit_name='h', unit_price=40000, vat_rate=20)
>>> invoice = Invoice(subject_id=saved_subject.id, due=10, issued_on=date(2012, 3, 30), tags=("test",), lines=[line])

>>> saved_invoice = fa.invoices.save(invoice)
>>> print(saved_invoice.due_on)
2012-04-09

```


```python
>>> test_invoices = fa.invoices.find(tag="test")
>>> test_subjects = fa.subjects.find(tag="test")
>>> for invoice in test_invoices:
...     fa.invoices.delete(saved_invoice.id)
>>> for subject in test_subjects:
...     fa.subjects.delete(subject.id)

```

## API

<code>Fakturoid.<b>account()</b></code>

Returns `Account` instance. Account is readonly and can't be updated by API.

<code>Fakturoid.<b>subject(id)</b></code>

Returns `Subject` instance.

<code>Fakturoid.<b>subjects(since=None, updated_since=None, custom_id=None)</b></code>

Loads all subjects filtered by args.
If since (`date` or `datetime`) parameter is passed, returns only subjects created since given date.

<code>Fakturoid.<b>subjects.search("General Motors")</b></code>

Perform full text search on subjects

<code>Fakturoid.<b>invoce(id)</b></code>

Returns `Invoice` instance.

<code>Fakturoid.<b>invoices(proforma=None, subject_id=None, since=None, updated_since=None, number=None, status=None, custom_id=None)</b></code>

Use `proforma=False`/`True` parameter to load regular or proforma invoices only.

Returns list of invoices. Invoices are lazily loaded according to slicing.
```python
from fakturoid import Fakturoid

fa = Fakturoid('yourslug', 'CLIENT_ID', 'CLIENT_SECRET', 'YourApp')
fa.invoices(status='paid')[:100]  # loads 100 paid invoices
fa.invoices()[
    -1
]  # loads first issued invoice (invoices are ordered from latest to first)
```

<code>Fakturoid.<b>fire_invoice_event(id, event, **args)</b></code>

Fires basic events on invoice. All events are described in [Fakturoid API docs](https://www.fakturoid.cz/api/v3/invoices#invoice-actions).

Pay event can accept optional arguments `paid_at` and `paid_amount`
```python
from fakturoid import Fakturoid
from datetime import date

fa = Fakturoid('yourslug', 'CLIENT_ID', 'CLIENT_SECRET', 'YourApp')
fa.fire_invoice_event(11331402, 'pay', paid_at=date(2018, 11, 17), paid_amount=2000)
```

<code>Fakturoid.<b>generator(id)</b></code>

Returns `Generator` instance.

<code>Fakturoid.<b>generators(recurring=None, subject_id=None, since=None)</b></code>

Use `recurring=False`/`True` parameter to load recurring or simple templates only.

<code>Fakturoid.<b>save(model)</b></code>

Create or modify `Subject`, `Invoice` or `Generator`.

To modify or delete invoice lines simply edit `lines`

```python
from fakturoid import Fakturoid

fa = Fakturoid('yourslug', 'CLIENT_ID', 'CLIENT_SECRET', 'YourApp')
invoice = fa.invoices(number='2014-0002')[0]
invoice.lines[0].unit_price = 5000  # edit first item
del invoice.lines[-1]  # delete last item
fa.save(invoice)
```

<code>Fakturoid.<b>delete(model)</b></code><br>

Delete `Subject`, `Invoice` or `Generator`.

```python
from fakturoid import Fakturoid, Subject

fa = Fakturoid('yourslug', 'CLIENT_ID', 'CLIENT_SECRET', 'YourApp')
subj = fa.subject(1234)
fa.delete(subj)  # delete subject

# or alternativelly delete is possible without object loading
fa.delete(Subject(id=1234))
```

### Models

All models fields are named same as  [Fakturoid API](https://www.fakturoid.cz/api/v3).

Values are mapped to corresponding `int`, `decimal.Decimal`, `datetime.date` and `datetime.datetime` types.
