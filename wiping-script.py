import fakturoid.nounapi as fakturoid
from os import environ
from fakturoid.models import InvoiceAction
from dotenv import load_dotenv
import asyncio


def confirm_wipening_allowed():
    fakturoid_slug = environ["FAKTUROID_SLUG"]
    assert (
        environ.get("ALLOW_WIPENING") == fakturoid_slug
    ), f"ALLOW_WIPENING needs to be defined to allow wipening {fakturoid_slug}"


load_dotenv()

# This script is used to wipe all invoices and subjects from the Fakturoid account.
# It should be used with caution, as it will delete all data.
# It is intended for use in a development or testing environment only.
# It is not intended for use in a production environment.
# It is recommended to run this script only when you are sure that you want to delete all data.
# Dont proceed without safety check.
confirm_wipening_allowed()
fa = fakturoid.Fakturoid()


async def delete_invoice(invoice: fakturoid.Invoice, fa: fakturoid.Fakturoid):
    # This function deletes a single invoice from the Fakturoid account.
    assert invoice.id
    print("Deleting invoice:", str(invoice.id))
    if invoice.locked_at:
        await invoice.a_fire_action(InvoiceAction.Unlock, fa)

    await invoice.a_delete(fa)


async def delete_invoices(fa: fakturoid.Fakturoid):
    # This function deletes all invoices from the Fakturoid account.
    async with asyncio.TaskGroup() as tg:
        invoices_to_delete = [
            invoice async for invoice in fakturoid.Invoice.a_index(fa)
        ]
        print(f"Deleting {len(invoices_to_delete)} subjects")
        for invoice in invoices_to_delete:
            tg.create_task(delete_invoice(invoice, fa))


async def delete_subject(subject: fakturoid.Subject, fa: fakturoid.Fakturoid):
    # This function deletes a single subject from the Fakturoid account.
    assert subject.id
    print("Deleting subject:", str(subject.id))
    await subject.a_delete(fa)


async def delete_subjects(fa: fakturoid.Fakturoid):
    # This function deletes all subjects from the Fakturoid account.
    async with asyncio.TaskGroup() as tg:
        subjects_to_delete = [
            subject async for subject in fakturoid.Subject.a_index(fa)
        ]
        print(f"Deleting {len(subjects_to_delete)} subjects")
        for subject in subjects_to_delete:
            tg.create_task(delete_subject(subject, fa))


async def main():
    load_dotenv()
    confirm_wipening_allowed()
    async with fakturoid.Fakturoid() as fa:
        await delete_invoices(fa)
        await delete_subjects(fa)


if __name__ == "__main__":
    asyncio.run(main())
