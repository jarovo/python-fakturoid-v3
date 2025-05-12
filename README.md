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

```python fixture:isolation
from fakturoid import Fakturoid

fa = Fakturoid('yourslug', 'CLIENT_ID', 'CLIENT_SECRET', 'YourApp')
```

```python continuation
from fakturoid import Fakturoid, Invoice, Line
from datetime import date

fa = Fakturoid('yourslug', 'CLIENT_ID', 'CLIENT_SECRET', 'YourApp')

# Print 25 regular invoices in year 2013:
for invoice in fa.invoices(proforma=False, since=date(2013, 1, 1))[:25]:
    print(invoice.number, invoice.total)

# Delete subject with id 27:
subject = fa.subject(27)
fa.delete(subject)

# And finally create new invoice:
invoice = Invoice(
    subject_id=28,
    number='2013-0108',
    due=10,
    issued_on=date(2012, 3, 30),
    taxable_fulfillment_due=date(2012, 3, 30),
    lines=[
        # use Decimal or string for floating values
        Line(name='Hard work', unit_name='h', unit_price=40000, vat_rate=20),
        Line(
            name='Soft material',
            quantity=12,
            unit_name='ks',
            unit_price="4.60",
            vat_rate=20,
        ),
    ],
)
fa.save(invoice)

print(invoice.due_on)
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
