import fakturoid
from os import environ
from fakturoid.models import InvoiceAction


def confirm_wipening_allowed():
    fakturoid_slug = environ["FAKTUROID_SLUG"]
    assert (
        environ.get("ALLOW_WIPENING") == fakturoid_slug
    ), f"ALLOW_WIPENING needs to be defined to allow wipening {fakturoid_slug}"


# Dont proceed without safety check.
confirm_wipening_allowed()
fa = fakturoid.Fakturoid.from_env()


def delete_invoices():
    invoices_to_delete = list(fa.invoices.list())
    print(f"Deleting {invoices_to_delete}")
    for invoice in invoices_to_delete:
        if invoice.locked_at:
            fa.invoice_action.fire(invoice.id, InvoiceAction.Unlock)
        fa.invoices.delete(invoice.id)


def delete_subjects():
    subjects_to_delete = list(fa.subjects.list())
    print(f"Deleting {subjects_to_delete}")
    for subject in subjects_to_delete:
        fa.subjects.delete(subject.id)


delete_invoices()
delete_subjects()
