# Copyright 2025 Apexive Solutions LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

"""
Type definitions for invoice analyzer and updater tools.

These types ensure type-safety and clear contracts between tools and LLM.
"""

import sys
from typing import Any, Literal

# For Python < 3.12, use typing_extensions for TypedDict and NotRequired
# to support proper handling of required/optional fields
if sys.version_info < (3, 12):
    from typing_extensions import NotRequired, TypedDict
else:
    from typing import NotRequired, TypedDict


# =============================================================================
# EXTRACTED DATA (Input from LLM)
# =============================================================================


class ExtractedLine(TypedDict):
    """Single line item extracted from invoice by LLM"""

    description: str
    quantity: float
    unit_price: float


class ExtractedInvoiceData(TypedDict):
    """Invoice data extracted by LLM from OCR text"""

    vendor_name: str
    lines: list[ExtractedLine]
    ref: NotRequired[str]  # Invoice reference/number
    vat: NotRequired[str]  # Vendor VAT number
    date: NotRequired[str]  # Invoice date
    due_date: NotRequired[str]  # Payment due date
    total: NotRequired[float]  # Total amount


# =============================================================================
# CONSTRAINTS (User Choices)
# =============================================================================


class ProductChoice(TypedDict):
    """Type-safe product choice for a line item"""

    line_index: int  # 0-based index
    choice: int | Literal["manual"] | Literal["skip"]
    # int = product_id to use
    # "manual" = create line without product (manual entry)
    # "skip" = don't create this line


class PartnerChoice(TypedDict):
    """Type-safe partner choice"""

    choice: int | Literal["create_new"]
    # int = partner_id to use
    # "create_new" = create new partner with extracted data


class AnalyzerConstraints(TypedDict, total=False):
    """Constraints for analyzer (user decisions)"""

    partner_choice: PartnerChoice
    product_choices: list[ProductChoice]


# =============================================================================
# ANALYZER RESPONSES
# =============================================================================


class AnalyzerContext(TypedDict):
    """Common context present in all analyzer responses"""

    invoice_id: int
    invoice_number: str
    extracted_data_summary: dict[str, Any]  # Compact OCR summary


class PartnerInfo(TypedDict):
    """Partner information"""

    id: int
    name: str
    vat: str


class PartnerOption(TypedDict):
    """Partner option for user selection"""

    id: int | None  # None for "create new"
    name: str
    vat: NotRequired[str]
    city: NotRequired[str]
    country: NotRequired[str]
    suggested_name: NotRequired[str]  # For create new option


class ProductInfo(TypedDict):
    """Product information"""

    id: int
    name: str
    code: str


class ProductOption(TypedDict):
    """Product option for user selection"""

    id: int | None  # None for "manual entry"
    name: str
    description: NotRequired[str]
    code: NotRequired[str]
    price: NotRequired[float]


class InvoiceLine(TypedDict):
    """Complete invoice line ready for creation"""

    description: str
    quantity: float
    unit_price: float
    product_id: int | None
    product_name: NotRequired[str]
    account_id: int | None
    tax_ids: list[int]


class SuggestedValues(TypedDict, total=False):
    """Suggested values from analyzer"""

    ref: str
    date: str
    due_date: str
    payment_term_id: int


# Response data for each status
class ReadyData(TypedDict):
    """Data when status is 'ready'"""

    partner_id: int  # CRITICAL: Include for updater
    partner: PartnerInfo
    lines: list[InvoiceLine]
    suggested_values: SuggestedValues


class SearchHints(TypedDict):
    """Search hints for LLM intelligent searching"""

    model: str  # e.g., "res.partner", "product.product"
    fields_to_search: list[str]  # e.g., ["name", "vat", "city"]
    suggested_strategies: list[str]  # Human-readable strategies
    example_queries: list[dict[str, Any]]  # Example domain queries
    instructions: str  # Detailed instructions for LLM


class NeedsInputPartnerData(TypedDict):
    """Data when status is 'needs_input' for partner selection"""

    question_type: Literal["partner_selection"]
    question: str
    partner_options: list[PartnerOption]


class NeedsInputPartnerSearchData(TypedDict):
    """Data when status is 'needs_input' for partner intelligent search"""

    question_type: Literal["partner_search"]
    question: str
    search_hints: dict[str, Any]  # SearchHints + specific fields


class NeedsInputProductData(TypedDict):
    """Data when status is 'needs_input' for product selection"""

    question_type: Literal["product_selection"]
    question: str
    line_number: int
    line_description: str
    product_options: list[ProductOption]
    completed: dict[str, Any]  # Already completed decisions (e.g., partner)


class NeedsInputProductSearchData(TypedDict):
    """Data when status is 'needs_input' for product intelligent search"""

    question_type: Literal["product_search"]
    question: str
    line_number: int
    line_description: str
    search_hints: dict[str, Any]  # SearchHints + specific fields
    completed: dict[str, Any]  # Already completed decisions (e.g., partner)


class DuplicateFoundData(TypedDict):
    """Data when status is 'duplicate_found'"""

    duplicate_id: int
    duplicate_number: str
    message: str


class ErrorData(TypedDict):
    """Data when status is 'error'"""

    error: str
    suggestion: str


# Union of all possible data types
NeedsInputData = (
    NeedsInputPartnerData
    | NeedsInputPartnerSearchData
    | NeedsInputProductData
    | NeedsInputProductSearchData
)


# Complete analyzer responses
class AnalyzerResponseReady(TypedDict):
    """Analyzer response when ready to create invoice"""

    status: Literal["ready"]
    context: AnalyzerContext
    data: ReadyData


class AnalyzerResponseNeedsInput(TypedDict):
    """Analyzer response when user input needed"""

    status: Literal["needs_input"]
    context: AnalyzerContext
    data: NeedsInputData


class AnalyzerResponseDuplicate(TypedDict):
    """Analyzer response when duplicate found"""

    status: Literal["duplicate_found"]
    context: AnalyzerContext
    data: DuplicateFoundData


class AnalyzerResponseError(TypedDict):
    """Analyzer response when error occurred"""

    status: Literal["error"]
    context: AnalyzerContext
    data: ErrorData


# Union type for all analyzer responses
AnalyzerResponse = (
    AnalyzerResponseReady
    | AnalyzerResponseNeedsInput
    | AnalyzerResponseDuplicate
    | AnalyzerResponseError
)


# =============================================================================
# UPDATER INPUT/OUTPUT
# =============================================================================


class ApprovedAnalysis(TypedDict):
    """Approved analysis from analyzer to pass to updater"""

    partner_id: int  # REQUIRED
    lines: list[InvoiceLine]  # REQUIRED
    ref: str  # REQUIRED
    date: str  # REQUIRED
    due_date: NotRequired[str]
    payment_term_id: NotRequired[int]


class UpdaterTotals(TypedDict):
    """Invoice totals"""

    subtotal: float
    tax: float
    total: float


class UpdaterValidation(TypedDict, total=False):
    """Validation results"""

    expected_total: float
    actual_total: float
    totals_match: bool


class UpdaterResponseSuccess(TypedDict):
    """Updater response when successful"""

    status: Literal["success"]
    invoice_id: int
    invoice_number: str
    partner: str
    lines_created: int
    totals: UpdaterTotals
    validation: UpdaterValidation
    message: str


class UpdaterResponseError(TypedDict):
    """Updater response when error occurred"""

    status: Literal["error"]
    invoice_id: int
    invoice_number: str
    error: str
    suggestion: str
    failed_at: str  # Which step failed


# Union type for all updater responses
UpdaterResponse = UpdaterResponseSuccess | UpdaterResponseError
