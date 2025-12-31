# Copyright 2025 Apexive Solutions LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

import logging
import re
from typing import Optional

from odoo import _, api, models
from odoo.exceptions import UserError

from .invoice_tool_types import (
    AnalyzerConstraints,
    AnalyzerResponse,
    ExtractedInvoiceData,
    PartnerChoice,
    ProductChoice,
)

_logger = logging.getLogger(__name__)


class LLMToolAccountMoveInvoiceAnalyzer(models.Model):
    """
    Consolidated invoice analysis tool following Anthropic's best practices.

    IMPORTANT: This tool does NOT parse OCR. Following Anthropic's principle
    "Tools do programmatic operations, LLMs do understanding unstructured data",
    the LLM should parse OCR text first and pass structured data to this tool.

    This tool consolidates multiple PROGRAMMATIC operations:
    - Partner matching (with OCA-style strategies: VAT → name)
    - Duplicate checking (early exit blocker)
    - Product matching (with supplier code support)
    - Historical pattern analysis

    Returns focused, high-signal results optimized for LLM consumption.
    """

    _inherit = "llm.tool"

    @api.model
    def _get_available_implementations(self):
        implementations = super()._get_available_implementations()
        return implementations + [
            ("account_move_invoice_analyzer", "Account Move Invoice Analyzer"),
        ]

    def _normalize_vat(self, vat: str) -> str:
        """Normalize VAT number (remove spaces, uppercase)"""
        return re.sub(r"[^A-Z0-9]", "", vat.upper())

    def _format_partner_alternatives(self, partners) -> list[dict]:
        """Format partner alternatives for LLM (semantic, not UUIDs)"""
        from .invoice_tool_types import PartnerOption

        return [
            PartnerOption(
                id=p.id,
                name=p.name,
                vat=p.vat or None,
                city=p.city or None,
                country=p.country_id.name if p.country_id else None,
            ).model_dump()
            for p in partners
        ]

    # ═══════════════════════════════════════════════════════════════
    # STEP 3: DUPLICATE CHECK
    # ═══════════════════════════════════════════════════════════════

    def _check_duplicate(self, partner, ocr_data: dict):
        """Check if invoice already exists (early exit blocker)"""
        if not partner or not ocr_data.get("ref"):
            return None

        Invoice = self.env["account.move"]

        duplicate = Invoice.search(
            [
                ("partner_id", "=", partner.id),
                ("ref", "=", ocr_data["ref"]),
                ("move_type", "in", ["in_invoice", "in_refund"]),
            ],
            limit=1,
        )

        return duplicate if duplicate else None

    def _format_product_alternatives(self, products) -> list[dict]:
        """Format product alternatives for LLM"""
        from .invoice_tool_types import ProductOption

        return [
            ProductOption(
                id=p.id,
                name=p.name,
                code=p.default_code or None,
                list_price=p.list_price,
            ).model_dump()
            for p in products
        ]

    def _get_historical_patterns(self, partner) -> dict:
        """Get common patterns from partner's invoice history"""
        from .invoice_tool_types import HistoricalPatterns

        if not partner:
            return HistoricalPatterns().model_dump()

        # Get last 10 posted invoices from this partner
        recent_invoices = self.env["account.move"].search(
            [
                ("partner_id", "=", partner.id),
                ("move_type", "in", ["in_invoice", "in_refund"]),
                ("state", "=", "posted"),
            ],
            limit=10,
            order="invoice_date desc",
        )

        if not recent_invoices:
            return HistoricalPatterns().model_dump()

        # Analyze patterns - find most common payment term
        payment_terms = recent_invoices.mapped("invoice_payment_term_id")

        if payment_terms:
            # Count occurrences of each payment term
            from collections import Counter
            term_ids = [term.id for term in payment_terms]
            most_common_id = Counter(term_ids).most_common(1)[0][0]
            most_common_term = self.env["account.payment.term"].browse(most_common_id)
        else:
            most_common_term = None

        patterns = HistoricalPatterns(
            common_payment_term=most_common_term.name if most_common_term else None,
            common_payment_term_id=most_common_term.id if most_common_term else None,
            recent_invoice_count=len(recent_invoices),
        )
        return patterns.model_dump()

    def _get_invoice(self, invoice_id: int):
        """Get and validate invoice"""
        invoice = self.env["account.move"].browse(invoice_id)
        if not invoice.exists():
            raise UserError(_("Invoice %d not found") % invoice_id)
        return invoice

    def _get_company_domain(self) -> list:
        """Multi-company domain filter"""
        company_ids = self.env.context.get("allowed_company_ids", [self.env.company.id])
        return ["|", ("company_id", "=", False), ("company_id", "in", company_ids)]

    def _format_ocr_summary(self, ocr_data: dict) -> dict:
        """Format OCR data for compact LLM response"""
        from .invoice_tool_types import OCRSummary

        summary = OCRSummary(
            vendor=ocr_data.get("vendor_name", ""),
            ref=ocr_data.get("ref", ""),
            date=ocr_data.get("invoice_date", ""),
            total=ocr_data.get("total", 0.0),
            line_count=len(ocr_data.get("lines", [])),
        )
        return summary.model_dump()

    # ═══════════════════════════════════════════════════════════════════════════
    # Type-Safe Invoice Analyzer with Intelligent Search
    # ═══════════════════════════════════════════════════════════════════════════

    def account_move_invoice_analyzer_execute(
        self,
        invoice_id: int,
        extracted_data: ExtractedInvoiceData,
        constraints: Optional[AnalyzerConstraints] = None,
    ) -> AnalyzerResponse:
        """
        Type-safe invoice analyzer with intelligent search and consistent responses.

        Philosophy: "Tools do programmatic operations, LLMs do understanding unstructured data"
        - Simple exact matching in tool (VAT, name)
        - LLM handles intelligent fuzzy matching via odoo_record_retriever

        Key features:
        - Consistent response structure for all statuses
        - Type-safe constraints (explicit "manual" | "skip" | int)
        - Always includes partner_id when ready
        - Returns search hints for LLM when no exact match found

        Parameters:
            invoice_id: ID of the account.move record
            extracted_data: Type-safe extracted invoice data from LLM
            constraints: Optional user decisions from previous call
                Format: {
                    "partner_choice": {"choice": 9},  # int or "create_new"
                    "product_choices": [
                        {"line_index": 0, "choice": 123},  # int, "manual", or "skip"
                        {"line_index": 1, "choice": "manual"}
                    ]
                }

        Returns:
            AnalyzerResponse with consistent structure:
            {
                "status": "ready" | "needs_input" | "duplicate_found" | "error",
                "context": {...},  # Always present
                "data": {...}      # Shape depends on status
            }

        Workflow:
            1. First call (no constraints):
               analyzer(invoice_id, extracted_data)
               → May return "needs_input" with search hints or options

            2. Second call (with constraints):
               analyzer(invoice_id, extracted_data, constraints={
                   "partner_choice": {"choice": partner_id}
               })
               → MUST return "ready" or "error"

            3. Use ready response with updater:
               updater(invoice_id, approved_analysis)
        """
        constraints = constraints or {}

        try:
            # Consolidate all imports at the top
            from .invoice_tool_types import (
                AnalyzerContext,
                AnalyzerResponseNeedsInput,
                AnalyzerResponseDuplicate,
                AnalyzerResponseReady,
                NeedsInputPartnerSearchData,
                NeedsInputPartnerData,
                NeedsInputProductSearchData,
                NeedsInputProductData,
                DuplicateFoundData,
                ReadyData,
                PartnerInfo,
                SuggestedValues,
            )

            invoice = self._get_invoice(invoice_id)

            # Build consistent context (present in all responses)
            context = AnalyzerContext(
                invoice_id=invoice.id,
                invoice_number=invoice.name,
                extracted_data_summary=self._format_ocr_summary(extracted_data),
            )

            # Validate extracted_data
            if not extracted_data.get("vendor_name"):
                return self._error_response(
                    context,
                    error="extracted_data must contain 'vendor_name'",
                    suggestion="Use llm_tool_ocr_mistral to get invoice text, "
                    "then extract vendor_name from it.",
                )

            if not extracted_data.get("lines"):
                return self._error_response(
                    context,
                    error="extracted_data must contain 'lines' array",
                    suggestion="Parse OCR text and extract line items with "
                    "name, quantity, and price_unit (Odoo field names).",
                )

            # ─────────────────────────────────────────────────────────────
            # STEP 1: Match Partner
            # ─────────────────────────────────────────────────────────────
            partner_choice = constraints.get("partner_choice")
            if partner_choice:
                # Apply constraint
                partner = self._apply_partner_choice(partner_choice, extracted_data)
            else:
                # Perform matching (simple + search hints)
                partner_result = self._match_partner(extracted_data, None)

                # Check if LLM needs to search
                if partner_result.get("needs_search"):
                    response = AnalyzerResponseNeedsInput(
                        status="needs_input",
                        context=context,
                        data=NeedsInputPartnerSearchData(
                            question_type="partner_search",
                            question=(
                                f"No exact match found for '{partner_result['search_hints']['vendor_name']}'. "
                                "Please search intelligently using odoo_record_retriever."
                            ),
                            search_hints=partner_result["search_hints"],
                        ),
                    )
                    return response.model_dump()

                # Check if user needs to choose between alternatives
                if partner_result["needs_decision"]:
                    response = AnalyzerResponseNeedsInput(
                        status="needs_input",
                        context=context,
                        data=NeedsInputPartnerData(
                            question_type="partner_selection",
                            question=f"Found {len(partner_result['alternatives'])} possible partners. Which one matches?",
                            partner_options=partner_result["alternatives"],
                        ),
                    )
                    return response.model_dump()

                partner = partner_result["partner"]

            # ─────────────────────────────────────────────────────────────
            # STEP 2: Check Duplicates (early exit)
            # ─────────────────────────────────────────────────────────────
            duplicate = self._check_duplicate(partner, extracted_data)
            if duplicate:
                response = AnalyzerResponseDuplicate(
                    status="duplicate_found",
                    context=context,
                    data=DuplicateFoundData(
                        duplicate_id=duplicate.id,
                        duplicate_number=duplicate.name,
                        message=f"This invoice already exists as {duplicate.name}",
                    ),
                )
                return response.model_dump()

            # ─────────────────────────────────────────────────────────────
            # STEP 3: Match Products
            # ─────────────────────────────────────────────────────────────
            product_results = []
            product_choices_list = constraints.get("product_choices") or []

            for idx, line in enumerate(extracted_data["lines"]):
                # Find constraint for this line
                line_constraint = next(
                    (c for c in product_choices_list if c["line_index"] == idx),
                    None,
                )

                result = self._match_single_product(line, line_constraint)

                # Check if LLM needs to search
                if result.get("needs_search"):
                    response = AnalyzerResponseNeedsInput(
                        status="needs_input",
                        context=context,
                        data=NeedsInputProductSearchData(
                            question_type="product_search",
                            question=(
                                f"Line {idx + 1}: No exact match found for '{result['ocr_description']}'. "
                                "Please search intelligently using odoo_record_retriever."
                            ),
                            line_number=idx + 1,
                            line_description=result["ocr_description"],
                            search_hints=result["search_hints"],
                            completed={
                                "partner": {
                                    "id": partner.id,
                                    "name": partner.name,
                                    "vat": partner.vat or "",
                                }
                            },
                        ),
                    )
                    return response.model_dump()

                # Check if needs user decision
                if result.get("needs_decision"):
                    response = AnalyzerResponseNeedsInput(
                        status="needs_input",
                        context=context,
                        data=NeedsInputProductData(
                            question_type="product_selection",
                            question=f"Which product matches line {idx + 1}?",
                            line_number=idx + 1,
                            line_description=line["name"],
                            product_options=result["alternatives"],
                            completed={
                                "partner": {
                                    "id": partner.id,
                                    "name": partner.name,
                                    "vat": partner.vat or "",
                                }
                            },
                        ),
                    )
                    return response.model_dump()

                # Skip lines marked as "skip"
                if not result.get("skip"):
                    product_results.append(result)

            # ─────────────────────────────────────────────────────────────
            # STEP 4: Build Complete Response (READY!)
            # ─────────────────────────────────────────────────────────────
            patterns = self._get_historical_patterns(partner)

            response = AnalyzerResponseReady(
                status="ready",
                context=context,
                data=ReadyData(
                    partner_id=partner.id,
                    partner=PartnerInfo(
                        id=partner.id,
                        name=partner.name,
                        vat=partner.vat or "",
                    ),
                    lines=self._build_invoice_lines(
                        extracted_data["lines"], product_results
                    ),
                    suggested_values=SuggestedValues(
                        ref=extracted_data.get("ref", ""),
                        invoice_date=extracted_data.get("invoice_date", ""),
                        invoice_date_due=extracted_data.get("invoice_date_due", ""),
                        invoice_payment_term_id=patterns.get("common_payment_term_id"),
                    ),
                ),
            )
            return response.model_dump()

        except Exception as e:
            _logger.error(f"Invoice analyzer error: {e}", exc_info=True)
            error_context = AnalyzerContext(
                invoice_id=invoice_id,
                invoice_number=invoice.name if invoice else "Unknown",
                extracted_data_summary={},
            )
            return self._error_response(
                error_context,
                error=str(e),
                suggestion="Check the invoice data and try again. "
                "Ensure all required fields are provided.",
            )

    # ─────────────────────────────────────────────────────────────────────
    # Helper Methods
    # ─────────────────────────────────────────────────────────────────────

    def _error_response(self, context, error: str, suggestion: str) -> dict:
        """Build standardized error response"""
        from .invoice_tool_types import AnalyzerResponseError, ErrorData

        response = AnalyzerResponseError(
            status="error",
            context=context,
            data=ErrorData(error=error, suggestion=suggestion),
        )
        return response.model_dump()

    def _match_partner(
        self, extracted_data: ExtractedInvoiceData, forced_partner_id: Optional[int] = None
    ) -> dict:
        """
        Simple exact matching, let LLM do intelligent searching!
        Returns PartnerMatchResult as dict.

        Philosophy: Keep tool simple, leverage LLM's intelligence for fuzzy matching.

        Matching hierarchy:
        1. VAT exact match (highest confidence)
        2. Name exact match (case-insensitive)
        3. No match → Return search hints for LLM

        The LLM will use odoo_record_retriever for intelligent fuzzy matching.
        """
        from .invoice_tool_types import PartnerMatchResult

        if forced_partner_id:
            partner = self.env["res.partner"].browse(forced_partner_id)
            if partner.exists():
                result = PartnerMatchResult(
                    partner=partner,
                    needs_decision=False,
                )
                return result.model_dump()

        Partner = self.env["res.partner"]
        company_domain = self._get_company_domain()

        # Priority 1: VAT exact match
        if extracted_data.get("vat"):
            vat_clean = self._normalize_vat(extracted_data["vat"])
            partner = Partner.search(
                [("vat", "=ilike", vat_clean)] + company_domain, limit=1
            )
            if partner:
                result = PartnerMatchResult(
                    partner=partner,
                    needs_decision=False,
                    method="vat",
                    confidence="high",
                )
                return result.model_dump()

        # Priority 2: Name exact match (case-insensitive)
        if extracted_data.get("vendor_name"):
            name = extracted_data["vendor_name"]

            partners = Partner.search(
                [("name", "=ilike", name)] + company_domain, limit=3
            )

            if len(partners) == 1:
                result = PartnerMatchResult(
                    partner=partners[0],
                    needs_decision=False,
                    method="name_exact",
                    confidence="high",
                )
                return result.model_dump()
            elif len(partners) > 1:
                # Multiple exact matches - need user input
                result = PartnerMatchResult(
                    partner=None,
                    needs_decision=True,
                    alternatives=self._format_partner_alternatives(partners[:2]),
                    method="name_multiple",
                )
                return result.model_dump()

        # No exact match → Let LLM search intelligently!
        vendor_name = extracted_data.get("vendor_name", "")
        vat = extracted_data.get("vat", "")

        # Extract first word for example query
        first_word = vendor_name.split()[0] if vendor_name else ""
        vat_prefix = vat[:4] if vat and len(vat) >= 4 else ""

        result = PartnerMatchResult(
            partner=None,
            needs_decision=False,  # Not a user decision
            needs_search=True,      # LLM should search
            search_hints={
                "vendor_name": vendor_name,
                "vat": vat,
                "model": "res.partner",
                "fields_to_search": ["name", "vat", "city", "country_id"],
                "suggested_strategies": [
                    "Try removing legal entities (GmbH, BV, Ltd, N.V., S.A., AG, etc.)",
                    "Search by company name without domain extension (.nl, .com, .de)",
                    "Try partial VAT number matching",
                    "Search by first word of company name",
                    "Look for common abbreviations or variations"
                ],
                "example_queries": [
                    {
                        "description": f"Search by first word: '{first_word}'",
                        "domain": [["name", "ilike", f"%{first_word}%"]] if first_word else [],
                    },
                    {
                        "description": f"Search by VAT prefix: '{vat_prefix}'",
                        "domain": [["vat", "ilike", f"{vat_prefix}%"]] if vat_prefix else [],
                    }
                ],
                "instructions": (
                    "Use odoo_record_retriever to search res.partner model. "
                    "Try different search strategies and present top 2-3 matches to user. "
                    "Include: name, vat, city, country for context."
                )
            },
        )
        return result.model_dump()

    def _apply_partner_choice(
        self, choice: PartnerChoice, extracted_data: ExtractedInvoiceData
    ):
        """Apply user's partner choice"""
        if choice["choice"] == "create_new":
            # Create new partner
            Partner = self.env["res.partner"]
            partner = Partner.create(
                {
                    "name": extracted_data["vendor_name"],
                    "vat": extracted_data.get("vat", ""),
                    "supplier_rank": 1,
                }
            )
            return partner
        else:
            # Use existing partner
            partner = self.env["res.partner"].browse(choice["choice"])
            if not partner.exists():
                raise UserError(_("Selected partner (ID %d) not found") % choice["choice"])
            return partner

    def _match_single_product(
        self,
        line: dict,
        constraint: Optional[ProductChoice],
    ) -> dict:
        """
        Simple exact matching + intelligent search hints for products.

        Key features:
        - Handles "manual"/"skip" explicitly!
        - Simple exact matching only
        - Returns search hints for LLM if no exact match
        """
        from .invoice_tool_types import ProductMatchResult

        if constraint is not None:
            # EXPLICIT constraint handling
            if constraint["choice"] == "manual":
                result = ProductMatchResult(
                    product_id=None,
                    needs_decision=False,
                    method="manual_entry",
                    ocr_description=line["name"],
                )
                return result.model_dump()
            elif constraint["choice"] == "skip":
                result = ProductMatchResult(
                    skip=True,
                    needs_decision=False,
                )
                return result.model_dump()
            elif isinstance(constraint["choice"], int):
                # User selected a product
                product = self.env["product.product"].browse(constraint["choice"])
                if product.exists():
                    result = ProductMatchResult(
                        product_id=product.id,
                        product_name=product.name,
                        needs_decision=False,
                        method="user_selected",
                        ocr_description=line["name"],
                    )
                    return result.model_dump()

        # No constraint - perform simple exact matching
        Product = self.env["product.product"]
        company_domain = self._get_company_domain()
        name = line.get("name", "")

        if not name:
            result = ProductMatchResult(
                product_id=None,
                needs_decision=True,
                alternatives=[
                    {
                        "id": None,
                        "name": "Enter manually (no product)",
                        "description": "Create line without product",
                    }
                ],
                ocr_description=name,
            )
            return result.model_dump()

        # Try exact name match
        products = Product.search(
            [("name", "=ilike", name)] + company_domain, limit=3
        )

        if len(products) == 1:
            result = ProductMatchResult(
                product_id=products[0].id,
                product_name=products[0].name,
                needs_decision=False,
                confidence="high",
                method="name_exact",
                ocr_description=name,
            )
            return result.model_dump()
        elif len(products) > 1:
            result = ProductMatchResult(
                product_id=None,
                needs_decision=True,
                alternatives=self._format_product_alternatives(products[:2]),
                ocr_description=name,
            )
            return result.model_dump()

        # No exact match → Let LLM search intelligently!
        result = ProductMatchResult(
            product_id=None,
            needs_decision=False,  # Not a user decision
            needs_search=True,      # LLM should search
            ocr_description=name,
            search_hints={
                "description": name,
                "model": "product.product",
                "fields_to_search": ["name", "default_code", "barcode"],
                "suggested_strategies": [
                    "Extract core product/service description",
                    "Remove vendor names, quantities, and billing periods",
                    "Search by product type or category",
                    "Look for technical specifications or model numbers",
                    "Try partial matches with distinctive features"
                ],
                "instructions": (
                    "IMPORTANT: Extract the CORE PRODUCT description by intelligently removing:\n"
                    "- Vendor/company names\n"
                    "- Billing periods and quantities\n"
                    "- Payment terms\n"
                    "- Parenthetical technical details\n"
                    "Focus on the actual product/service being purchased.\n\n"
                    "Use odoo_record_retriever to search product.product model.\n"
                    "Present top 2-3 matches with name, code, price.\n"
                    "Always include 'Enter manually (no product)' as an option."
                )
            },
        )
        return result.model_dump()

    def _build_invoice_lines(
        self, ocr_lines: list[dict], product_results: list[dict]
    ) -> list[dict]:
        """Build complete invoice lines for updater"""
        from .invoice_tool_types import InvoiceLine

        lines = []

        for line_ocr, prod_result in zip(ocr_lines, product_results):
            # Build using Pydantic model for type safety
            line_data = {
                "name": line_ocr["name"],
                "quantity": line_ocr.get("quantity", 1.0),
                "price_unit": line_ocr.get("price_unit", 0.0),
                "product_id": prod_result.get("product_id"),
            }

            if prod_result.get("product_id"):
                product = self.env["product.product"].browse(prod_result["product_id"])
                line_data["product_name"] = product.name
                # Odoo auto-computes account_id via _compute_account_id() with fiscal position
            else:
                # Manual entry - no product
                line_data["product_name"] = None
                # Odoo will auto-compute account_id using partner's most frequent account

            # Don't set account_id or tax_ids - Odoo computes both with fiscal position mapping

            line = InvoiceLine(**line_data)
            lines.append(line.model_dump())

        return lines

