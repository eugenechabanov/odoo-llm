# Chart of Accounts Auto-Determination in Odoo

## Overview

Odoo's invoice lines automatically compute the `account_id` (chart of accounts) based on the product, partner, and journal. **Neither EDI nor our LLM tools need to explicitly set the account** - it's handled by Odoo's computed field mechanism.

---

## How It Works

### The Computed Field

**File**: `/src/odoo/addons/account/models/account_move_line.py:77-80`

```python
account_id = fields.Many2one(
    'account.account',
    compute='_compute_account_id',
    store=True,
    readonly=False,
    precompute=True,
)
```

**Key Points**:
- `compute='_compute_account_id'`: Automatically calculates the account
- `store=True`: Saves the computed value to database
- `readonly=False`: Can be manually overridden if needed
- `precompute=True`: Computes during create/write operations

---

## Account Computation Logic

### For Product Lines (The Main Case)

**File**: `/src/odoo/addons/account/models/account_move_line.py:581-590`

```python
product_lines = self.filtered(
    lambda line: line.display_type == 'product' and line.move_id.is_invoice(True)
)

for line in product_lines:
    if line.product_id:
        fiscal_position = line.move_id.fiscal_position_id

        # Get product's income/expense accounts
        accounts = line.with_company(line.company_id).product_id \
            .product_tmpl_id.get_product_accounts(fiscal_pos=fiscal_position)

        # Choose based on invoice type
        if line.move_id.is_sale_document(include_receipts=True):
            line.account_id = accounts['income']  # Customer invoice
        elif line.move_id.is_purchase_document(include_receipts=True):
            line.account_id = accounts['expense']  # Vendor bill
```

### Account Resolution Hierarchy

When `get_product_accounts()` is called, it resolves accounts in this order:

#### 1. Product-Specific Accounts (Highest Priority)
```
Product Form → Accounting Tab
- Customer Invoices: property_account_income_id
- Vendor Bills: property_account_expense_id
```

If set, these override category defaults.

#### 2. Product Category Accounts
```
Product Category → Accounting Properties
- Income Account: property_account_income_categ_id
- Expense Account: property_account_expense_categ_id
```

Inherited from category if product doesn't have specific accounts.

#### 3. Fiscal Position Mapping (Optional)
```
Fiscal Position → Account Mapping
- Maps accounts based on fiscal rules (e.g., domestic vs international)
```

Applied after base account is determined.

**Example**:
```python
# Product has expense account: "610000 - Purchases"
# Fiscal position maps: "610000" → "610100 - International Purchases"
# Final account_id: "610100 - International Purchases"
```

---

## Fallback Mechanisms

### No Product Set (Lines 591-597)

If invoice line has **no product** but has a **partner**:

```python
elif line.partner_id:
    line.account_id = self.env['account.account']._get_most_frequent_account_for_partner(
        company_id=line.company_id.id,
        partner_id=line.partner_id.id,
        move_type=line.move_id.move_type,
        journal_id=line.journal_id.id,
    )
```

Uses **account predictive bills** - the account most frequently used for this partner.

### No Product and No Pattern (Lines 598-606)

Final fallback:

```python
for line in self:
    if not line.account_id and line.display_type not in ('line_section', 'line_note'):
        # Try to reuse account from previous lines
        previous_two_accounts = line.move_id.line_ids.filtered(
            lambda l: l.account_id and l.display_type == line.display_type
        )[-2:].account_id

        if len(previous_two_accounts) == 1 and len(line.move_id.line_ids) > 2:
            line.account_id = previous_two_accounts
        else:
            # Last resort: journal's default account
            line.account_id = line.move_id.journal_id.default_account_id
```

**Fallback Order**:
1. Use same account as previous lines (if consistent)
2. Use journal's default account

---

## How EDI Uses This

### EDI Does NOT Set account_id

**File**: `/src/odoo/addons/account_edi_ubl_cii/models/account_edi_xml_ubl_20.py:726-732`

```python
# EDI extracts product information from XML
product = self.env['account.edi.format']._retrieve_product(
    default_code=self._find_value('./cac:Item/cac:SellersItemIdentification/cbc:ID', tree),
    name=name,
    barcode=self._find_value("./cac:Item/cac:StandardItemIdentification/cbc:ID[@schemeID='0160']", tree),
)

# EDI sets product_id
if product is not None:
    invoice_line.product_id = product

# ✨ account_id is automatically computed by Odoo!
# EDI does nothing else - Odoo's _compute_account_id handles it
```

**What EDI provides**:
- ✅ Product identification (code, name, barcode)
- ✅ Product matching via `_retrieve_product()`

**What Odoo provides automatically**:
- ✅ account_id determination
- ✅ Fiscal position mapping
- ✅ Fallback logic

---

## How This Applies to Our Hybrid Approach

### Current LLM Implementation

**Problem**: Our analyzer and updater might duplicate account logic

**Solution**: Follow EDI's approach - just set product_id

### Analyzer Phase

```python
# Analyzer finds product using EDI helper
product = self.env['account.edi.format']._retrieve_product(
    default_code=extracted_code,
    name=extracted_description,
    barcode=extracted_barcode
)

# Return product_id in JSON
invoice_data['lines'].append({
    'product_id': product.id,  # ✅ Set product
    'name': description,
    'quantity': qty,
    'price_unit': price,
    # ❌ NO account_id needed!
})
```

### Updater Phase (Current Approach)

```python
# Updater writes invoice line
line_vals = {
    'product_id': line_data['product_id'],
    'name': line_data['name'],
    'quantity': line_data['quantity'],
    'price_unit': line_data['price_unit'],
    # account_id automatically computed!
}
invoice.write({'invoice_line_ids': [(0, 0, line_vals)]})
```

### Updater Phase (EDI Delegation Approach)

```python
# Build minimal XML with product info
line_xml = etree.SubElement(invoice_xml, 'InvoiceLine')
item = etree.SubElement(line_xml, 'Item')

# Product identification
sellers_id = etree.SubElement(item, 'SellersItemIdentification')
etree.SubElement(sellers_id, 'ID').text = product.default_code or ''
etree.SubElement(item, 'Name').text = product.name

# Let EDI process it
edi_format._import_fill_invoice_form(journal, tree, invoice, qty_factor=1)

# ✨ EDI sets product_id → Odoo computes account_id
```

---

## Special Cases

### Manual Account Override

Users can manually override the computed account:

```python
# After automatic computation
invoice_line.account_id = specific_account  # Manual override

# The computed field is readonly=False, so this works
```

**Use Case**: Exception handling, special GL postings

### Payment Term Lines (Lines 493-579)

Special logic for receivable/payable accounts:

```python
term_lines = self.filtered(lambda line: line.display_type == 'payment_term')
```

Uses:
1. Partner's receivable/payable account property
2. Company's default receivable/payable account
3. Fallback to any receivable/payable account in chart

**Not relevant for invoice lines** - only for AR/AP term lines.

---

## Configuration Requirements

### Minimum Setup for Auto-Determination

1. **Product Category**:
   ```
   Accounting → Configuration → Product Categories
   → Set "Income Account" and "Expense Account"
   ```

2. **Or Product-Specific**:
   ```
   Product → Accounting Tab
   → Set "Income Account" and/or "Expense Account"
   ```

3. **Journal Default** (Fallback):
   ```
   Accounting → Configuration → Journals
   → Set "Default Income/Expense Account"
   ```

### Fiscal Position (Optional)

```
Accounting → Configuration → Fiscal Positions
→ Account Mapping tab
→ Add mappings: Account on Invoice → Account to Use
```

**Example**: Domestic sales use account 400000, international sales use 400100

---

## Summary

| Component | Sets Product? | Sets Account? | How Account is Determined |
|-----------|--------------|---------------|---------------------------|
| **EDI** | ✅ Via `_retrieve_product()` | ❌ No | Odoo's `_compute_account_id()` |
| **LLM Analyzer** | ✅ Should use EDI helper | ❌ No | Odoo's `_compute_account_id()` |
| **LLM Updater** | ✅ Via invoice_data | ❌ No | Odoo's `_compute_account_id()` |
| **Odoo Core** | N/A | ✅ Automatic | Product → Category → Fiscal Position → Fallbacks |

---

## Key Takeaways

1. **Never manually set account_id** unless absolutely necessary (special cases)
2. **Always set product_id** - the rest happens automatically
3. **EDI doesn't worry about accounts** - neither should we
4. **Fiscal positions work transparently** - no code changes needed
5. **Fallbacks are robust** - even without product, Odoo finds an account

---

## Code References

- **Compute Logic**: `/src/odoo/addons/account/models/account_move_line.py:492-606`
- **Product Accounts**: `/src/odoo/addons/product/models/product_template.py` (get_product_accounts)
- **EDI Usage**: `/src/odoo/addons/account_edi_ubl_cii/models/account_edi_xml_ubl_20.py:721-768`
- **Account Predictive Bills**: `/src/odoo/addons/account/models/account_account.py:_get_most_frequent_account_for_partner`

---

## Testing Account Auto-Determination

### Test Case 1: Product with Specific Account

```python
# Setup
product = self.env['product.product'].create({
    'name': 'Test Product',
    'property_account_expense_id': account_610000.id,  # Specific account
})

# Create invoice line
line = self.env['account.move.line'].create({
    'move_id': invoice.id,
    'product_id': product.id,
    'quantity': 1,
})

# Assert
assert line.account_id == account_610000  # ✅ Uses product's account
```

### Test Case 2: Product with Category Account

```python
# Setup
category = self.env['product.category'].create({
    'name': 'Test Category',
    'property_account_expense_categ_id': account_600000.id,
})
product = self.env['product.product'].create({
    'name': 'Test Product',
    'categ_id': category.id,
    # No property_account_expense_id set
})

# Create invoice line
line = self.env['account.move.line'].create({
    'move_id': invoice.id,
    'product_id': product.id,
    'quantity': 1,
})

# Assert
assert line.account_id == account_600000  # ✅ Uses category's account
```

### Test Case 3: No Product, Uses Predictive

```python
# Create invoice line without product
line = self.env['account.move.line'].create({
    'move_id': invoice.id,
    'name': 'Manual entry',
    'quantity': 1,
    'price_unit': 100,
})

# Assert
assert line.account_id  # ✅ Some account is set (predictive or journal default)
```

---

## Conclusion

**The Golden Rule**: Set `product_id`, forget about `account_id`.

Odoo's automatic account determination is:
- ✅ Robust (multiple fallbacks)
- ✅ Configurable (product, category, fiscal position)
- ✅ Transparent (works without intervention)
- ✅ Used by EDI (proven approach)

Our hybrid LLM+EDI approach inherits all these benefits by following EDI's pattern.
