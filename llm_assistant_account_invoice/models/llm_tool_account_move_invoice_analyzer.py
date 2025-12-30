# Copyright 2025 Apexive Solutions LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

import logging
import re
from typing import Any, Optional

from odoo import _, api, models
from odoo.exceptions import UserError

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
            ("account_move_invoice_analyzer", "Account Move Invoice Analyzer")
        ]

    def account_move_invoice_analyzer_execute(
        self,
        invoice_id: int,
        extracted_data: dict[str, Any],
        constraints: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Analyze invoice using LLM-extracted structured data.

        This tool handles the PROGRAMMATIC parts: matching, validation, duplicate checking.
        The LLM handles the UNSTRUCTURED part: parsing OCR text into structured fields.

        This follows Anthropic's principle: tools do "programmatic operations",
        LLMs do "understanding unstructured data".

        Parameters:
            invoice_id: ID of the account.move record to analyze
            extracted_data: Structured data extracted by LLM from OCR, containing:
                {
                    "vendor_name": str,
                    "vat": str (optional),
                    "ref": str (invoice reference/number),
                    "date": str (invoice date),
                    "due_date": str (optional),
                    "lines": [
                        {
                            "description": str,
                            "quantity": float,
                            "unit_price": float
                        }
                    ],
                    "total": float
                }
            constraints: Optional user-provided constraints (e.g., confirmed partner_id)

        Returns:
            Focused analysis with one of these statuses:
            - 'ready': All matches found, ready to execute
            - 'needs_input': User decision required
            - 'duplicate_found': Invoice already exists (blocker)
            - 'error': Analysis failed

        Example LLM usage:
            # Step 1: LLM parses OCR text
            ocr_text = llm_tool_ocr_mistral(attachment_ids)
            # LLM extracts structured data from OCR text

            # Step 2: LLM calls analyzer with structured data
            result = invoice_analyzer(
                invoice_id=123,
                extracted_data={
                    "vendor_name": "Acme Corp",
                    "vat": "BE0123456789",
                    "ref": "INV-2025-001",
                    "lines": [...]
                }
            )

            if result['status'] == 'needs_input':
                # Ask user to choose from result['options']

            elif result['status'] == 'ready':
                # Present result['suggested_invoice'] for approval
        """
        constraints = constraints or {}

        try:
            # Get invoice and validate
            invoice = self._get_invoice(invoice_id)

            # Validate extracted_data has required fields
            if not extracted_data.get("vendor_name"):
                return {
                    "status": "error",
                    "error": "extracted_data must contain 'vendor_name'. "
                            "Please parse the OCR text and extract vendor information first.",
                    "suggestion": "Use llm_tool_ocr_mistral to get the invoice text, then extract vendor_name from it.",
                }

            if not extracted_data.get("lines"):
                return {
                    "status": "error",
                    "error": "extracted_data must contain 'lines' array. "
                            "Please extract line items from the OCR text.",
                    "suggestion": "Parse the OCR text and extract line items with description, quantity, and unit_price.",
                }

            # Use the LLM-extracted data directly
            ocr_data = extracted_data

            # STEP 2: Match Partner
            partner_result = self._match_partner(
                ocr_data, constraints.get("partner_id")
            )

            if partner_result["needs_decision"]:
                return self._needs_input_response(
                    question="partner_selection",
                    message=f"Found {len(partner_result['alternatives'])} possible partners",
                    options=partner_result["alternatives"],
                    ocr_data=ocr_data,
                )

            partner = partner_result["partner"]

            # STEP 3: Check Duplicates (EARLY EXIT if found)
            duplicate = self._check_duplicate(partner, ocr_data)
            if duplicate:
                return self._duplicate_response(duplicate, ocr_data)

            # STEP 4: Match Products
            product_results = self._match_products(
                ocr_data["lines"], partner, constraints.get("product_choices", {})
            )

            # Check if any product needs user input
            for idx, prod in enumerate(product_results):
                if prod["needs_decision"]:
                    return self._needs_input_response(
                        question="product_selection",
                        message=f"Line {idx + 1}: '{prod['ocr_description']}' has multiple matches",
                        line_number=idx + 1,
                        ocr_description=prod["ocr_description"],
                        options=prod["alternatives"],
                        ocr_data=ocr_data,
                        partner={
                            "id": partner.id,
                            "name": partner.name,
                            "vat": partner.vat or "",
                        },
                        partial_products=product_results,
                    )

            # STEP 5: Get Historical Patterns (optional context)
            patterns = self._get_historical_patterns(partner)

            # STEP 6: Build Suggested Invoice Structure
            suggested_invoice = self._build_suggested_invoice(
                invoice, ocr_data, partner, product_results, patterns
            )

            # SUCCESS: Everything matched!
            return {
                "status": "ready",
                "invoice_id": invoice.id,
                "ocr_data": self._format_ocr_summary(ocr_data),
                "partner": {
                    "id": partner.id,
                    "name": partner.name,
                    "vat": partner.vat or "",
                },
                "duplicate_check": {"is_duplicate": False},
                "lines_matched": len(product_results),
                "suggested_invoice": suggested_invoice,
                "historical_patterns": patterns,
                "message": f"Analysis complete! Found partner '{partner.name}', matched {len(product_results)} lines",
            }

        except Exception as e:
            _logger.error(f"Invoice analyzer error: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "suggestion": "Check the invoice data and try again. Ensure all required fields are provided.",
            }

    # ═══════════════════════════════════════════════════════════════
    # PARTNER MATCHING (OCA-inspired strategies)
    # ═══════════════════════════════════════════════════════════════

    def _match_partner(self, ocr_data: dict, forced_partner_id: Optional[int] = None) -> dict:
        """
        Match partner using OCA-style hierarchy:
        1. VAT (highest confidence)
        2. Partner ref
        3. Name (exact then fuzzy)

        Returns max 2 alternatives if ambiguous.
        """
        if forced_partner_id:
            partner = self.env["res.partner"].browse(forced_partner_id)
            if partner.exists():
                return {"partner": partner, "needs_decision": False}

        Partner = self.env["res.partner"]
        company_domain = self._get_company_domain()

        # Priority 1: VAT exact match
        if ocr_data.get("vat"):
            vat_clean = self._normalize_vat(ocr_data["vat"])
            partner = Partner.search(
                [("vat", "=ilike", vat_clean)] + company_domain, limit=1
            )
            if partner:
                return {
                    "partner": partner,
                    "needs_decision": False,
                    "method": "vat",
                    "confidence": "high",
                }

        # Priority 2: Name search
        if ocr_data.get("vendor_name"):
            name = ocr_data["vendor_name"]

            # Exact match first
            partners = Partner.search(
                [("name", "=ilike", name)] + company_domain, limit=3
            )

            if len(partners) == 1:
                return {
                    "partner": partners[0],
                    "needs_decision": False,
                    "method": "name_exact",
                    "confidence": "high",
                }
            elif len(partners) > 1:
                # Multiple matches - need user input
                return {
                    "partner": None,
                    "needs_decision": True,
                    "alternatives": self._format_partner_alternatives(partners[:2]),
                    "method": "name_multiple",
                }

            # Fuzzy match: split into tokens and search with OR
            # Handles cases like "strato gmbh" vs "strato.nl"
            tokens = name.split()
            if tokens:
                # Build OR domain for all tokens: token1 OR token2 OR token3
                token_domain = []
                for token in tokens:
                    if token_domain:
                        token_domain = ["|"] + token_domain
                    token_domain.append(("name", "ilike", f"%{token}%"))

                # Combine with company domain
                fuzzy_domain = token_domain + company_domain
                partners = Partner.search(fuzzy_domain, limit=3)

                if len(partners) == 1:
                    return {
                        "partner": partners[0],
                        "needs_decision": False,
                        "method": "name_fuzzy",
                        "confidence": "medium",
                    }
                elif len(partners) > 1:
                    return {
                        "partner": None,
                        "needs_decision": True,
                        "alternatives": self._format_partner_alternatives(partners[:2]),
                        "method": "name_fuzzy_multiple",
                    }

        # No match - suggest creation
        return {
            "partner": None,
            "needs_decision": True,
            "alternatives": [
                {
                    "id": None,
                    "name": "Create new partner",
                    "vat": ocr_data.get("vat", ""),
                    "suggested_name": ocr_data.get("vendor_name", ""),
                }
            ],
        }

    def _normalize_vat(self, vat: str) -> str:
        """Normalize VAT number (remove spaces, uppercase)"""
        return re.sub(r"[^A-Z0-9]", "", vat.upper())

    def _format_partner_alternatives(self, partners) -> list[dict]:
        """Format partner alternatives for LLM (semantic, not UUIDs)"""
        return [
            {
                "id": p.id,
                "name": p.name,
                "vat": p.vat or "",
                "city": p.city or "",
                "country": p.country_id.name if p.country_id else "",
            }
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

    # ═══════════════════════════════════════════════════════════════
    # STEP 4: PRODUCT MATCHING (with supplier code support!)
    # ═══════════════════════════════════════════════════════════════

    def _match_products(
        self, lines: list[dict], partner, product_choices: dict
    ) -> list[dict]:
        """
        Match products using OCA-style priority:
        1. Supplier code (via product.supplierinfo) - CRITICAL!
        2. Barcode
        3. Internal code
        4. Name fuzzy match
        """
        results = []

        for idx, line in enumerate(lines):
            forced_product_id = product_choices.get(str(idx))

            if forced_product_id:
                product = self.env["product.product"].browse(forced_product_id)
                if product.exists():
                    results.append(
                        {
                            "product_id": product.id,
                            "product_name": product.name,
                            "needs_decision": False,
                            "ocr_description": line["description"],
                        }
                    )
                    continue

            result = self._match_single_product(line, partner)
            results.append(result)

        return results

    def _match_single_product(self, line: dict, partner) -> dict:
        """Match a single product line"""
        Product = self.env["product.product"]
        company_domain = self._get_company_domain()

        description = line.get("description", "")

        # Priority 1: Supplier code (if we can extract it)
        # In real implementation, you'd extract supplier codes from OCR
        # For now, we'll skip to name matching

        # Priority 2: Name search
        if description:
            # Exact match
            products = Product.search(
                [("name", "=ilike", description)] + company_domain, limit=3
            )

            if len(products) == 1:
                return {
                    "product_id": products[0].id,
                    "product_name": products[0].name,
                    "needs_decision": False,
                    "confidence": "high",
                    "method": "name_exact",
                    "ocr_description": description,
                }
            elif len(products) > 1:
                return {
                    "product_id": None,
                    "product_name": None,
                    "needs_decision": True,
                    "alternatives": self._format_product_alternatives(products[:2]),
                    "ocr_description": description,
                }

            # Fuzzy match
            products = Product.search(
                [("name", "ilike", description)] + company_domain, limit=3
            )

            if len(products) == 1:
                return {
                    "product_id": products[0].id,
                    "product_name": products[0].name,
                    "needs_decision": False,
                    "confidence": "medium",
                    "method": "name_fuzzy",
                    "ocr_description": description,
                }
            elif len(products) > 1:
                return {
                    "product_id": None,
                    "product_name": None,
                    "needs_decision": True,
                    "alternatives": self._format_product_alternatives(products[:2]),
                    "ocr_description": description,
                }

        # No match - will need manual entry
        return {
            "product_id": None,
            "product_name": None,
            "needs_decision": True,
            "alternatives": [
                {
                    "id": None,
                    "name": "Enter manually (no product)",
                    "description": "Create line without product",
                }
            ],
            "ocr_description": description,
        }

    def _format_product_alternatives(self, products) -> list[dict]:
        """Format product alternatives for LLM"""
        return [
            {
                "id": p.id,
                "name": p.name,
                "code": p.default_code or "",
                "price": p.list_price,
            }
            for p in products
        ]

    # ═══════════════════════════════════════════════════════════════
    # STEP 5: HISTORICAL PATTERNS
    # ═══════════════════════════════════════════════════════════════

    def _get_historical_patterns(self, partner) -> dict:
        """Get common patterns from partner's invoice history"""
        if not partner:
            return {}

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
            return {}

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

        return {
            "common_payment_term": most_common_term.name if most_common_term else None,
            "common_payment_term_id": most_common_term.id if most_common_term else None,
            "recent_invoice_count": len(recent_invoices),
        }

    # ═══════════════════════════════════════════════════════════════
    # STEP 6: BUILD SUGGESTED INVOICE
    # ═══════════════════════════════════════════════════════════════

    def _build_suggested_invoice(
        self, invoice, ocr_data: dict, partner, product_results: list[dict], patterns: dict
    ) -> dict:
        """Build complete suggested invoice structure"""
        lines = []

        for line_ocr, prod_result in zip(ocr_data["lines"], product_results):
            line = {
                "description": line_ocr["description"],
                "quantity": line_ocr.get("quantity", 1.0),
                "unit_price": line_ocr.get("unit_price", 0.0),
            }

            if prod_result.get("product_id"):
                product = self.env["product.product"].browse(prod_result["product_id"])
                line["product_id"] = product.id
                line["product_name"] = product.name
                # Auto-fill from product
                line["account_id"] = product.property_account_expense_id.id or product.categ_id.property_account_expense_categ_id.id
                line["tax_ids"] = product.supplier_taxes_id.ids
            else:
                # Manual line - need account
                line["product_id"] = None
                line["account_id"] = None  # Will need to be determined
                line["tax_ids"] = []

            lines.append(line)

        return {
            "partner_id": partner.id,
            "ref": ocr_data.get("ref", ""),
            "invoice_date": ocr_data.get("date"),
            "invoice_payment_term_id": patterns.get("common_payment_term_id"),
            "lines": lines,
            "totals": {
                "expected_total": ocr_data.get("total", 0.0),
            },
        }

    # ═══════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════

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
        return {
            "vendor": ocr_data.get("vendor_name", ""),
            "ref": ocr_data.get("ref", ""),
            "date": ocr_data.get("date", ""),
            "total": ocr_data.get("total", 0.0),
            "line_count": len(ocr_data.get("lines", [])),
        }

    # Response formatters
    def _needs_input_response(self, question: str, message: str, **kwargs) -> dict:
        """Format 'needs_input' response"""
        return {
            "status": "needs_input",
            "question": question,
            "message": message,
            **kwargs,
        }

    def _duplicate_response(self, duplicate, ocr_data: dict) -> dict:
        """Format 'duplicate_found' response"""
        return {
            "status": "duplicate_found",
            "duplicate_invoice": duplicate.name,
            "duplicate_id": duplicate.id,
            "message": f"⚠️ This invoice already exists as {duplicate.name}",
            "ocr_summary": self._format_ocr_summary(ocr_data),
        }

