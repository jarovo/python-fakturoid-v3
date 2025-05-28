# These are the remaining bits from python-fakturoid to be covered and tested in python-fakturoid-v3

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
