import dataclasses
from datetime import datetime
from typing import Optional
from decimal import Decimal
from dateutil.parser import parse
from pydantic.dataclasses import dataclass
from pydantic import Field, BaseModel, EmailStr


__all__ = ['Account', 'Subject', 'Line', 'Invoice', 'Generator',
           'Message', 'Expense']


class Model(BaseModel):
    """Base class for all Fakturoid model objects"""

    def __unicode__(self):
        return "<{0}:{1}>".format(self.__class__.__name__, self.id)


class Unique(BaseModel):
    id: Optional[int] = Field(export=False)


class Account(Model):
    """See http://docs.fakturoid.apiary.io/ for complete field reference."""
    name: str
    invoice_email: EmailStr
    registration_no: Optional[str]

    class Meta:
        decimal = []


class Subject(Model, Unique):
    """See http://docs.fakturoid.apiary.io/ for complete field reference."""
    name: str
    registration_no: Optional[str] = None
    updated_at: datetime

    class Meta:
        readonly = ['avatar_url', 'html_url', 'url', 'updated_at']
        decimal = []

    def __unicode__(self):
        return self.name


@dataclass
class Inventory:
    item_id: str
    sku: str
    article_number_type: str
    article_article_number_type: str
    move_id: int


class Line(Unique):
    name: str
    quantity: Decimal
    unit_name: Optional[str]
    unit_price: Decimal

    class Meta:
        readonly = []  # no id here, to correct update
        decimal = ['quantity', 'unit_price']

    def __unicode__(self):
        if self.unit_name:
            return "{0} {1} {2}".format(self.quantity, self.unit_name, self.name)
        else:
            if self.quantity == 1:
                return self.name
            else:
                return "{0} {1}".format(self.quantity, self.name)


class AbstractInvoice(Model, Unique):
    lines: list[Line]
    _loaded_lines = []  # keep loaded data to be able delete removed lines


class Invoice(AbstractInvoice):
    """See http://docs.fakturoid.apiary.io/ for complete field reference."""

    number: Optional[str]

    class Meta:
        readonly = [
            'id', 'token', 'status', 'due_on',
            'sent_at', 'paid_at', 'reminder_sent_at', 'accepted_at', 'canceled_at',
            'subtotal', 'native_subtotal', 'total', 'native_total',
            'remaining_amount', 'remaining_native_amount',
            'html_url', 'public_html_url', 'url', 'updated_at',
            'subject_url'
        ]
        decimal = [
            'exchange_rate', 'subtotal', 'total',
            'native_subtotal', 'native_total', 'remaining_amount',
            'remaining_native_amount'
        ]

    def __unicode__(self):
        return self.number


class InventoryItem(Model, Unique):
    """See http://docs.fakturoid.apiary.io/ for complete field reference."""
    name: str

    class Meta:
        readonly = 'id'
        writeable = 'name sku article_number_type article_number unit_name vat_rate supply_type private_note suggest_for'.split()
        boolean = ['track_quantity', 'allow_below_zero']
        decimal = 'quantity min_quantity max_quantity native_purchase_price native_retail_price'.split()

    def __unicode__(self):
        return self.name


class Expense(AbstractInvoice):
    """See http://docs.fakturoid.apiary.io/ for complete field reference."""

    number: str

    class Meta:
        readonly = [
            'id', 'supplier_name', 'supplier_street', 'supplier_city',
            'supplier_zip', 'supplier_country', 'supplier_registration_no',
            'supplier_vat_no', 'status', 'paid_on', 'subtotal', 'total',
            'native_subtotal', 'native_total', 'html_url', 'url', 'subject_url',
            'created_at', 'updated_at'
        ]
        decimal = [
            'exchange_rate', 'subtotal', 'total',
            'native_subtotal', 'native_total'
        ]

    def __unicode__(self):
        return self.number


class Generator(Model):
    """See http://docs.fakturoid.apiary.io/ for complete field reference."""
    name: str

    class Meta:
        readonly = [
            'id', 'subtotal', 'native_subtotal', 'total', 'native_total',
            'html_url', 'url', 'subject_url', 'updated_at'
        ]
        decimal = ['exchange_rate', 'subtotal', 'total', 'native_subtotal', 'native_total']

    def __unicode__(self):
        return self.name


class Message(Model):
    """See http://docs.fakturoid.apiary.io/#reference/messages for complete field reference."""
    subject: str

    class Meta:
        decimal = []

    def __unicode__(self):
        return self.subject
