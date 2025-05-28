# The typing enabled fakturoid.cz Python API client.

The Python interface to online accounting service [Fakturoid](http://fakturoid.cz/) using Fakturoid's v3 api.

This library is developed and maintained by Jaroslav Henner ([jaroslav.henner@gmail.com](mailto:jaroslav.henner@gmail.com)).


## Installation

Install from PyPI

    pip install fakturoid-v3

or alternatively install development version directly from github

    pip install -e git+git://github.com/jarovo/python-fakturoid-v3#egg=fakturoid-v3


Tested with Python >= 3.9


## Quickstart

Generate the Client ID and Client Secret from your Fakturoid user screen: Settings → User account and set environment variables:

```shell
# Check the definitions in the file
$ cat .env
FAKTUROID_SLUG = ******
FAKTUROID_CLIENT_ID = *****
FAKTUROID_CLIENT_SECRET = ******

# Load the env file
$ . .env
```

### Create subject and  invoice
Now you can start Python and start using Fakturoid.
```python
>>> from fakturoid import Fakturoid, Invoice, Line, Subject
>>> from datetime import date
>>> # fa = Fakturoid('yourslug', 'CLIENT_ID', 'CLIENT_SECRET')
>>> # or
>>> fa = Fakturoid.from_env()

```

Then we can create a first subject.
```python
>>> subject = Subject(name="foo", tags=("test",))
>>> saved_subject = fa.subjects.save(subject)

```

And create a line and invoice for that subject.

```python
>>> line = Line(name='Hard work', unit_name='h', unit_price=40000, vat_rate=20)
>>> invoice = Invoice(subject_id=saved_subject.id, due=10, issued_on=date(2012, 3, 30), tags=("test",), lines=[line])
>>> first_saved_invoice = fa.invoices.save(invoice)
>>> print(first_saved_invoice.due_on)
2012-04-09

```

We can find the invoices from that date.
```python
>>> assert 1 == len(list(fa.invoices.find(subject_id=saved_subject.id)))
>>> second_saved_invoice = fa.invoices.save(invoice)
>>> found_invoices = list(fa.invoices.find(subject_id=saved_subject.id))
>>> assert 2 == len(list(invoice for invoice in found_invoices))

```


Fires basic action on invoice. All actions are described in [Fakturoid API docs](https://www.fakturoid.cz/api/v3/invoices#invoice-actions).

```python
>>> from fakturoid.models import InvoiceAction
>>> fa.invoice_action.fire(first_saved_invoice.id, InvoiceAction.Lock)
>>> first_saved_invoice = fa.invoices.get(first_saved_invoice.id)
>>> assert first_saved_invoice.locked_at is not None

```

We cannot delete the locked invoice:
```python
>>> from fakturoid.api import FakturoidError
>>> try:
...     fa.invoices.delete(first_saved_invoice.id)
... except FakturoidError as e:
...     pass
... else:
...     assert False, "This codepath should't get executed."

```

We can delete what we created (after unlocking the locked invoice.)

```python
>>> fa.invoice_action.fire(first_saved_invoice.id, InvoiceAction.Unlock)
>>> test_invoices = list(fa.invoices.search(tags=("test",)))
>>> for invoice in test_invoices:
...     fa.invoices.delete(invoice.id)
>>> fa.subjects.delete(saved_subject.id)
