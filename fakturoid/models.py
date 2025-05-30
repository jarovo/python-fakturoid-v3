import logging
from datetime import date, datetime
from typing import Optional, Union, Literal, Any, Sequence
from decimal import Decimal
from pydantic.dataclasses import dataclass
from pydantic import Field, BaseModel, EmailStr, AnyUrl

from fakturoid.strenum import StrEnum

from fakturoid.routing import RouteParamAware

__all__ = ["Account", "Subject", "Line", "Invoice", "Generator", "Expense"]


LOGGER = logging.getLogger("python-fakturoid-v3-model")


class Model(BaseModel, RouteParamAware):
    """Base class for all Fakturoid model objects"""

    __original_data__: dict[str, Any] = {}
    __resource_path__: Optional[str] = None

    def __init__(self, **data: Any):
        super().__init__(**data)
        object.__setattr__(self, "__original_data__", self.model_dump())

    def changed_fields(self) -> dict[str, Any]:
        # Start with changed values (unset or default-excluded)
        base = self.model_dump(exclude_defaults=True, exclude_unset=True)

        # Get fields to always include (e.g. foreign keys)
        meta = getattr(self, "Meta", None)
        always = getattr(meta, "always_include", []) if meta else []

        for field in always:
            if field not in base and hasattr(self, field):
                base[field] = getattr(self, field)

        return base

    def to_patch_payload(self):
        return type(self)(**self.changed_fields())

    _display_fields = list[str]()

    def __str__(self):
        values = {k: getattr(self, k) for k in self._display_fields}
        return f"<{self.__class__.__name__} {', '.join(f'{k}={v}' for k, v in values.items())}>"


Currency = str


class UniqueMixin(Model):
    _display_fields = ["id"]

    id: Optional[int] = Field(default_factory=lambda: None, exclude=False)


class TimeTrackedMixin(Model):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AllowedScope(StrEnum):
    Reports = "reports"
    Expenses = "expenses"
    Invoices = "invoices"


class VATMode(StrEnum):
    VATPayer = "vat_payer"
    NonVATPayer = "non_vat_payer"
    IdentifiedPerson = "identified_person"


class VATPriceMode(StrEnum):
    WithVAT = "with_vat"
    WithoutVAT = "without_vat"
    NumericalWithVAT = "numerical_with_vat"
    FromTotalWithVAT = "from_total_with_vat"


class Language(StrEnum):
    Cz = "cz"
    Sk = "sk"
    En = "en"
    De = "de"
    Fr = "fr"
    It = "it"
    Es = "es"
    Ru = "ru"
    Pl = "pl"
    Hu = "hu"
    Ro = "ro"


class PaymentMethod(StrEnum):
    Bank = "bank"
    Card = "card"
    Cash = "cash"
    COD = "cod"
    PayPal = "paypal"


class HidingPaymentTypes(StrEnum):
    Card = "card"
    Cash = "cash"
    Cod = "cod"
    PayPal = "paypal"


class DefaultEstimate(StrEnum):
    estimate = "estimate"
    quote = "quote"


class Account(TimeTrackedMixin):
    subdomain: Optional[str] = None
    plan: Optional[str] = None
    plan_price: Optional[Decimal] = None
    plan_paid_users: Optional[int] = None
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
    currency: Optional[Currency] = None
    unit_name: Optional[str] = None
    vat_rate: Optional[int] = None
    displayed_note: Optional[str] = None
    invoice_note: Optional[str] = None
    due: Optional[int] = None
    invoice_language: Optional[Language] = None
    invoice_payment_method: Optional[PaymentMethod] = None
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


class UserAccount(Model):
    slug: Optional[str] = None
    logo: Optional[AnyUrl] = None
    name: Optional[str] = None
    registration_no: Optional[str] = None
    permission: Optional[str] = None
    allowed_scope: Optional[set[AllowedScope]] = None


class User(UniqueMixin):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    avatar_url: Optional[AnyUrl] = None
    default_account: Optional[str] = None
    permission: Optional[str] = None
    allowed_scope: Optional[set[AllowedScope]] = None
    accounts: Optional[list[UserAccount]] = None


class BankAccount(UniqueMixin, TimeTrackedMixin):
    name: Optional[str] = None
    currency: Optional[str] = None
    number: Optional[str] = None
    iban: Optional[str] = None
    swift_bic: Optional[str] = None
    pairing: Optional[bool] = None
    expense_pairing: Optional[bool] = None
    payment_adjustment: Optional[bool] = None
    default: Optional[bool] = None


class NumberFormat(UniqueMixin, TimeTrackedMixin):
    format: Optional[str] = None
    preview: Optional[str] = None
    default: Optional[bool] = None


class Inherswitch(StrEnum):
    Inherit = "inherit"
    On = "On"
    Off = "Off"


class WebinvoiceHistory(StrEnum):
    Null = None
    Disabled = "disabled"
    Recent = "recent"
    ClientPortal = "client_portal"


class Subject(UniqueMixin, TimeTrackedMixin):

    _display_fields = ["name"]

    name: str

    custom_id: Optional[str] = None
    user_id: Optional[int] = None
    type: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[Union[EmailStr, Literal[""]]] = None
    email_copy: Optional[Union[EmailStr, Literal[""]]] = None
    phone: Optional[str] = None
    web: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None
    zip: Optional[str] = None
    country: Optional[str] = None
    has_delivery_address: Optional[bool] = None
    delivery_name: Optional[str] = None
    delivery_street: Optional[str] = None
    delivery_city: Optional[str] = None
    delivery_country: Optional[str] = None
    due: Optional[int] = None
    currency: Optional[str] = None
    language: Optional[str] = None
    private_note: Optional[str] = None
    registration_no: Optional[str] = None
    vat_no: Optional[str] = None
    unreliable: Optional[bool] = None
    unreliable_checked_at: Optional[datetime] = None
    legal_form: Optional[str] = None
    vat_mode: Optional[str] = None
    bank_account: Optional[str] = None
    iban: Optional[str] = None
    swift_bic: Optional[str] = None
    variable_symbol: Optional[str] = None
    settings_update_from_ares: Optional[Inherswitch] = None
    settings_invoice_pdf_attachments: Optional[Inherswitch] = None
    settings_estimate_pdf_attachments: Optional[Inherswitch] = None
    settings_invoice_send_reminders: Optional[Inherswitch] = None
    suggestion_enabled: Optional[bool] = None
    custom_email_text: Optional[str] = None
    overdue_email_text: Optional[str] = None
    invoice_from_proforma_email_text: Optional[str] = None
    thank_you_email_text: Optional[str] = None
    custom_estimate_email_text: Optional[str] = None
    webinvoice_history: Optional[WebinvoiceHistory] = None
    html_url: Optional[AnyUrl] = None
    url: Optional[AnyUrl] = None

    class Meta:
        readonly = [
            "id",
            "user_id",
            "unreliable",
            "unreliable_checked_at",
            "html_url",
            "url",
            "created_at" "updated_at",
        ]


@dataclass
class LineInventory:
    item_id: int
    sku: str
    article_number_type: Optional[str]
    move_id: int


class Line(UniqueMixin):
    name: str
    unit_price: Decimal
    unit_name: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit_price_without_vat: Optional[Decimal] = None
    unit_price_with_vat: Optional[Decimal] = None
    total_price_without_vat: Optional[Decimal] = None
    total_vat: Optional[Decimal] = None
    native_total_price_without_vat: Optional[Decimal] = None
    native_total_vat: Optional[Decimal] = None
    intventory_item_id: Optional[int] = None
    sku: Optional[str] = None
    inventory: Optional[LineInventory] = None

    class Meta:
        readonly: list[str] = []  # no id here, to correct update
        decimal = ["quantity", "unit_price"]


class VatRateSummary(Model):
    vat_rate: Decimal
    base: Decimal
    vat: Decimal
    currency: Currency
    native_base: Decimal
    native_vat: Decimal
    native_currency: Currency


class PaidAdvances(UniqueMixin):
    number: Optional[str] = None
    variable_symbol: Optional[str] = None
    paid_on: Optional[date] = None
    vat_rate: Optional[Decimal] = None
    price: Optional[Decimal] = None
    vat: Optional[Decimal] = None


class Attachment(Model):
    filename: Optional[str] = None
    data_url: Optional[str] = None


class AccountingDocumentBase(UniqueMixin):

    _display_fields = ["id", "number"]

    subject_id: int

    custom_id: Optional[str] = None
    number: Optional[str] = None
    variable_symbol: Optional[str] = None

    due_on: Optional[date] = None
    locked_at: Optional[datetime] = None
    paid_on: Optional[date] = None
    tags: Optional[set[str]] = None
    bank_account: Optional[str] = None
    iban: Optional[str] = None
    swift_bic: Optional[str] = None
    payment_method: Optional[PaymentMethod] = None
    custom_payment_method: Optional[str] = None
    currency: Optional[Currency] = None
    exchange_rate: Optional[Decimal] = None
    subtotal: Optional[Decimal] = None
    total: Optional[Decimal] = None
    native_subtotal: Optional[Decimal] = None

    lines: list[Line] = Field(default_factory=list[Line])
    vat_rates_summary: list[VatRateSummary] = Field(
        default_factory=list[VatRateSummary]
    )

    class Meta:
        always_include = ["subject_id"]


class DocumentType(StrEnum):
    PartialProforma = "partial_proforma"
    Proforma = "proforma"
    Correction = "correction"
    TaxDocument = "tax_document"
    FinalInvoice = "final_invoice"
    Invoice = "invoice"


class ProformaFollowupDocument(StrEnum):
    FinalInvoicePaid = "final_invoice_paid"
    FinalInvoice = "final_invoice"
    TaxDocument = "tax_document"
    None_ = "none"


class Payment(UniqueMixin, TimeTrackedMixin):
    paid_on: Optional[datetime] = None
    currency: Optional[Currency] = None
    amount: Optional[Decimal] = None
    native_amount: Optional[Decimal] = None
    mark_document_as_paid: Optional[bool] = None
    variable_symbol: Optional[str] = None
    bank_account_id: Optional[int] = None


class ExpensePayment(Payment):
    pass


class InvoicePayment(Payment):
    proforma_followup_document: Optional[ProformaFollowupDocument] = None
    send_thank_you_email: Optional[bool] = None
    tax_document_id: Optional[int] = None


class InvoiceStatus(StrEnum):
    Open = "open"
    Sent = "sent"
    Overdue = "overdue"
    Paid = "paid"
    Cancelled = "cancelled"
    Uncollectible = "uncollectible"


class IbanVisibility(StrEnum):
    Automatically = "automatically"
    Always = "always"


class OSSMode(StrEnum):
    Disabled = "disabled"
    Service = "service"
    Goods = "goods"


class EETRecord(UniqueMixin):
    pass


class Invoice(AccountingDocumentBase):
    document_type: Optional[DocumentType] = None
    proforma_followup_document: Optional[ProformaFollowupDocument] = None
    tax_document_ids: Optional[set[int]] = None
    correction_id: Optional[int] = None
    # number inherited from AccountingDocumentBase
    number_format_id: Optional[int] = None
    # variable symbol inherited from AccountingDocumentBase
    your_name: Optional[str] = None
    your_street: Optional[str] = None
    your_city: Optional[str] = None
    your_zip: Optional[str] = None
    your_country: Optional[str] = None
    your_registration_no: Optional[str] = None
    your_vat_no: Optional[str] = None
    your_local_vat_no: Optional[str] = None

    client_name: Optional[str] = None
    client_street: Optional[str] = None
    client_city: Optional[str] = None
    client_zip: Optional[str] = None
    client_country: Optional[str] = None
    client_has_delivery_address: Optional[bool] = None
    client_delivery_name: Optional[str] = None
    client_delivery_street: Optional[str] = None
    client_delivery_city: Optional[str] = None
    client_delivery_zip: Optional[str] = None
    client_delivery_country: Optional[str] = None
    client_registration_no: Optional[str] = None
    client_vat_no: Optional[str] = None

    subject_custom_id: Optional[str] = None
    generator_id: Optional[int] = None
    related_id: Optional[int] = None

    paypal: Optional[bool] = None
    gopay: Optional[bool] = None

    token: Optional[str] = None
    status: Optional[InvoiceStatus] = None
    order_number: Optional[str] = None
    issued_on: Optional[date] = None
    taxable_fullfillment_due: Optional[str] = None
    due: Optional[int] = None
    sent_at: Optional[datetime] = None
    # paid_on, locked_at # Inherited from AccountingDocumentBase
    reminder_sent_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    uncollectible_at: Optional[datetime] = None

    webinvoice_seen_on: Optional[date] = None
    note: Optional[str] = None
    footer_note: Optional[str] = None
    # tags inherited from AccountingDocumentBase
    bank_account_id: Optional[int] = None
    # bank_account inherited from AccountingDocumentBase
    # iban inherited from AccountingDocumentBase
    # swift_bic inherited from AccountingDocumentBase
    iban_visibility: Optional[IbanVisibility] = None
    show_already_paid_note_in_pdf: Optional[bool] = None
    # payment_method inherited from AccountingDocumentBase
    # custom_payment_method inherited from AccountingDocumentBase
    hide_bank_account: Optional[bool] = None
    # currency inherited from AccountingDocumentBase
    # exchange_rate inherited from AccountingDocumentBase
    language: Optional[Language] = None
    transferred_tax_liability: Optional[bool] = None
    supply_code: Optional[str] = None
    oss: Optional[OSSMode] = None
    # vat_price_mode inherited from AccountingDocumentBase
    round_total: Optional[bool] = None
    # subtotal inherited from AccountingDocumentBase
    # native subtotal inherited from AccountingDocumentBase
    remaining_amount: Optional[Decimal] = None
    remaining_native_amount: Optional[Decimal] = None
    eet_records: Optional[Sequence[EETRecord]] = None
    payments: Optional[Sequence[InvoicePayment]] = None
    attachments: Optional[Sequence[Attachment]] = None

    html_url: Optional[str] = None
    public_html_url: Optional[str] = None
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    subject_url: Optional[str] = None


class InventoryItem(UniqueMixin):
    name: str
    native_retail_price: Optional[Decimal] = None


class Expense(AccountingDocumentBase):
    # custom_id: Inherited from AccountingDocument Base
    # number: Inherited from AccountingDocumentBase
    original_number: Optional[str] = None

    payments: Optional[Sequence[ExpensePayment]] = None


class Generator(UniqueMixin):
    name: str


class LockableAction(StrEnum):
    Lock = "lock"
    Unlock = "unlock"


class InvoiceAction(StrEnum):
    MarkAsSend = "mark_as_send"
    Cancel = "cancel"
    UndoCancel = "undo_cancel"
    MarkAsCollectible = "mark_as_collectible"
    UndoCollectible = "undo_collectible"
    Lock = "lock"
    Unlock = "unlock"
