# UBL XML Paths Reference for Invoice Import

## Summary

Complete reference of all UBL 2.0 XML paths used by Odoo EDI to import invoice data. Use this to build correct UBL XML from LLM-extracted JSON.

**Source**: `/src/odoo/addons/account_edi_ubl_cii/models/account_edi_xml_ubl_20.py`

---

## XML Namespaces

```python
ns = {
    None: 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
}
```

**Note**: `{*}` in XPath means "any namespace" - Odoo uses this for flexibility.

---

## Document Level Fields

### 1. Partner Information (Supplier/Customer)

**Location**: Lines 607-621

**Role**: "Supplier" for vendor bills, "Customer" for sales invoices

| Odoo Field | UBL XPath | Example Value |
|------------|-----------|---------------|
| `partner_id.vat` | `.//cac:AccountingSupplierParty/cac:Party//cbc:CompanyID` | `BE0123456789` |
| `partner_id.phone` | `.//cac:AccountingSupplierParty/cac:Party//cbc:Telephone` | `+32 2 123 45 67` |
| `partner_id.email` | `.//cac:AccountingSupplierParty/cac:Party//cbc:ElectronicMail` | `info@supplier.com` |
| `partner_id.name` | `.//cac:AccountingSupplierParty/cac:Party//cbc:Name`<br>or `.//cac:AccountingSupplierParty/cac:Party//cbc:RegistrationName` | `Supplier Inc.` |
| `partner_id.country_id` | `.//cac:AccountingSupplierParty/cac:Party//cac:Country//cbc:IdentificationCode` | `BE` |
| `partner_id.street` | `.//cac:AccountingSupplierParty/cac:Party//cbc:StreetName` | `Main Street 123` |
| `partner_id.street2` | `.//cac:AccountingSupplierParty/cac:Party//cbc:AdditionalStreetName` | `Building A` |
| `partner_id.city` | `.//cac:AccountingSupplierParty/cac:Party//cbc:CityName` | `Brussels` |
| `partner_id.zip` | `.//cac:AccountingSupplierParty/cac:Party//cbc:PostalZone` | `1000` |

**XML Structure**:
```xml
<cac:AccountingSupplierParty>
  <cac:Party>
    <cac:PartyName>
      <cbc:Name>Supplier Inc.</cbc:Name>
    </cac:PartyName>
    <cac:PostalAddress>
      <cbc:StreetName>Main Street 123</cbc:StreetName>
      <cbc:AdditionalStreetName>Building A</cbc:AdditionalStreetName>
      <cbc:CityName>Brussels</cbc:CityName>
      <cbc:PostalZone>1000</cbc:PostalZone>
      <cac:Country>
        <cbc:IdentificationCode>BE</cbc:IdentificationCode>
      </cac:Country>
    </cac:PostalAddress>
    <cac:PartyTaxScheme>
      <cbc:CompanyID>BE0123456789</cbc:CompanyID>
    </cac:PartyTaxScheme>
    <cac:Contact>
      <cbc:Telephone>+32 2 123 45 67</cbc:Telephone>
      <cbc:ElectronicMail>info@supplier.com</cbc:ElectronicMail>
    </cac:Contact>
  </cac:Party>
</cac:AccountingSupplierParty>
```

---

### 2. Currency

**Location**: Line 625

| Odoo Field | UBL XPath | Example Value |
|------------|-----------|---------------|
| `currency_id` | `./{*}DocumentCurrencyCode` | `EUR` |

**XML Structure**:
```xml
<cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>
```

---

### 3. Invoice Date

**Location**: Line 640

| Odoo Field | UBL XPath | Example Value |
|------------|-----------|---------------|
| `invoice_date` | `./{*}IssueDate` | `2024-01-15` |

**XML Structure**:
```xml
<cbc:IssueDate>2024-01-15</cbc:IssueDate>
```

**Format**: `YYYY-MM-DD` (ISO 8601 date)

---

### 4. Due Date

**Location**: Lines 646-650

| Odoo Field | UBL XPath (tried in order) | Example Value |
|------------|----------------------------|---------------|
| `invoice_date_due` | `./{*}DueDate`<br>or `.//{ *}PaymentDueDate` | `2024-02-14` |

**XML Structure** (Option 1):
```xml
<cbc:DueDate>2024-02-14</cbc:DueDate>
```

**XML Structure** (Option 2):
```xml
<cac:PaymentMeans>
  <cbc:PaymentDueDate>2024-02-14</cbc:PaymentDueDate>
</cac:PaymentMeans>
```

---

### 5. Bank Details

**Location**: Lines 654-658

| Odoo Field | UBL XPath | Example Value |
|------------|-----------|---------------|
| `partner_bank_id` | `.//{ *}PaymentMeans/{*}PayeeFinancialAccount/{*}ID` | `BE68539007547034` |

**XML Structure**:
```xml
<cac:PaymentMeans>
  <cac:PayeeFinancialAccount>
    <cbc:ID>BE68539007547034</cbc:ID>
  </cac:PayeeFinancialAccount>
</cac:PaymentMeans>
```

---

### 6. Invoice Reference/Number

**Location**: Lines 662-667

| Odoo Field | UBL XPath | Example Value |
|------------|-----------|---------------|
| `ref` (vendor bill)<br>or `name` (sales invoice) | `./{*}ID` | `INV-2024-001` |

**XML Structure**:
```xml
<cbc:ID>INV-2024-001</cbc:ID>
```

---

### 7. Purchase Order Reference

**Location**: Lines 671-673

| Odoo Field | UBL XPath | Example Value |
|------------|-----------|---------------|
| `invoice_origin` | `./{*}OrderReference/{*}ID` | `PO-2024-123` |

**XML Structure**:
```xml
<cac:OrderReference>
  <cbc:ID>PO-2024-123</cbc:ID>
</cac:OrderReference>
```

---

### 8. Notes/Narration

**Location**: Lines 677-686

| Odoo Field | UBL XPath | Example Value |
|------------|-----------|---------------|
| `narration` | `./{*}Note`<br>and `./{*}PaymentTerms/{*}Note` | `Payment within 30 days` |

**XML Structure**:
```xml
<cbc:Note>Thank you for your business</cbc:Note>
<cac:PaymentTerms>
  <cbc:Note>Payment within 30 days, 2% discount within 10 days</cbc:Note>
</cac:PaymentTerms>
```

---

### 9. Payment Reference

**Location**: Lines 690-692

| Odoo Field | UBL XPath | Example Value |
|------------|-----------|---------------|
| `payment_reference` | `./{*}PaymentMeans/{*}PaymentID` | `+++123/4567/89012+++` |

**XML Structure**:
```xml
<cac:PaymentMeans>
  <cbc:PaymentID>+++123/4567/89012+++</cbc:PaymentID>
</cac:PaymentMeans>
```

---

### 10. Incoterm

**Location**: Lines 696-700

| Odoo Field | UBL XPath | Example Value |
|------------|-----------|---------------|
| `invoice_incoterm_id` | `./{*}TransportExecutionTerms/{*}DeliveryTerms/{*}ID` | `EXW` |

**XML Structure**:
```xml
<cac:TransportExecutionTerms>
  <cac:DeliveryTerms>
    <cbc:ID>EXW</cbc:ID>
  </cac:DeliveryTerms>
</cac:TransportExecutionTerms>
```

---

### 11. Prepaid Amount

**Location**: Line 708

| Odoo Field | UBL XPath | Example Value |
|------------|-----------|---------------|
| N/A (logged only) | `./{*}LegalMonetaryTotal/{*}PrepaidAmount` | `500.00` |

**XML Structure**:
```xml
<cac:LegalMonetaryTotal>
  <cbc:PrepaidAmount currencyID="EUR">500.00</cbc:PrepaidAmount>
</cac:LegalMonetaryTotal>
```

---

## Invoice Line Fields

**Root**: `./{*}InvoiceLine` (for invoices) or `./{*}CreditNoteLine` (for credit notes)

**Location**: Lines 721-768

### 1. Product Identification

**Location**: Lines 726-732

| Odoo Field | UBL XPath | Example Value |
|------------|-----------|---------------|
| `product_id` (by code) | `./cac:Item/cac:SellersItemIdentification/cbc:ID` | `PROD-001` |
| `product_id` (by name) | `./cac:Item/cbc:Name` | `Web Development Services` |
| `product_id` (by barcode) | `./cac:Item/cac:StandardItemIdentification/cbc:ID[@schemeID='0160']` | `5412345678901` |

**XML Structure**:
```xml
<cac:InvoiceLine>
  <cac:Item>
    <cbc:Name>Web Development Services</cbc:Name>
    <cac:SellersItemIdentification>
      <cbc:ID>PROD-001</cbc:ID>
    </cac:SellersItemIdentification>
    <cac:StandardItemIdentification>
      <cbc:ID schemeID="0160">5412345678901</cbc:ID>
    </cac:StandardItemIdentification>
  </cac:Item>
</cac:InvoiceLine>
```

**Note**: Odoo tries to match product by:
1. `default_code` (seller's ID)
2. `barcode` (standard ID with schemeID='0160')
3. `name` (product name)

---

### 2. Line Description/Name

**Location**: Lines 735-740

| Odoo Field | UBL XPath (priority order) | Example Value |
|------------|----------------------------|---------------|
| `name` | `./{ *}Item/{*}Description`<br>or `./{*}Item/{*}Name` (fallback) | `Consulting services for Q1 2024` |

**XML Structure** (preferred):
```xml
<cac:Item>
  <cbc:Description>Consulting services for Q1 2024</cbc:Description>
  <cbc:Name>Consulting</cbc:Name>
</cac:Item>
```

---

### 3. Quantity

**Location**: Line 749

| Odoo Field | UBL XPath | Example Value |
|------------|-----------|---------------|
| `quantity` | `./{*}InvoicedQuantity` (for invoices)<br>or `./{*}CreditedQuantity` (for credit notes) | `10.00` |

**XML Structure**:
```xml
<cbc:InvoicedQuantity unitCode="C62">10.00</cbc:InvoicedQuantity>
```

**Common Unit Codes**:
- `C62`: Unit/Piece (items)
- `HUR`: Hour
- `DAY`: Day
- `MTR`: Meter
- `KGM`: Kilogram

---

### 4. Price

**Location**: Lines 743-748

| Odoo Field | UBL XPath | Example Value |
|------------|-----------|---------------|
| `price_unit` | `./{*}Price/{*}PriceAmount` | `100.00` |
| Base quantity | `./{*}Price/{*}BaseQuantity` | `1.00` |
| Gross price (before discount) | `./{*}Price/{*}AllowanceCharge/{*}BaseAmount` | `110.00` |
| Discount amount | `./{*}Price/{*}AllowanceCharge/{*}Amount` | `10.00` |

**XML Structure**:
```xml
<cac:Price>
  <cbc:PriceAmount currencyID="EUR">100.00</cbc:PriceAmount>
  <cbc:BaseQuantity unitCode="C62">1.00</cbc:BaseQuantity>
  <!-- Optional discount info -->
  <cac:AllowanceCharge>
    <cbc:BaseAmount currencyID="EUR">110.00</cbc:BaseAmount>
    <cbc:Amount currencyID="EUR">10.00</cbc:Amount>
  </cac:AllowanceCharge>
</cac:Price>
```

---

### 5. Line Total (Subtotal)

**Location**: Line 755

| Odoo Field | UBL XPath | Example Value |
|------------|-----------|---------------|
| Computed from qty × price | `./{*}LineExtensionAmount` | `1000.00` |

**XML Structure**:
```xml
<cbc:LineExtensionAmount currencyID="EUR">1000.00</cbc:LineExtensionAmount>
```

**Formula**: `Quantity × PriceAmount = LineExtensionAmount`

---

### 6. Taxes

**Location**: Lines 761-767

**Multiple possible locations (tried in order)**:

| Odoo Field | UBL XPath (priority order) | Example Value |
|------------|----------------------------|---------------|
| `tax_ids` (by %) | `.//{ *}Item/{*}ClassifiedTaxCategory/{*}Percent`<br>or `.//{ *}TaxTotal/{*}TaxSubtotal/{*}TaxCategory/{*}Percent`<br>or `.//{ *}TaxTotal/{*}TaxSubtotal/{*}Percent` | `21.00` |

**XML Structure** (Option 1 - Most common):
```xml
<cac:InvoiceLine>
  <cac:Item>
    <cac:ClassifiedTaxCategory>
      <cbc:Percent>21.00</cbc:Percent>
      <cac:TaxScheme>
        <cbc:ID>VAT</cbc:ID>
      </cac:TaxScheme>
    </cac:ClassifiedTaxCategory>
  </cac:Item>
</cac:InvoiceLine>
```

**XML Structure** (Option 2 - TaxTotal):
```xml
<cac:TaxTotal>
  <cac:TaxSubtotal>
    <cbc:Percent>21.00</cbc:Percent>
    <cbc:TaxAmount currencyID="EUR">210.00</cbc:TaxAmount>
    <cac:TaxCategory>
      <cbc:ID>S</cbc:ID>
      <cbc:Percent>21.00</cbc:Percent>
      <cac:TaxScheme>
        <cbc:ID>VAT</cbc:ID>
      </cac:TaxScheme>
    </cac:TaxCategory>
  </cac:TaxSubtotal>
</cac:TaxTotal>
```

**Note**: Odoo matches taxes by percentage, not by ID!

---

### 7. Line-Level Allowance/Charge (Discount)

**Location**: Lines 750-754

| Purpose | UBL XPath | Example Value |
|---------|-----------|---------------|
| Discount/charge nodes | `.//{ *}AllowanceCharge` | (multiple nodes) |
| Is it a charge? | `./{*}ChargeIndicator` | `false` (discount) or `true` (charge) |
| Amount | `./{*}Amount` | `50.00` |
| Reason | `./{*}AllowanceChargeReason` | `Volume discount` |
| Reason code | `./{*}AllowanceChargeReasonCode` | `95` |

**XML Structure**:
```xml
<cac:AllowanceCharge>
  <cbc:ChargeIndicator>false</cbc:ChargeIndicator>
  <cbc:AllowanceChargeReasonCode>95</cbc:AllowanceChargeReasonCode>
  <cbc:AllowanceChargeReason>Volume discount</cbc:AllowanceChargeReason>
  <cbc:Amount currencyID="EUR">50.00</cbc:Amount>
</cac:AllowanceCharge>
```

---

## Document Totals

**Location**: Lines 805-806, 774-792

### LegalMonetaryTotal

| Odoo Field | UBL XPath | Example Value |
|------------|-----------|---------------|
| Total excluding tax | `./{*}LegalMonetaryTotal/{*}TaxExclusiveAmount` | `1000.00` |
| Total including tax | `./{*}LegalMonetaryTotal/{*}TaxInclusiveAmount` | `1210.00` |
| Payable amount | `./{*}LegalMonetaryTotal/{*}PayableAmount` | `1210.00` |
| Prepaid amount | `./{*}LegalMonetaryTotal/{*}PrepaidAmount` | `0.00` |

**XML Structure**:
```xml
<cac:LegalMonetaryTotal>
  <cbc:LineExtensionAmount currencyID="EUR">1000.00</cbc:LineExtensionAmount>
  <cbc:TaxExclusiveAmount currencyID="EUR">1000.00</cbc:TaxExclusiveAmount>
  <cbc:TaxInclusiveAmount currencyID="EUR">1210.00</cbc:TaxInclusiveAmount>
  <cbc:PayableAmount currencyID="EUR">1210.00</cbc:PayableAmount>
</cac:LegalMonetaryTotal>
```

---

### TaxTotal

| Odoo Field | UBL XPath | Example Value |
|------------|-----------|---------------|
| Total tax amount | `./{*}TaxTotal/{*}TaxAmount` | `210.00` |
| Tax by category | `./{*}TaxTotal/{*}TaxSubtotal/{*}TaxAmount` | `210.00` |
| Tax percentage | `./{*}TaxTotal/{*}TaxSubtotal/{*}TaxCategory/{*}Percent` | `21.00` |

**XML Structure**:
```xml
<cac:TaxTotal>
  <cbc:TaxAmount currencyID="EUR">210.00</cbc:TaxAmount>
  <cac:TaxSubtotal>
    <cbc:TaxableAmount currencyID="EUR">1000.00</cbc:TaxableAmount>
    <cbc:TaxAmount currencyID="EUR">210.00</cbc:TaxAmount>
    <cac:TaxCategory>
      <cbc:ID>S</cbc:ID>
      <cbc:Percent>21.00</cbc:Percent>
      <cac:TaxScheme>
        <cbc:ID>VAT</cbc:ID>
      </cac:TaxScheme>
    </cac:TaxCategory>
  </cac:TaxSubtotal>
</cac:TaxTotal>
```

---

## Complete Minimal UBL Invoice Example

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">

  <!-- Invoice Reference -->
  <cbc:ID>INV-2024-001</cbc:ID>

  <!-- Invoice Date -->
  <cbc:IssueDate>2024-01-15</cbc:IssueDate>

  <!-- Due Date -->
  <cbc:DueDate>2024-02-14</cbc:DueDate>

  <!-- Currency -->
  <cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>

  <!-- Supplier -->
  <cac:AccountingSupplierParty>
    <cac:Party>
      <cac:PartyName>
        <cbc:Name>Supplier Inc.</cbc:Name>
      </cac:PartyName>
      <cac:PartyTaxScheme>
        <cbc:CompanyID>BE0123456789</cbc:CompanyID>
      </cac:PartyTaxScheme>
    </cac:Party>
  </cac:AccountingSupplierParty>

  <!-- Invoice Line -->
  <cac:InvoiceLine>
    <cbc:ID>1</cbc:ID>
    <cbc:InvoicedQuantity unitCode="C62">10.00</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount currencyID="EUR">1000.00</cbc:LineExtensionAmount>

    <cac:Item>
      <cbc:Description>Web Development Services</cbc:Description>
      <cbc:Name>Web Development</cbc:Name>
      <cac:ClassifiedTaxCategory>
        <cbc:Percent>21.00</cbc:Percent>
        <cac:TaxScheme>
          <cbc:ID>VAT</cbc:ID>
        </cac:TaxScheme>
      </cac:ClassifiedTaxCategory>
    </cac:Item>

    <cac:Price>
      <cbc:PriceAmount currencyID="EUR">100.00</cbc:PriceAmount>
    </cac:Price>
  </cac:InvoiceLine>

  <!-- Tax Total -->
  <cac:TaxTotal>
    <cbc:TaxAmount currencyID="EUR">210.00</cbc:TaxAmount>
    <cac:TaxSubtotal>
      <cbc:TaxableAmount currencyID="EUR">1000.00</cbc:TaxableAmount>
      <cbc:TaxAmount currencyID="EUR">210.00</cbc:TaxAmount>
      <cac:TaxCategory>
        <cbc:ID>S</cbc:ID>
        <cbc:Percent>21.00</cbc:Percent>
        <cac:TaxScheme>
          <cbc:ID>VAT</cbc:ID>
        </cac:TaxScheme>
      </cac:TaxCategory>
    </cac:TaxSubtotal>
  </cac:TaxTotal>

  <!-- Monetary Totals -->
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="EUR">1000.00</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount currencyID="EUR">1000.00</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount currencyID="EUR">1210.00</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount currencyID="EUR">1210.00</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>

</Invoice>
```

---

## Field Priority Summary

### Required Fields (Minimum for valid invoice)

1. **Invoice Reference**: `cbc:ID`
2. **Invoice Date**: `cbc:IssueDate`
3. **Currency**: `cbc:DocumentCurrencyCode`
4. **Supplier**: `cac:AccountingSupplierParty/cac:Party/cac:PartyName/cbc:Name`
5. **At least one line**: `cac:InvoiceLine`
6. **Line quantity**: `cbc:InvoicedQuantity`
7. **Line price**: `cac:Price/cbc:PriceAmount`
8. **Line total**: `cbc:LineExtensionAmount`
9. **Tax total**: `cac:TaxTotal/cbc:TaxAmount`
10. **Monetary totals**: `cac:LegalMonetaryTotal`

### Highly Recommended Fields

1. **Supplier VAT**: `cac:PartyTaxScheme/cbc:CompanyID`
2. **Due Date**: `cbc:DueDate`
3. **Line description**: `cac:Item/cbc:Description` or `cac:Item/cbc:Name`
4. **Tax percentage**: `cac:ClassifiedTaxCategory/cbc:Percent`

### Optional But Useful Fields

1. **Purchase Order Reference**: `cac:OrderReference/cbc:ID`
2. **Payment Reference**: `cac:PaymentMeans/cbc:PaymentID`
3. **Bank Account**: `cac:PaymentMeans/cac:PayeeFinancialAccount/cbc:ID`
4. **Supplier Address**: Street, City, Postal Code, Country
5. **Product Code**: `cac:Item/cac:SellersItemIdentification/cbc:ID`

---

## Notes for JSON → UBL Conversion

1. **All amounts must have `currencyID` attribute**
2. **All quantities must have `unitCode` attribute** (default: `C62` for items)
3. **Dates must be in `YYYY-MM-DD` format**
4. **Tax percentages are decimals** (21% = `21.00`, not `0.21`)
5. **VAT numbers should include country code** (e.g., `BE0123456789`)
6. **Line IDs should be sequential** starting from `1`
7. **TaxScheme ID is usually `VAT`**
8. **TaxCategory ID**: `S` = Standard rate, `Z` = Zero rated, `E` = Exempt
9. **Calculate totals correctly**:
   - `LineExtensionAmount` = Quantity × PriceAmount
   - `TaxAmount` = TaxableAmount × (Percent / 100)
   - `TaxInclusiveAmount` = TaxExclusiveAmount + TaxAmount

---

## Calculation Formulas

```python
# Line level
line_extension_amount = invoiced_quantity * price_amount

# Tax level
tax_amount = taxable_amount * (tax_percent / 100)

# Document level
tax_exclusive_amount = sum(all line_extension_amounts)
tax_inclusive_amount = tax_exclusive_amount + total_tax_amount
payable_amount = tax_inclusive_amount - prepaid_amount
```

---

## References

- **UBL 2.0 Specification**: http://docs.oasis-open.org/ubl/os-UBL-2.0/
- **Odoo Implementation**: `/src/odoo/addons/account_edi_ubl_cii/models/account_edi_xml_ubl_20.py`
- **Import Method**: `_import_fill_invoice_form()` (line 601)
- **Line Import Method**: `_import_fill_invoice_line_form()` (line 721)
