# Fiscal Position Tax Mapping in EDI Import

## Issue

Odoo's EDI import (`account_edi_ubl_cii`) does **not** apply fiscal position tax mappings when importing invoices from UBL XML.

### Root Cause

EDI import bypasses Odoo's UI layer and writes directly to the database:
- **UI Path**: Form views → `@api.onchange` handlers → `fiscal_position.map_tax()` → Correct taxes ✅
- **EDI Path**: Direct DB writes → **NO** `@api.onchange` → **NO** tax mapping → Wrong taxes ❌

EDI matches taxes **only by percentage** from `<cbc:Percent>` in UBL XML:
```python
# account_edi_ubl_cii/models/account_edi_common.py:703-709
domain = [
    ('company_id', '=', journal.company_id.id),
    ('amount_type', '=', 'percent'),
    ('type_tax_use', '=', journal.type),
    ('amount', '=', amount),  # ← Only matches by percentage!
]
tax = self.env['account.tax'].search(domain, limit=1)
```

## Impact

**Intra-EU B2B invoices** have incorrect tax amounts:

**Example:**
- Vendor: Isabel N.V. (Belgium - BE0455530509)
- Customer: White Willow B.V. (Netherlands - NL851348257B01)
- Invoice: 4.00 EUR + "21% BTW = 0.00 EUR" (reverse charge)

**Without fiscal position mapping:**
```
EDI finds: "BTW te vorderen hoog (inkopen)" (domestic 21%)
Tax calculated: 4.00 × 21% = 0.84 EUR ❌ WRONG
```

**With fiscal position mapping:**
```
EDI finds: "BTW te vorderen hoog (inkopen)" (domestic 21%)
Fiscal position maps: → "Inkopen import binnen EU hoog" (reverse charge 21%)
Tax calculated: 4.00 × 21% (reverse charge) = 0.00 EUR ✅ CORRECT
```

## Solution

Manually apply fiscal position tax mapping **after** EDI import completes:

```python
# models/account_move.py:424-450
if self.fiscal_position_id:
    for line in self.invoice_line_ids:
        if line.tax_ids:
            original_taxes = line.tax_ids
            mapped_taxes = self.fiscal_position_id.map_tax(original_taxes)
            if mapped_taxes != original_taxes:
                line.tax_ids = mapped_taxes
```

### How map_tax() Works

```python
# account/models/partner.py:117-124
def map_tax(self, taxes):
    """Map taxes according to fiscal position rules"""
    result = self.env['account.tax']
    for tax in taxes:
        # Find mapping rule: source_tax → destination_tax
        mapping = self.tax_ids.filtered(lambda t: t.tax_src_id == tax._origin)
        result |= mapping.tax_dest_id if mapping else tax
    return result
```

Fiscal position "EU landen" has tax mapping rules:
```
Source Tax                          → Destination Tax
────────────────────────────────────────────────────────────────
BTW te vorderen hoog (inkopen) 21%  → Inkopen import binnen EU hoog 21%
BTW te vorderen laag (inkopen) 9%   → Inkopen import binnen EU laag 9%
BTW te vorderen overig (inkopen) 0% → Inkopen import binnen EU overig 0%
```

## Why This is Safe

1. **Same logic as UI**: Uses identical business logic that manual invoice entry uses
2. **Graceful fallback**: If no mapping exists, returns original tax unchanged
3. **Configuration-driven**: Relies on existing fiscal position setup
4. **Well-tested**: Same code path used throughout Odoo core

## References

- `account/models/partner.py::map_tax()` - Odoo core tax mapping logic
- `account_edi_ubl_cii/models/account_edi_common.py::_import_fill_invoice_line_taxes()` - EDI tax matching
- Odoo Documentation: [Fiscal Positions](https://www.odoo.com/documentation/16.0/applications/finance/accounting/taxation/taxes/fiscal_positions.html)
