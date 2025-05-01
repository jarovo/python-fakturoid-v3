from enum import Enum
from datetime import datetime
from typing import Optional
from decimal import Decimal
from dateutil.parser import parse
from pydantic.dataclasses import dataclass
from pydantic import Field, BaseModel, EmailStr, AnyUrl


__all__ = ['Account', 'Subject', 'Line', 'Invoice', 'Generator',
           'Message', 'Expense']


class StrEnum(str, Enum):
    pass


class Model(BaseModel):
    """Base class for all Fakturoid model objects"""

    def __unicode__(self):
        return "<{0}:{1}>".format(self.__class__.__name__, self.id)



class Unique(BaseModel):
    id: Optional[int] = Field(export=False)




class VATMode(StrEnum):
    VATPayer = 'vat_payer'
    NonVATPayer = 'non_vat_payer'
    IdentifiedPerson = 'identified_person'


class VATPriceMode(StrEnum):
    WithVAT = 'with_vat'
    WithoutVAT = 'without_vat'
    NumericalWithVAT = 'numerical_with_vat'
    FromTotalWithVAT = 'from_total_with_vat'


class Language(StrEnum):
    CZ = 'cz'
    SK = 'SK'
    EN = 'EN'
    DE = 'DE'
    FR = 'FR'
    IT = 'IT'
    ES = 'ES'
    RU = 'RU'
    PL = 'PL'
    HU = 'HU'
    RO = 'RO'


class InvoicePaymentMethod(StrEnum):
    Bank = 'bank'
    Card = 'card'
    Cash = 'cash'
    COD = 'cod'
    PayPal = 'paypal'


class HidingPaymentTypes(StrEnum):
    Card = 'card'
    Cash = 'cash'
    Cod = 'cod'
    PayPal = 'paypal'


class DefaultEstimate(StrEnum):
    estimate = "estimate"
    quote = "quote"


class Account(Model):
    """See http://docs.fakturoid.apiary.io/ for complete field reference."""
    subdomain: Optional[str] = None
    plan: Optional[str] = None
    plan_price: Optional[Decimal] = None
    plan_paid_users : Optional[int] = None
    invoice_email: Optional[str] = None
    name: Optional[str] = None
    invoice_email: Optional[EmailStr] = None
    phone: Optional[str] = None
    web: Optional[AnyUrl] = None
    name: Optional[str] = None
    full_name: Optional[str] = None
    registration_no: Optional[str] = None
    vat_no: Optional[str] = None
    local_vat_no: Optional[str] = None
    vat_mode: Optional[VATMode] = None
    vat_price_mode: Optional[VATPriceMode] = None
    street: Optional[str] = None
    city: Optional[str] = None
    zip: Optional[str] = None
    country: Optional[str] = None
    currency: Optional[str] = None
    unit_name: Optional[str] = None
    vat_rate: Optional[int] = None
    displayed_note: Optional[str] = None
    invoice_note: Optional[str] = None
    due: Optional[int] = None
    invoice_language: Optional[Language] = None
    invoice_payment_method: Optional[InvoicePaymentMethod] = None
    invoice_proforma: Optional[bool] = None
    invoice_hide_bank_account_for_payments: Optional[set[HidingPaymentTypes]] = None
    fixed_exchange_rate: Optional[bool] = None
    invoice_selfbilling: Optional[bool] = None
    default_estimate_type: Optional[DefaultEstimate] = None
    send_overdue_email: Optional[bool] = None
    overdue_email_days: Optional[int] = None
    send_repeated_reminders: Optional[bool] = None
    send_invoice_from_proforma_email: Optional[bool] = None
    send_thank_you_email: Optional[bool] = None
    invoice_paypal: Optional[bool] = None
    invoice_gopay: Optional[bool] = None
    digitoo_enabled: Optional[bool] = None
    digitoo_auto_processing_enabled: Optional[bool] = None
    digitoo_extractions_remaining: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BankAccount(Unique):
    name: Optional[str] = None
    currency: Optional[str] = None
    number: Optional[str] = None
    iban: Optional[str] = None
    swift_bic: Optional[str] = None
    pairing:  Optional[bool] = None
    expense_pairing: Optional[bool] = None
    payment_adjustment: Optional[bool] = None
    default: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


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
