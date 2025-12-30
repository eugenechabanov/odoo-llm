# Copyright 2025 Apexive Solutions LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

"""
Type definitions for invoice analyzer and updater tools.

These types ensure type-safety and clear contracts between tools and LLM.
Uses Pydantic for runtime validation and type safety.
"""

from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# EXTRACTED DATA (Input from LLM)
# =============================================================================


class ExtractedLine(BaseModel):
    """Single line item extracted from invoice by LLM - uses Odoo field names"""

    name: str = Field(..., description="Line description (Odoo field name)")
    quantity: float
    price_unit: float = Field(..., description="Unit price (Odoo field name)")


class ExtractedInvoiceData(BaseModel):
    """Invoice data extracted by LLM from OCR text - uses Odoo field names where applicable"""

    vendor_name: str = Field(..., description="Intermediate field (maps to partner_id)")
    lines: list[ExtractedLine]
    ref: Optional[str] = Field(None, description="Invoice reference/number (Odoo field name)")
    vat: Optional[str] = Field(None, description="Vendor VAT number (intermediate, maps to partner_id.vat)")
    invoice_date: Optional[str] = Field(None, description="Invoice date (Odoo field name)")
    invoice_date_due: Optional[str] = Field(None, description="Payment due date (Odoo field name)")
    total: Optional[float] = Field(None, description="Total amount (intermediate, maps to amount_total)")


# =============================================================================
# CONSTRAINTS (User Choices)
# =============================================================================


class ProductChoice(BaseModel):
    """Type-safe product choice for a line item"""

    line_index: int = Field(..., description="0-based index")
    choice: Union[int, Literal["manual"], Literal["skip"]] = Field(
        ...,
        description="int = product_id to use, 'manual' = create line without product, 'skip' = don't create this line"
    )


class PartnerChoice(BaseModel):
    """Type-safe partner choice"""

    choice: Union[int, Literal["create_new"]] = Field(
        ...,
        description="int = partner_id to use, 'create_new' = create new partner with extracted data"
    )


class AnalyzerConstraints(BaseModel):
    """Constraints for analyzer (user decisions)"""

    partner_choice: Optional[PartnerChoice] = None
    product_choices: Optional[list[ProductChoice]] = None


# =============================================================================
# INTERNAL MATCHING RESULTS
# =============================================================================


class HistoricalPatterns(BaseModel):
    """Historical patterns from partner's invoice history"""

    common_payment_term: Optional[str] = None
    common_payment_term_id: Optional[int] = None
    recent_invoice_count: int = 0


class PartnerMatchResult(BaseModel):
    """Result of partner matching operation"""

    model_config = ConfigDict(arbitrary_types_allowed=True)  # Allow Odoo recordset

    partner: Optional[Any] = None  # Odoo recordset
    needs_decision: bool = False
    needs_search: bool = False
    method: Optional[str] = None
    confidence: Optional[str] = None
    alternatives: Optional[list[PartnerOption]] = None
    search_hints: Optional[dict[str, Any]] = None


class ProductMatchResult(BaseModel):
    """Result of product matching operation"""

    product_id: Optional[int] = None
    product_name: Optional[str] = None
    needs_decision: bool = False
    needs_search: bool = False
    skip: bool = False
    method: Optional[str] = None
    confidence: Optional[str] = None
    ocr_description: str = ""
    alternatives: Optional[list[ProductOption]] = None
    search_hints: Optional[dict[str, Any]] = None


# =============================================================================
# ANALYZER RESPONSES
# =============================================================================


class OCRSummary(BaseModel):
    """Compact OCR summary for analyzer context"""

    vendor: str
    ref: str
    date: str
    total: float
    line_count: int


class AnalyzerContext(BaseModel):
    """Common context present in all analyzer responses"""

    invoice_id: int
    invoice_number: str
    extracted_data_summary: dict[str, Any] = Field(..., description="Compact OCR summary")


class PartnerInfo(BaseModel):
    """Partner information"""

    id: int
    name: str
    vat: str


class PartnerOption(BaseModel):
    """Partner option for user selection"""

    id: Optional[int] = Field(None, description="None for 'create new'")
    name: str
    vat: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    suggested_name: Optional[str] = Field(None, description="For create new option")


class ProductOption(BaseModel):
    """Product option for user selection"""

    id: Optional[int] = Field(None, description="None for 'manual entry'")
    name: str
    description: Optional[str] = None
    code: Optional[str] = None
    list_price: Optional[float] = Field(None, description="Sales price (Odoo field name)")


class InvoiceLine(BaseModel):
    """Complete invoice line ready for creation - uses Odoo field names"""

    name: str = Field(..., description="Line description (Odoo field name)")
    quantity: float
    price_unit: float = Field(..., description="Unit price (Odoo field name)")
    product_id: Optional[int] = Field(None, description="Optional - can be omitted or None")
    product_name: Optional[str] = Field(None, description="Metadata only")
    account_id: Optional[int] = Field(None, description="Optional - can be omitted or None")
    tax_ids: Optional[list[int]] = Field(None, description="Optional - Odoo auto-computes based on product/account + fiscal position")


class SuggestedValues(BaseModel):
    """Suggested values from analyzer - uses Odoo field names"""

    ref: Optional[str] = None
    invoice_date: Optional[str] = Field(None, description="Odoo field name")
    invoice_date_due: Optional[str] = Field(None, description="Odoo field name")
    invoice_payment_term_id: Optional[int] = Field(None, description="Odoo field name")


# Response data for each status
class ReadyData(BaseModel):
    """Data when status is 'ready'"""

    partner_id: int = Field(..., description="CRITICAL: Include for updater")
    partner: PartnerInfo
    lines: list[InvoiceLine]
    suggested_values: SuggestedValues


class SearchHints(BaseModel):
    """Search hints for LLM intelligent searching"""

    model: str = Field(..., description="e.g., 'res.partner', 'product.product'")
    fields_to_search: list[str] = Field(..., description="e.g., ['name', 'vat', 'city']")
    suggested_strategies: list[str] = Field(..., description="Human-readable strategies")
    example_queries: list[dict[str, Any]] = Field(..., description="Example domain queries")
    instructions: str = Field(..., description="Detailed instructions for LLM")


class NeedsInputPartnerData(BaseModel):
    """Data when status is 'needs_input' for partner selection"""

    question_type: Literal["partner_selection"]
    question: str
    partner_options: list[PartnerOption]


class NeedsInputPartnerSearchData(BaseModel):
    """Data when status is 'needs_input' for partner intelligent search"""

    question_type: Literal["partner_search"]
    question: str
    search_hints: dict[str, Any] = Field(..., description="SearchHints + specific fields")


class NeedsInputProductData(BaseModel):
    """Data when status is 'needs_input' for product selection"""

    question_type: Literal["product_selection"]
    question: str
    line_number: int
    line_description: str
    product_options: list[ProductOption]
    completed: dict[str, Any] = Field(..., description="Already completed decisions (e.g., partner)")


class NeedsInputProductSearchData(BaseModel):
    """Data when status is 'needs_input' for product intelligent search"""

    question_type: Literal["product_search"]
    question: str
    line_number: int
    line_description: str
    search_hints: dict[str, Any] = Field(..., description="SearchHints + specific fields")
    completed: dict[str, Any] = Field(..., description="Already completed decisions (e.g., partner)")


class DuplicateFoundData(BaseModel):
    """Data when status is 'duplicate_found'"""

    duplicate_id: int
    duplicate_number: str
    message: str


class ErrorData(BaseModel):
    """Data when status is 'error'"""

    error: str
    suggestion: str


# Union of all possible data types
NeedsInputData = Union[
    NeedsInputPartnerData,
    NeedsInputPartnerSearchData,
    NeedsInputProductData,
    NeedsInputProductSearchData,
]


# Complete analyzer responses
class AnalyzerResponseReady(BaseModel):
    """Analyzer response when ready to create invoice"""

    status: Literal["ready"]
    context: AnalyzerContext
    data: ReadyData


class AnalyzerResponseNeedsInput(BaseModel):
    """Analyzer response when user input needed"""

    status: Literal["needs_input"]
    context: AnalyzerContext
    data: NeedsInputData


class AnalyzerResponseDuplicate(BaseModel):
    """Analyzer response when duplicate found"""

    status: Literal["duplicate_found"]
    context: AnalyzerContext
    data: DuplicateFoundData


class AnalyzerResponseError(BaseModel):
    """Analyzer response when error occurred"""

    status: Literal["error"]
    context: AnalyzerContext
    data: ErrorData


# Union type for all analyzer responses
AnalyzerResponse = Union[
    AnalyzerResponseReady,
    AnalyzerResponseNeedsInput,
    AnalyzerResponseDuplicate,
    AnalyzerResponseError,
]


# =============================================================================
# UPDATER INPUT/OUTPUT
# =============================================================================


class ApprovedAnalysis(BaseModel):
    """Approved analysis from analyzer to pass to updater - uses Odoo field names"""

    partner_id: int = Field(..., description="REQUIRED")
    lines: list[InvoiceLine] = Field(..., description="REQUIRED")
    ref: str = Field(..., description="REQUIRED")
    invoice_date: str = Field(..., description="REQUIRED (Odoo field name)")
    invoice_date_due: Optional[str] = Field(None, description="Odoo field name")
    invoice_payment_term_id: Optional[int] = Field(None, description="Odoo field name")


class UpdaterTotals(BaseModel):
    """Invoice totals"""

    subtotal: float
    tax: float
    total: float


class UpdaterValidation(BaseModel):
    """Validation results"""

    expected_total: Optional[float] = None
    actual_total: Optional[float] = None
    totals_match: Optional[bool] = None


class UpdaterResponseSuccess(BaseModel):
    """Updater response when successful"""

    status: Literal["success"]
    invoice_id: int
    invoice_number: str
    partner: str
    lines_created: int
    totals: UpdaterTotals
    validation: UpdaterValidation
    message: str


class UpdaterResponseError(BaseModel):
    """Updater response when error occurred"""

    status: Literal["error"]
    invoice_id: int
    invoice_number: str
    error: str
    suggestion: str
    failed_at: str = Field(..., description="Which step failed")


# Union type for all updater responses
UpdaterResponse = Union[UpdaterResponseSuccess, UpdaterResponseError]
