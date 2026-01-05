# EDI Analysis: Odoo EDI Modules vs LLM-Based Invoice Processing

> **Analysis Date**: 2026-01-01
> **Status**: Analysis Complete - No integration required (0-10% e-invoice volume)
> **Recommendation**: Keep systems separate, continue with LLM-based approach

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [What is EDI?](#what-is-edi)
3. [Odoo EDI Modules Overview](#odoo-edi-modules-overview)
4. [EDI Module Deep Dive](#edi-module-deep-dive)
5. [Current LLM-Based Implementation](#current-llm-based-implementation)
6. [Comparison: EDI vs LLM-OCR](#comparison-edi-vs-llm-ocr)
7. [Partner & Product Matching Strategies](#partner--product-matching-strategies)
8. [Use Case Analysis](#use-case-analysis)
9. [Integration Opportunities](#integration-opportunities)
10. [Technical Implementation Details](#technical-implementation-details)
11. [Recommendations](#recommendations)
12. [References](#references)

---

## Executive Summary

### Key Finding

The Odoo EDI modules (`account_edi`, `account_edi_ubl_cii`) and the LLM-based OCR system are **complementary, not competing**. They solve different invoice processing problems:

- **EDI**: Handles **structured** electronic invoices (XML-based UBL, CII/Factur-X)
- **LLM-OCR**: Handles **unstructured** invoices (PDF scans, images, varying layouts)

### Current Recommendation

**Keep systems separate** - No integration needed for current vendor profile (0-10% e-invoices, 90%+ unstructured PDFs).

### Why LLM-Based Approach is Optimal

Your implementation excels at the **hard problem**:
- ✅ Scanned/handwritten invoices
- ✅ Varying vendor-specific layouts
- ✅ Multi-language support
- ✅ Intelligent fuzzy matching
- ✅ Historical pattern analysis
- ✅ User-guided interactive workflow

EDI handles the **easy case**: parsing standardized, schema-validated XML formats.

---

## What is EDI?

**EDI (Electronic Data Interchange)** is the structured, computer-to-computer exchange of business documents in standardized formats.

### Key Characteristics

- **Structured Data**: XML-based schemas (not plain text)
- **Standardized Formats**: International standards (UBL, CII/Factur-X, PEPPOL)
- **Schema Validation**: Data integrity guaranteed by XML schema
- **Machine-Readable**: Designed for automated processing
- **B2B Focus**: Primarily used between businesses with established relationships

### Common E-Invoice Standards

| Standard | Full Name | Region | Format |
|----------|-----------|--------|--------|
| **UBL** | Universal Business Language | International | XML |
| **CII** | Cross Industry Invoice | International (UN/CEFACT) | XML |
| **Factur-X** | French/German e-invoice | France/Germany | PDF + embedded XML |
| **PEPPOL** | Pan-European Public Procurement OnLine | Europe | UBL variant |
| **XRechnung** | German e-invoice standard | Germany | UBL variant |
| **E-FFF** | Belgian e-invoice format | Belgium | UBL variant |

---

## Odoo EDI Modules Overview

### Module Hierarchy

```
account_edi (Base Framework)
    ├── account_edi_proxy_client (Web service communication)
    ├── account_edi_ubl_cii (UBL & CII/Factur-X parsers)
    │   ├── account_edi_ubl_cii_tax_extension (Tax handling)
    │   └── Regional variants:
    │       ├── XRechnung (Germany)
    │       ├── E-FFF (Belgium)
    │       ├── NLCIUS (Netherlands)
    │       ├── A-NZ (Australia/New Zealand)
    │       └── SG (Singapore)
    └── Localization modules (l10n_*)
```

### Core Modules

#### 1. **account_edi** - Base Framework

**Location**: `/src/odoo/addons/account_edi`

**Purpose**: Extensible framework for electronic invoice import/export

**Key Features**:
- File format detection (XML, PDF with embedded XML, binary)
- Partner/product matching helpers
- EDI document state machine (to_send → sent → to_cancel → cancelled)
- Async processing via cron jobs
- Web service integration support

**Key Models**:
- `AccountEdiFormat` - Base parser with overridable methods
- `AccountEdiDocument` - Tracks processing state per invoice
- `AccountMove` (extended) - Invoice with EDI capabilities
- `AccountJournal` (extended) - Journal with EDI format selection

#### 2. **account_edi_ubl_cii** - Format Parsers

**Location**: `/src/odoo/addons/account_edi_ubl_cii`

**Purpose**: UBL and CII/Factur-X format parsing

**Supported Formats**:
- UBL 2.0, 2.1, 2.2, 2.3
- UBL Bis3 (Peppol Billing 3.0)
- CII/Factur-X 2.2.0
- Regional variants (XRechnung, E-FFF, NLCIUS, etc.)

**Key Capabilities**:
- XPath-based data extraction from XML
- Partner identification (VAT, name, address)
- Product matching (barcode, supplier code)
- Line item parsing (quantities, prices, taxes, discounts)
- Embedded PDF extraction
- Tax calculation validation

---

## EDI Module Deep Dive

### 1. File Format Detection and Parsing

**File Type Support**:
```
Invoice File Upload
    ↓
[Format Detection] (account_edi_format.py:_decode_attachment)
    ├─→ XML file (.xml extension or starts with <?xml)
    │   └→ _decode_xml() → lxml.etree object
    │
    ├─→ PDF file (.pdf extension)
    │   ├→ Extract embedded XML attachments
    │   └→ _decode_pdf() → PDF reader + embedded XMLs
    │
    └─→ Binary file (fallback)
        └→ _decode_binary() → raw content + extension
```

**Format Inference** (account_edi_ubl_cii):
```python
# From XML structure
if tree.find('./{*}CrossIndustryInvoice'):
    → CII/Factur-X format
elif tree.find('./{*}UBLVersionID'):
    version = tree.find('./{*}UBLVersionID').text
    → UBL {version} format

    # Regional variant detection
    customization = tree.find('./{*}CustomizationID').text
    if 'xrechnung' in customization:
        → XRechnung (German)
    elif 'urn:cen.eu:en16931' in customization:
        → PEPPOL Bis3
```

### 2. Data Extraction Mechanisms

**XPath Queries with Namespace Handling**:
```python
# account_edi_common.py:114-117
def _find_value(self, xpath, tree, nsmap=False):
    # Strip namespaces for wildcard queries: ./{*}NodeName
    nsmap = nsmap or {k: v for k, v in tree.nsmap.items() if k is not None}
    return self.env['account.edi.format']._find_value(
        xpath=xpath,
        xml_element=tree,
        namespaces=nsmap
    )
```

**Extracted Fields**:

| Category | Fields | XPath Examples (UBL) |
|----------|--------|----------------------|
| **Partner** | Name, VAT, Address, Phone, Email | `//cac:AccountingSupplierParty//cbc:Name`<br>`//cac:Party//cbc:CompanyID` |
| **Invoice Header** | Reference, Date, Due Date, Currency | `./{*}ID`<br>`./{*}IssueDate`<br>`./{*}DueDate` |
| **Line Items** | Description, Quantity, Price, Discount | `./cac:InvoiceLine/cac:Item/cbc:Name`<br>`./cbc:InvoicedQuantity`<br>`./cac:Price/cbc:PriceAmount` |
| **Taxes** | Rate, Category, Amount | `./cac:TaxCategory/cbc:Percent`<br>`./cac:TaxTotal/cbc:TaxAmount` |
| **Bank Details** | IBAN, Account Number | `./{*}PayeeFinancialAccount/{*}ID` |

### 3. Partner Matching Logic

**Priority-Based Search Strategy** (account_edi_format.py:389-494):

```python
# 1. VAT-Based Matching (_retrieve_partner_with_vat)
partner = search_by_vat(normalized_vat)
if not found:
    # Try without country prefix but with country filter
    partner = search_by_vat(numeric_only, country=country)
    if not found:
        # Fuzzy match with leading zeros: ^{prefix}0*{numeric}$
        partner = regex_search(r'^BE0*476155272$')

# 2. Phone/Email Matching (_retrieve_partner_with_phone_mail)
partner = search([
    '|', ('phone', '=', phone), ('mobile', '=', phone),
    ('email', '=', email)
])

# 3. Name Matching (_retrieve_partner_with_name)
partner = search([('name', 'ilike', name)])

# 4. Auto-Create (if enabled)
if not partner and name and vat:
    partner = create({
        'name': name,
        'vat': vat,
        'email': email,
        'phone': phone,
        'street': street,
        'city': city,
        'country_id': country.id
    })
```

**Search Scope**:
1. Company-specific first: `company_id = current_company`
2. Global fallback: `company_id = False`

### 4. Product Matching Logic

**Priority-Based Search Strategy** (account_edi_format.py:496-531):

```python
# 1. Barcode (highest priority)
product = search([('barcode', '=', extracted_barcode)])

# 2. Supplier Code (default_code)
product = search([('default_code', '=', extracted_code)])

# 3. Name (exact)
product = search([('name', '=', extracted_name)])

# 4. Name (fuzzy - ILIKE)
product = search([('name', 'ilike', extracted_name)])
```

**Each search tries**:
1. Company-specific products first
2. Global products as fallback

### 5. Invoice Creation Workflow

**Complete Import Process** (account_edi_common.py:261-336):

```
1. Format Detection & XML Parsing
    ↓
2. Invoice Type Classification
    - in_invoice / out_invoice
    - in_refund / out_refund (credit notes)
    ↓
3. Quantity Factor Calculation
    - qty_factor = 1 (normal)
    - qty_factor = -1 (if negative amounts → convert to credit note)
    ↓
4. Invoice Header Population
    - Partner identification (via matching)
    - Currency, dates, bank details
    - References, payment terms
    ↓
5. Document-Level Allowances/Charges
    - Discounts/charges as invoice lines
    ↓
6. Line Item Processing (for each InvoiceLine)
    - Product matching
    - Price calculation (complex formula, see below)
    - Discount computation
    - UOM mapping (UNECE codes → Odoo UOMs)
    - Tax resolution
    ↓
7. Tax Amount Correction
    - Compare imported vs computed tax
    - Correct if within tolerance (±0.05)
    ↓
8. Embedded PDF Extraction (if present)
    - Attach visual invoice to record
    ↓
9. Validation & Posting
    - Log warnings/errors
    - Create draft invoice
```

### 6. Price Calculation Formula

**Peppol BIS 3.0 Calculation Rules** (account_edi_common.py:506-565):

```
Mathematical Formula:
line_net_subtotal = (gross_unit_price - rebate) × (billed_qty / basis_qty) - allow_charge_amount

Where:
- gross_unit_price = Price including item discount (BT-148)
- rebate = Item price discount amount (BT-147)
- basis_qty = Price base quantity (BT-149, default=1)
- billed_qty = Invoiced quantity (BT-129)
- allow_charge_amount = Sum of line-level allowances/charges (BT-136/BT-141)
- line_net_subtotal = Line extension amount (BT-131)
```

**Reverse Calculation for Odoo** (account_edi_common.py:566-674):

```python
# Odoo fields computation
quantity = billed_qty * qty_factor

# price_unit (three options, in order of preference)
if gross_price_unit:
    price_unit = gross_price_unit / basis_qty
elif net_price_unit:
    price_unit = (net_price_unit + rebate) / basis_qty
else:
    price_unit = (price_subtotal + allow_charge_amount) / billed_qty

# discount (percentage)
discount = 100 * (1 - (price_subtotal - fixed_taxes) / (billed_qty * price_unit))
```

---

## Current LLM-Based Implementation

### Architecture Overview

**Your System** (`account_invoice_import_llm`):

```
Invoice Upload (Any Format)
    ↓
[Mistral OCR] → Extract text from PDF/image
    ↓
[LLM Analysis] → Parse unstructured OCR text
    ↓
{ExtractedInvoiceData} (Pydantic model)
    ├─ vendor_name
    ├─ vat
    ├─ ref
    ├─ invoice_date
    ├─ lines: [{name, quantity, price_unit}, ...]
    └─ total
    ↓
[Analyzer Tool] (llm_tool_account_move_invoice_analyzer.py)
    ├─→ Duplicate Check (early exit if found)
    ├─→ Partner Matching
    │   ├─ Exact VAT match → High confidence
    │   ├─ Exact name match → Medium confidence
    │   └─ No match → Return search_hints for LLM
    │
    ├─→ Historical Pattern Analysis
    │   └─ Last 10 invoices → suggest payment terms
    │
    └─→ Product Matching (per line)
        ├─ Exact name match → Use product
        ├─ Multiple matches → Return alternatives for user
        └─ No match → Return search_hints for LLM
    ↓
[Status Determination]
    ├─→ "ready" → All matched, ready for updater
    ├─→ "needs_input" → User decision required
    ├─→ "duplicate_found" → Stop processing
    └─→ "error" → Validation failed
    ↓
[User Interaction] (if needs_input)
    ├─ Partner selection from alternatives
    ├─ Intelligent partner search via LLM
    ├─ Product selection from alternatives
    ├─ Intelligent product search via LLM
    └─ Product creation option
    ↓
[Analyzer Tool] (with constraints from user choices)
    ↓
[Status: ready]
    ↓
[Updater Tool] (llm_tool_account_move_invoice_updater.py)
    ├─→ Create invoice lines (batch)
    ├─→ Update invoice header
    └─→ Return success with totals
```

### Key Strengths

1. **Format Agnostic**
   - Handles any invoice format (no standardization required)
   - Adapts to vendor-specific layouts
   - Works with scanned/handwritten invoices

2. **Intelligent Understanding**
   - LLM parses unstructured text (excels at this!)
   - Semantic matching via search hints
   - Handles language variations, typos, abbreviations

3. **Interactive Workflow**
   - User guides ambiguous cases
   - Intelligent search with LLM assistance
   - Option to create new products for recurring items

4. **Historical Intelligence**
   - Analyzes last 10 invoices from partner
   - Suggests common payment terms
   - Learns from partner patterns

5. **Type Safety**
   - Pydantic models for all data structures
   - Runtime validation
   - Clear contracts between tools and LLM

6. **Duplicate Prevention**
   - Early-exit blocker (stops processing immediately)
   - Saves time and prevents errors

---

## Comparison: EDI vs LLM-OCR

### Feature Comparison Table

| Aspect | EDI Modules | LLM-Based OCR |
|--------|-------------|---------------|
| **Input Type** | Structured XML/PDF+XML | Unstructured text from OCR |
| **Data Extraction** | XPath queries on XML schemas | LLM parsing of raw text |
| **Reliability** | Deterministic (schema-validated) | Probabilistic (LLM-dependent) |
| **Accuracy** | 100% (if XML valid) | 95%+ (depends on OCR quality) |
| **Format Support** | Standards-compliant e-invoices only | **Any invoice format** |
| **Layout Flexibility** | Fixed (per XML schema) | **Infinite (adapts to any layout)** |
| **Language Support** | Encoding-dependent | **Multi-language via LLM** |
| **Partner Matching** | Exact VAT → fuzzy name | Exact → **intelligent search** |
| **Product Matching** | Barcode → code → name | Name → **intelligent search** |
| **User Interaction** | Minimal (auto-creates) | **Interactive (needs_input)** |
| **Historical Patterns** | None | **Yes (last 10 invoices)** |
| **Duplicate Detection** | Basic | **Early-exit blocker** |
| **Processing Speed** | Fast (direct parsing) | Slower (OCR + LLM analysis) |
| **Cost** | Low (no AI) | Higher (OCR + LLM tokens) |
| **Setup Complexity** | Medium (format configuration) | Low (works out of box) |
| **Best For** | B2B, high-volume, compliant vendors | **Heterogeneous, legacy, scanned** |

### Strengths and Weaknesses

#### EDI Strengths ✅
- **Deterministic**: 100% accuracy for valid XML
- **Fast**: Direct XML parsing, no OCR needed
- **Standardized**: Industry-proven formats
- **Automated**: Zero user intervention for known vendors
- **Cost-effective**: No AI costs

#### EDI Weaknesses ❌
- **Format-limited**: Only standards-compliant e-invoices
- **Inflexible**: Cannot handle layout variations
- **No scanned docs**: Requires digital, structured files
- **No intelligence**: Cannot understand context or variations
- **Setup overhead**: Requires format configuration

#### LLM-OCR Strengths ✅
- **Universal**: Handles **any invoice format**
- **Flexible**: Adapts to layout variations automatically
- **Intelligent**: Semantic understanding of text
- **Scanned docs**: Processes images, faxes, photos
- **Multi-language**: Understands multiple languages
- **Interactive**: User guides ambiguous cases
- **Historical learning**: Suggests based on patterns

#### LLM-OCR Weaknesses ❌
- **Probabilistic**: Not 100% accurate (OCR + LLM errors)
- **Slower**: OCR + LLM analysis takes time
- **Cost**: OCR + LLM token costs
- **Requires review**: User should validate results

---

## Partner & Product Matching Strategies

### EDI Matching (Deterministic Approach)

**Partner Matching Pipeline**:
```
1. VAT Exact Match
   ├─ Normalize: Remove whitespace
   ├─ Extract country prefix (BE, NL, etc.)
   ├─ Search: exact VAT
   └─ If not found:
       ├─ Search without country prefix
       └─ Fuzzy regex: ^{prefix}0*{numeric}$
2. Phone/Email Match
3. Name ILIKE Match
4. Auto-Create (if enabled)
```

**Product Matching Pipeline**:
```
1. Barcode Exact Match
2. Supplier Code (default_code) Exact Match
3. Product Name Exact Match
4. Product Name Fuzzy Match (ILIKE)
```

**Characteristics**:
- ✅ Fast (database queries)
- ✅ Deterministic (same input → same output)
- ✅ VAT normalization handles variations
- ❌ No semantic understanding
- ❌ Cannot handle typos, abbreviations

### LLM Matching (Intelligent Approach)

**Partner Matching Pipeline**:
```
1. Exact Matching (Analyzer Tool)
   ├─ VAT exact match (if provided)
   └─ Name exact match (case-insensitive)

2. If No Exact Match:
   ├─ Return status: "needs_input"
   ├─ question_type: "partner_search"
   └─ search_hints: {
       model: "res.partner",
       vendor_name: "Acme Corp",
       vat: "BE0123456789",
       fields_to_search: ["name", "vat", "city", "country_id"]
   }

3. LLM Intelligent Search
   ├─ Strategy 1: Remove legal entities ("Strato GmbH" → "Strato")
   ├─ Strategy 2: Remove domain extensions ("strato.nl" → "strato")
   ├─ Strategy 3: Search by VAT prefix
   ├─ Strategy 4: Partial name matching
   └─ Present matches with confidence indicators

4. User Selection
   └─ Call analyzer again with constraint
```

**Product Matching Pipeline**:
```
1. Exact Matching (Analyzer Tool)
   └─ Product name exact match

2. If Multiple Matches:
   ├─ Return status: "needs_input"
   ├─ question_type: "product_selection"
   └─ product_options: [
       {id: 123, name: "Product A", code: "PROD-A"},
       {id: 124, name: "Product A+", code: "PROD-A2"}
   ]

3. If No Match:
   ├─ Return status: "needs_input"
   ├─ question_type: "product_search"
   └─ search_hints: {
       model: "product.product",
       description: "Odoo - ING NL Accounts",
       fields_to_search: ["name", "default_code", "barcode"]
   }

4. LLM Intelligent Search
   ├─ Strategy 1: First significant word
   ├─ Strategy 2: Remove measurements ("Cable 5m" → "Cable")
   ├─ Strategy 3: Extract product codes from description
   ├─ Strategy 4: Price comparison for best match
   └─ Present 3 options:
       a. Match existing product (if found)
       b. Create new product (for recurring purchases)
       c. Manual entry (for one-time expenses)
```

**Characteristics**:
- ✅ Semantic understanding (handles typos, variations)
- ✅ Context-aware (analyzes description, not just keywords)
- ✅ Interactive (user validates matches)
- ✅ Flexible (adapts to edge cases)
- ❌ Slower (LLM analysis required)
- ❌ Requires user interaction for ambiguous cases

---

## Use Case Analysis

### When to Use EDI

**Ideal Scenarios**:
- ✅ **B2B Invoicing**: Established relationships with suppliers using e-invoicing
- ✅ **High Volume**: Processing hundreds/thousands of invoices from same vendors
- ✅ **Standards-Compliant**: Vendors send UBL, Factur-X, PEPPOL invoices
- ✅ **Government Mandates**: Countries requiring e-invoicing (France, Italy, etc.)
- ✅ **Automated Workflows**: No manual intervention desired
- ✅ **Guaranteed Accuracy**: Schema validation ensures data integrity

**Example Vendors**:
- Major suppliers with e-invoicing capability
- Cloud service providers (AWS, Azure, Google Cloud)
- Large utilities (electricity, internet, telecom)
- Government agencies (e-government portals)

### When to Use LLM-Based OCR

**Ideal Scenarios**:
- ✅ **Heterogeneous Vendors**: Different layouts per vendor
- ✅ **Legacy Vendors**: No e-invoicing capability (send PDFs)
- ✅ **Scanned Invoices**: Physical mail, faxes, email attachments
- ✅ **Variable Formats**: Vendors change invoice layouts over time
- ✅ **Multi-Language**: Invoices in different languages
- ✅ **Complex Scenarios**: Similar vendor names, branch variations
- ✅ **Interactive Workflows**: User validation desired
- ✅ **Small/Medium Volume**: Cost-effective for 10-100 invoices/month

**Example Vendors**:
- Small local suppliers (restaurants, office supplies, contractors)
- International vendors (varying invoice standards)
- Rental companies, travel agencies, hotels
- Freelancers, consultants

### Complementary Use Cases

**Scenario 1: Mixed Vendor Base**
```
Large Supplier (e-invoicing) → Use EDI (fast, automated)
Small Local Vendors → Use LLM-OCR (flexible, handles scans)
```

**Scenario 2: Format Evolution**
```
Vendor starts: PDF invoices → LLM-OCR
Vendor upgrades: UBL e-invoices → Switch to EDI
```

**Scenario 3: Validation Layer**
```
EDI parsing → Validate totals with LLM
LLM extraction → Validate structure with EDI schemas
```

---

## Integration Opportunities

### Option 1: Keep Systems Separate ⭐ (Current Recommendation)

**Approach**: No integration - systems serve different purposes

**When to Use**:
- E-invoice volume < 10%
- Mostly unstructured PDFs
- Different vendor bases for each system

**Benefits**:
- ✅ Zero risk
- ✅ No development effort
- ✅ Systems work independently
- ✅ Clear separation of concerns

**Implementation**: None required

---

### Option 2: EDI Pre-Check Before OCR

**Approach**: Try EDI first, fallback to LLM-OCR if fails

**Workflow**:
```
Invoice Upload
    ↓
[Format Detection]
    ├─→ XML detected? → Try EDI parsing
    ├─→ PDF with embedded XML? → Try EDI parsing
    └─→ Regular PDF/Image? → Use LLM-OCR
    ↓
If EDI succeeds:
    - Use extracted data (skip OCR)
    - Higher confidence

If EDI fails:
    - Fallback to LLM-OCR
    - Log fallback for analysis
```

**When to Use**:
- E-invoice volume 10-30%
- Want faster processing for structured invoices
- Willing to add routing logic

**Changes Required**:
1. Add format detection before OCR step
2. Extract data via EDI if XML detected
3. Pass EDI-extracted data to analyzer (skip OCR)
4. Update system prompt with routing logic

**Files to Modify**:
- `llm_assistant_data.xml` - System prompt (routing instructions)
- Analyzer tool - Accept data from EDI or OCR source

**Benefits**:
- ✅ Faster for e-invoices (skip OCR)
- ✅ Higher accuracy for structured formats
- ✅ Graceful fallback to LLM
- ✅ Low risk (additive change)

**Risks**:
- ⚠️ Additional complexity
- ⚠️ Need to handle both data formats

---

### Option 3: Unified Matching Logic

**Approach**: Combine EDI's exact matching with LLM's intelligence

**Partner Matching Fusion**:
```python
# EDI's strength: VAT normalization and fuzzy regex
if extracted_vat:
    partner = edi_vat_match(vat)  # Handles normalization, leading zeros
    if partner:
        return partner  # High confidence

# LLM's strength: Semantic understanding
search_hints = create_partner_search_hints(vendor_name, vat)
return llm_intelligent_search(search_hints)
```

**Product Matching Fusion**:
```python
# Extract supplier codes from OCR text (learn from EDI)
supplier_code = extract_supplier_code(ocr_description)

# EDI's strength: Exact code matching
if supplier_code or barcode:
    product = edi_exact_match(supplier_code, barcode)
    if product:
        return product

# LLM's strength: Description understanding
search_hints = create_product_search_hints(description)
return llm_intelligent_search(search_hints)
```

**When to Use**:
- Want best-of-both-worlds matching
- Experiencing matching accuracy issues
- Willing to extract EDI logic

**Changes Required**:
1. Extract VAT normalization from EDI (`account_edi_format.py:389-494`)
2. Add to analyzer's `_match_partner()` method
3. Extract product code matching from EDI
4. Add supplier_code extraction to OCR parsing

**Files to Modify**:
- `llm_tool_account_move_invoice_analyzer.py` - Matching methods
- `invoice_tool_types.py` - Add supplier_code to ProductSearchHints

**Benefits**:
- ✅ Better exact matching (VAT regex, normalization)
- ✅ Reduced LLM calls for common cases
- ✅ Learn from EDI's battle-tested logic
- ✅ Keep LLM fallback for edge cases

**Risks**:
- ⚠️ Medium complexity
- ⚠️ Need to maintain EDI logic copy

---

### Option 4: Full Hybrid System

**Approach**: Complete integration with routing, confidence scoring, learning loop

**Architecture**:
```
Invoice Upload
    ↓
[Intelligent Router]
    ├─ Format detection
    ├─ Vendor profiling (historical data)
    └─ Route to optimal path
    ↓
[Dual Processing]
    ├─→ EDI Path (for structured)
    │   └─ Extract via XPath
    └─→ OCR Path (for unstructured)
        └─ Extract via LLM
    ↓
[Confidence Scoring]
    ├─ EDI: High confidence (schema-validated)
    ├─ LLM: Variable confidence (probabilistic)
    └─ Fusion: Combine if both available
    ↓
[Unified Result Format]
    └─ Same structure regardless of source
    ↓
[Learning Loop]
    ├─ Track which path users validate
    ├─ Improve routing over time
    └─ Suggest vendor e-invoice adoption
```

**When to Use**:
- E-invoice volume > 30%
- Need maximum automation **and** flexibility
- Willing to invest in architecture changes

**Changes Required**:
1. Create routing module (format detection + vendor profiling)
2. Dual-path processing (EDI + OCR in parallel)
3. Confidence scoring system
4. Unified result format (merge EDI + LLM data structures)
5. Learning loop (track validations, improve routing)

**Files to Create/Modify**:
- New: `llm_tool_invoice_router.py` - Intelligent routing
- Modify: Analyzer tool - Support both data sources
- Modify: `llm_assistant_data.xml` - Dual-path instructions
- New: Confidence tracking model

**Benefits**:
- ✅ Maximum automation for e-invoices
- ✅ Maximum flexibility for legacy invoices
- ✅ Continuous improvement via feedback
- ✅ Future-proof (handles e-invoice adoption)

**Risks**:
- ⚠️ High complexity
- ⚠️ Significant development effort
- ⚠️ Need to maintain both systems

---

## Technical Implementation Details

### EDI Processing Flow

**File Path**: `/src/odoo/addons/account_edi/models/account_edi_format.py`

```python
# Entry Point (line 186-215)
def _create_document_from_attachment(attachment):
    """Create invoice from attachment"""

    # Step 1: Decode attachment by type
    decoded_files = _decode_attachment(attachment)  # XML, PDF, Binary

    # Step 2: For each decoded file
    for decoded in decoded_files:
        if decoded['type'] == 'xml':
            invoice = _create_invoice_from_xml_tree(
                filename=decoded['filename'],
                tree=decoded['xml_tree'],
                journal=journal
            )
        elif decoded['type'] == 'pdf':
            invoice = _create_invoice_from_pdf_reader(
                filename=decoded['filename'],
                reader=decoded['pdf_reader']
            )
        # ...

    # Step 3: Link to purchase orders (4 second timeout)
    _link_invoice_origin_to_purchase_orders(timeout=4)

    return invoice
```

**Key Methods**:

| Method | Line | Purpose |
|--------|------|---------|
| `_decode_attachment()` | 142 | Detect file type, decode content |
| `_decode_xml()` | 108 | Parse XML with lxml.etree |
| `_decode_pdf()` | 115 | Extract PDF + embedded XMLs |
| `_retrieve_partner()` | 389 | VAT/phone/email/name matching |
| `_retrieve_product()` | 496 | Barcode/code/name matching |
| `_retrieve_tax()` | 533 | Tax matching by percentage |

### LLM Processing Flow

**File Path**: `/extra-addons/.src/apexive/odoo-llm/account_invoice_import_llm/models/llm_tool_account_move_invoice_analyzer.py`

```python
# Entry Point (line 191-228)
def account_move_invoice_analyzer_execute(
    invoice_id: int,
    extracted_data: ExtractedInvoiceData,
    constraints: Optional[AnalyzerConstraints] = None
) -> dict:
    """Analyze invoice data and match partners/products"""

    # Step 1: Duplicate check (early exit)
    duplicate = _check_duplicate(invoice_id, extracted_data)
    if duplicate:
        return _duplicate_response(duplicate)

    # Step 2: Partner matching
    partner_result = _match_partner(extracted_data, constraints)
    if partner_result['needs_decision'] or partner_result['needs_search']:
        return _needs_input_response(partner_result)

    # Step 3: Historical pattern analysis
    patterns = _analyze_partner_history(partner_result['partner'])

    # Step 4: Product matching (per line)
    product_results = [
        _match_single_product(line, constraints)
        for line in extracted_data['lines']
    ]

    if any(r['needs_decision'] or r['needs_search'] for r in product_results):
        return _needs_input_response(product_results[0])

    # Step 5: Build complete invoice lines
    lines = _build_invoice_lines(extracted_data['lines'], product_results)

    # Step 6: Return ready status
    return _ready_response(partner, lines, patterns)
```

**Key Methods**:

| Method | Line | Purpose |
|--------|------|---------|
| `_check_duplicate()` | 270 | Partner + ref matching |
| `_match_partner()` | 430 | Exact VAT/name, return search hints |
| `_analyze_partner_history()` | 348 | Last 10 invoices analysis |
| `_match_single_product()` | 560 | Exact name, return search hints/alternatives |
| `_build_invoice_lines()` | 629 | Combine OCR + product data |

### Key Differences in Code

**EDI (Imperative)**:
```python
# Direct database queries, immediate results
partner = self.env['res.partner'].search([('vat', '=', vat)], limit=1)
if not partner:
    partner = self.env['res.partner'].create({'name': name, 'vat': vat})
```

**LLM (Declarative)**:
```python
# Return search hints, let LLM search intelligently
if not partner:
    return {
        'status': 'needs_input',
        'question_type': 'partner_search',
        'search_hints': PartnerSearchHints(
            vendor_name=name,
            vat=vat
        ).model_dump()
    }
```

---

## Recommendations

### Current Recommendation (Based on Analysis)

**Your Situation**:
- ✅ Goal: Understand EDI capabilities (**COMPLETE**)
- ✅ Vendor Profile: 0-10% e-invoices, 90%+ unstructured PDFs
- ✅ System: LLM-based OCR working well

**Recommendation**: **Keep systems separate (Option 1)**

**Action**: **No changes needed**

### Rationale

1. **LLM-based approach is optimal for your use case**
   - Handles 90%+ of your invoices (unstructured PDFs)
   - Excels at the hard problem (scanned docs, varying layouts)
   - EDI would only help with 0-10% of invoices

2. **Integration would add complexity without significant benefit**
   - Development effort not justified for <10% volume
   - Maintenance overhead for minimal gain
   - Current system already handles structured invoices (via OCR)

3. **Your current implementation is well-designed**
   - Type-safe Pydantic models ✅
   - Intelligent fuzzy matching ✅
   - Historical pattern analysis ✅
   - Duplicate detection ✅
   - Interactive workflow ✅

### Future Considerations

**Monitor E-Invoice Adoption**:
- If e-invoice volume increases to >30%, revisit Option 2 (EDI pre-check)
- Track vendor adoption of UBL, Factur-X, PEPPOL standards
- Suggest e-invoicing to major suppliers for automation

**Optional Learning Opportunities** (low priority):

1. **VAT Normalization** (from EDI)
   ```python
   # Extract from account_edi_format.py:389-494
   def normalize_vat(vat: str) -> tuple[str, str]:
       """Normalize VAT: extract country + numeric part"""
       vat = vat.replace(' ', '').upper()
       country = vat[:2] if vat[:2].isalpha() else ''
       numeric = vat[2:] if country else vat
       return country, numeric
   ```

2. **Supplier Code Extraction** (for product matching)
   ```python
   # Add to OCR parsing
   def extract_supplier_code(description: str) -> Optional[str]:
       """Extract supplier code from product description"""
       # Pattern: "Product Name [CODE-123]"
       match = re.search(r'\[([A-Z0-9-]+)\]', description)
       return match.group(1) if match else None
   ```

3. **Tax Validation** (from EDI)
   ```python
   # Compare OCR total vs computed total
   def validate_tax_amount(ocr_total: float, computed_total: float) -> bool:
       """Check if tax amounts match within tolerance"""
       tolerance = 0.05
       return abs(ocr_total - computed_total) <= tolerance
   ```

### Decision Tree

```
Do you have >10% e-invoice volume?
    ├─→ No → Keep systems separate (Option 1) ⭐
    │
    └─→ Yes → Do you have >30% e-invoice volume?
            ├─→ No → Add EDI pre-check (Option 2)
            │
            └─→ Yes → Need maximum automation?
                    ├─→ No → Unified matching (Option 3)
                    └─→ Yes → Full hybrid (Option 4)
```

---

## References

### EDI Module Files

**Base Framework**:
- `account_edi/models/account_edi_format.py`
  - Partner matching: lines 389-494
  - Product matching: lines 496-531
  - File decoding: lines 108-180
  - Invoice creation: lines 186-215

- `account_edi/models/account_edi_document.py`
  - State machine: lines 30-80
  - Batch processing: lines 120-200

**UBL/CII Parsers**:
- `account_edi_ubl_cii/models/account_edi_common.py`
  - Partner creation: lines 338-351
  - Price calculation: lines 506-674
  - Tax resolution: lines 393-465

- `account_edi_ubl_cii/models/account_edi_xml_ubl_20.py`
  - UBL parsing: lines 607-768
  - Bank details: lines 652-658

- `account_edi_ubl_cii/models/account_edi_xml_cii_facturx.py`
  - CII parsing: lines 243-251

### LLM System Files

**Tools**:
- `account_invoice_import_llm/models/llm_tool_account_move_invoice_analyzer.py`
  - Partner matching: lines 430-504
  - Product matching: lines 560-627
  - Duplicate check: lines 270-302
  - Historical patterns: lines 348-390

- `account_invoice_import_llm/models/llm_tool_account_move_invoice_updater.py`
  - Invoice creation: lines 129-216
  - Line preparation: lines 66-104

**Type Definitions**:
- `account_invoice_import_llm/models/invoice_tool_types.py`
  - ExtractedInvoiceData: lines 25-34
  - AnalyzerConstraints: lines 61-66
  - AnalyzerResponse: lines 303-341
  - InvoiceUpdateData: lines 349-358
  - SearchHints: lines 200-233

**System Prompt**:
- `account_invoice_import_llm/data/llm_assistant_data.xml`
  - Workflow instructions: line 20
  - Tool descriptions: lines 26-33

### Related Documentation

- `V2_IMPLEMENTATION_SUMMARY.md` - V2 tools design (type-safe, consistent responses)
- `TOOL_REDESIGN.md` - Tool architecture and design principles
- `INTELLIGENT_SEARCH.md` - Search hints and LLM intelligent searching
- `SYSTEM_PROMPT_SEARCH.md` - Search strategies in system prompt

---

## Conclusion

The Odoo EDI modules are **specialized tools** for structured electronic invoices (XML-based standards). Your LLM-based OCR system is a **general-purpose solution** for unstructured invoices (PDF scans, images, varying layouts).

**Key Takeaways**:

1. **Complementary Systems**: EDI handles easy cases (structured), LLM handles hard cases (unstructured)
2. **No Integration Needed**: For 0-10% e-invoice volume, keep systems separate
3. **LLM Excels**: Your implementation is optimal for heterogeneous, scanned invoices
4. **Future-Proof**: Monitor e-invoice adoption, revisit integration if volume increases

**Your system is well-designed for your use case. No action required.**

---

*Analysis Date: 2026-01-01*
*Status: Complete - Documentation archived for future reference*
