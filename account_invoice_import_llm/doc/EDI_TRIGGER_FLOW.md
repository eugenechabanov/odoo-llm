# EDI Attachment Processing Trigger Flow

## Overview

This document explains **exactly where** and **how** Odoo's EDI modules process invoice attachments, and **what happens when EDI fails** or encounters non-EDI files.

---

## Two Entry Points

### 1. Creating New Invoice from Attachment (Journal UI)

**User Action**: `Accounting → Vendors/Customers → Upload` button

**Code Flow**:

```
account.journal.create_document_from_attachment(attachment_ids)
    ↓
account.journal._create_document_from_attachment(attachment_ids)  [Line 810]
    ↓
account.move._get_create_document_from_attachment_decoders()  [Line 821]
    ↓
account.edi.format._create_document_from_attachment(attachment)  [Priority 10]
    ↓
account.edi.format._decode_attachment(attachment)  [Line 298]
    ↓
Loops through all EDI formats trying to parse
    ↓
SUCCESS: Returns invoice
FAILURE: Returns empty invoice recordset
    ↓
If ALL decoders fail: Creates empty draft invoice [Line 828]
Attaches file to invoice anyway [Line 829-830]
```

**File**: `/src/odoo/addons/account/models/account_journal.py:810-832`

---

### 2. Updating Existing Invoice from Attachment

**User Action**: Drag & drop attachment to existing invoice or use paperclip button

**Code Flow**:

```
User uploads attachment
    ↓
account.move._message_post_after_hook(new_message, message_values)  [Line 4356]
    ↓
Validation checks:
    - Must be single invoice [Line 4362]
    - Must be draft state [Line 4366-4371]
    - Must have no invoice lines yet [Line 4372-4377]
    ↓
account.move._get_update_invoice_from_attachment_decoders(invoice)  [Line 4379]
    ↓
account.edi.format._update_invoice_from_attachment(attachment, invoice)  [Priority 10]
    ↓
account.edi.format._decode_attachment(attachment)  [Line 298]
    ↓
Loops through all EDI formats trying to parse
    ↓
SUCCESS: Updates invoice, returns
FAILURE: Returns silently (no error to user)
```

**File**: `/src/odoo/addons/account/models/account_move.py:4356-4389`

---

## Detailed: `_decode_attachment()` Process

**File**: `/src/odoo/addons/account_edi/models/account_edi_format.py:298-322`

### Step 1: Detect File Type

```python
def _decode_attachment(self, attachment):
    content = base64.b64decode(attachment.datas)
    to_process = []

    # Detect file type by mimetype
    is_text_plain_xml = 'text/plain' in attachment.mimetype and (
        content.startswith(b'<?xml') or attachment.name.endswith('.xml')
    )

    if 'pdf' in attachment.mimetype:
        to_process.extend(self._decode_pdf(attachment.name, content))
    elif attachment.mimetype.endswith('/xml') or is_text_plain_xml:
        to_process.extend(self._decode_xml(attachment.name, content))
    else:
        to_process.extend(self._decode_binary(attachment.name, content))

    return to_process
```

**Returns**: List of dictionaries with:
- `filename`: Attachment name
- `content`: Binary content
- `type`: 'xml', 'pdf', or 'binary'
- `xml_tree`: lxml tree (if type='xml')
- `pdf_reader`: OdooPdfFileReader (if type='pdf')

---

### Step 2: Decode PDF (Extract Embedded XML)

**File**: `/src/odoo/addons/account_edi/models/account_edi_format.py:242-296`

```python
def _decode_pdf(self, filename, content):
    to_process = []
    try:
        buffer = io.BytesIO(content)
        pdf_reader = OdooPdfFileReader(buffer, strict=False)
    except Exception as e:
        _logger.exception("Error when reading the pdf: %s" % e)
        return to_process  # ❌ Empty list = EDI can't process

    # Add the PDF itself
    to_process.append({
        'filename': filename,
        'content': content,
        'type': 'pdf',
        'pdf_reader': pdf_reader,
    })

    # Extract embedded XML files (Factur-X/ZUGFeRD)
    for xml_name, xml_content in pdf_reader.getAttachments():
        try:
            xml_tree = etree.fromstring(xml_content)
            to_process.append({
                'filename': xml_name,
                'content': xml_content,
                'type': 'xml',
                'xml_tree': xml_tree,
            })
        except Exception as e:
            _logger.exception("Error parsing embedded XML: %s" % e)
            continue  # Skip this embedded file

    return to_process
```

**Key Points**:
- ✅ **PDF with embedded XML** (Factur-X): Returns both PDF + XML entries
- ✅ **Pure PDF**: Returns only PDF entry (type='pdf')
- ❌ **Corrupt PDF**: Returns empty list

---

### Step 3: Decode XML

**File**: `/src/odoo/addons/account_edi/models/account_edi_format.py:216-240`

```python
def _decode_xml(self, filename, content):
    to_process = []
    try:
        xml_tree = etree.fromstring(content)
    except Exception as e:
        _logger.exception("Error when converting the xml content to etree: %s" % e)
        return to_process  # ❌ Empty list = Can't parse XML

    if len(xml_tree):  # Ensure XML has content
        to_process.append({
            'filename': filename,
            'content': content,
            'type': 'xml',
            'xml_tree': xml_tree,
        })
    return to_process
```

**Key Points**:
- ✅ **Valid XML**: Returns XML tree
- ❌ **Invalid XML**: Logs error, returns empty list
- ❌ **Empty XML**: Returns empty list

---

## Detailed: Invoice Creation/Update Loop

### For New Invoices

**File**: `/src/odoo/addons/account_edi/models/account_edi_format.py:324-351`

```python
def _create_document_from_attachment(self, attachment):
    # Decode attachment (PDF → extract XML, etc.)
    for file_data in self._decode_attachment(attachment):

        # Try each EDI format (UBL, CII, etc.)
        for edi_format in self:
            res = False
            try:
                if file_data['type'] == 'xml':
                    res = edi_format._create_invoice_from_xml_tree(
                        file_data['filename'],
                        file_data['xml_tree']
                    )
                elif file_data['type'] == 'pdf':
                    res = edi_format._create_invoice_from_pdf_reader(
                        file_data['filename'],
                        file_data['pdf_reader']
                    )
                else:  # binary
                    res = edi_format._create_invoice_from_binary(
                        file_data['filename'],
                        file_data['content'],
                        file_data['extension']
                    )

            except RedirectWarning as rw:
                raise rw  # Re-raise redirect warnings

            except Exception as e:
                # ⚠️ Log error but CONTINUE to next format
                _logger.exception(
                    "Error importing attachment \"%s\" as invoice with format \"%s\": %s",
                    file_data['filename'],
                    edi_format.name,
                    str(e)
                )

            if res:  # ✅ Success!
                return res._link_invoice_origin_to_purchase_orders(timeout=4)

    # ❌ All formats failed
    return self.env['account.move']  # Empty recordset
```

**Critical Behavior**:
- **Exception handling**: Logs error, **continues** to next format
- **Success**: Returns invoice immediately
- **All failures**: Returns empty `account.move` recordset

---

### For Existing Invoices

**File**: `/src/odoo/addons/account_edi/models/account_edi_format.py:353-383`

```python
def _update_invoice_from_attachment(self, attachment, invoice):
    for file_data in self._decode_attachment(attachment):
        for edi_format in self:
            res = False
            try:
                if file_data['type'] == 'xml':
                    res = edi_format._update_invoice_from_xml_tree(
                        file_data['filename'],
                        file_data['xml_tree'],
                        invoice
                    )
                elif file_data['type'] == 'pdf':
                    res = edi_format._update_invoice_from_pdf_reader(
                        file_data['filename'],
                        file_data['pdf_reader'],
                        invoice
                    )
                else:
                    res = edi_format._update_invoice_from_binary(
                        file_data['filename'],
                        file_data['content'],
                        file_data['extension'],
                        invoice
                    )

            except Exception as e:
                _logger.exception(
                    "Error importing attachment \"%s\" as invoice with format \"%s\": %s",
                    file_data['filename'],
                    edi_format.name,
                    str(e)
                )

            if res:
                return invoice

    return self.env['account.move']  # Empty recordset
```

**Same pattern as create**, but updates existing invoice.

---

## What Happens When EDI Fails?

### Scenario 1: Regular PDF (No Embedded XML)

```
_decode_pdf() extracts:
    - PDF file (type='pdf')
    - No embedded XML found

Loops through formats:
    - UBL format: _create_invoice_from_pdf_reader() → Returns empty (stub method)
    - CII format: _create_invoice_from_pdf_reader() → Returns empty (stub method)

Result: Returns empty recordset
```

**Back in journal flow** (Line 828):
```python
if not invoice:
    invoice = self.env['account.move'].create({})  # ✅ Creates empty invoice
invoice.message_post(attachment_ids=[attachment.id])  # Attaches file
```

**User sees**: Empty draft invoice with attached PDF

---

### Scenario 2: XML File (Non-UBL/Non-CII)

```
_decode_xml() succeeds:
    - Valid XML tree created

Loops through formats:
    - UBL format: Checks XML namespace → Not UBL → Returns empty
    - CII format: Checks XML namespace → Not CII → Returns empty

Result: Returns empty recordset
```

**User sees**: Empty draft invoice with attached XML (or silent failure if updating)

---

### Scenario 3: Corrupt/Invalid File

```
_decode_pdf() or _decode_xml() fails:
    - Exception caught
    - _logger.exception() logs error
    - Returns empty list

_create_document_from_attachment():
    - for file_data in []: (empty loop, no iterations)
    - Returns empty recordset immediately
```

**User sees**: Empty draft invoice, error logged server-side only

---

### Scenario 4: Valid Factur-X with Embedded XML

```
_decode_pdf() extracts:
    - PDF file (type='pdf')
    - Embedded XML (type='xml', xml_tree=...)

First iteration: PDF
    - All formats return empty (no PDF parser implemented)

Second iteration: XML
    - CII format: Recognizes namespace → Parses successfully → Returns invoice ✅

Result: Returns populated invoice
```

**User sees**: Draft invoice with all data filled from XML

---

## Decoder Priority System

**File**: `/src/odoo/addons/account_edi/models/account_move.py:414-424`

### Registration

```python
def _get_create_document_from_attachment_decoders(self):
    # OVERRIDE from base account
    res = super()._get_create_document_from_attachment_decoders()

    # Add EDI decoder with priority 10
    res.append((10, self.env['account.edi.format'].search([])._create_document_from_attachment))

    return res

def _get_update_invoice_from_attachment_decoders(self, invoice):
    # OVERRIDE from base account
    res = super()._get_update_invoice_from_attachment_decoders(invoice)

    # Add EDI updater with priority 10
    res.append((10, self.env['account.edi.format'].search([])._update_invoice_from_attachment))

    return res
```

### Execution

**File**: `/src/odoo/addons/account/models/account_journal.py:823-826`

```python
for decoder in sorted(decoders, key=lambda d: d[0]):  # Sort by priority
    invoice = decoder[1](attachment)  # Call decoder function
    if invoice:
        break  # Stop at first success
```

**Priority**: Lower number = higher priority
- **10**: EDI formats (standard)
- **20+**: Other modules (e.g., OCR if installed)

**Our LLM-OCR** should register at **priority 15-20** to run AFTER EDI fails.

---

## Validation Checks (Existing Invoice Update)

**File**: `/src/odoo/addons/account/models/account_move.py:4362-4377`

### Check 1: Must be Draft

```python
if attachments and self.state != 'draft':
    self.message_post(
        body=_('The invoice is not a draft, it was not updated from the attachment.')
    )
    return res
```

### Check 2: Must Have No Lines

```python
if attachments and self.invoice_line_ids:
    self.message_post(
        body=_('The invoice already contains lines, it was not updated from the attachment.')
    )
    return res
```

**Implication**: EDI (and our LLM tool) only auto-fills **empty draft invoices**.

---

## EDI Format Implementations

### UBL Format

**File**: `/src/odoo/addons/account_edi_ubl_cii/models/account_edi_xml_ubl_20.py`

```python
def _create_invoice_from_xml_tree(self, filename, tree, journal=None):
    self.ensure_one()

    # Check if this is a UBL 2.0 invoice
    if self._is_ubl20(tree):
        return self._import_ubl(tree, self.env['account.move'])

    return self.env['account.move']  # Not UBL, return empty
```

**Detection**: Checks XML namespace and root element

---

### CII/Factur-X Format

**File**: `/src/odoo/addons/account_edi_ubl_cii/models/account_edi_xml_cii_facturx.py`

```python
def _create_invoice_from_xml_tree(self, filename, tree, journal=None):
    self.ensure_one()

    # Check if this is a CII invoice
    if self._is_facturx(tree):
        return self._import_facturx(tree, self.env['account.move'])

    return self.env['account.move']  # Not CII, return empty
```

**Detection**: Checks for CII-specific XML structure

---

### PDF Reader (Stub Implementation)

**File**: `/src/odoo/addons/account_edi/models/account_edi_format.py:154-164`

```python
def _create_invoice_from_pdf_reader(self, filename, reader):
    """ Create a new invoice with the data inside a pdf.

    :param filename: The name of the pdf.
    :param reader:   The OdooPdfFileReader of the pdf to import.
    :returns:        The created invoice.
    """
    # TO OVERRIDE
    self.ensure_one()
    return self.env['account.move']  # ❌ Stub: Always returns empty
```

**Why Stub?**: EDI only parses XML, not PDF text. PDF reader is only for extracting embedded XML.

---

## Where OCR/LLM Should Hook In

### Option 1: As a Decoder (Recommended)

Register our LLM tool as a decoder with **priority 15-20**:

```python
# In account.move override
def _get_create_document_from_attachment_decoders(self):
    res = super()._get_create_document_from_attachment_decoders()

    # EDI runs at priority 10
    # Our LLM-OCR runs at priority 15 (after EDI fails)
    res.append((15, self._llm_ocr_create_from_attachment))

    return res
```

**Benefit**: Integrates seamlessly into existing flow

---

### Option 2: Post-Creation Hook

Hook into the empty invoice creation:

```python
@api.model_create_multi
def create(self, vals_list):
    invoices = super().create(vals_list)

    for invoice in invoices:
        # Check if invoice is empty and has attachment
        if not invoice.invoice_line_ids and invoice.message_main_attachment_id:
            # Trigger LLM-OCR processing
            self._process_with_llm_ocr(invoice)

    return invoices
```

**Drawback**: Runs on ALL invoice creation, needs filtering

---

### Option 3: Manual Button (Current Approach)

Add button to invoice form for manual triggering:

```xml
<button name="action_extract_invoice_data"
        string="Extract with AI"
        type="object"/>
```

**Benefit**: User control, no automatic processing
**Drawback**: Requires manual action

---

## Error Logging

All EDI errors are logged but **not shown to user**:

```python
_logger.exception(
    "Error importing attachment \"%s\" as invoice with format \"%s\": %s",
    file_data['filename'],
    edi_format.name,
    str(e)
)
```

**To see errors**: Check Odoo server logs at `DEBUG` or `ERROR` level

---

## Summary Flow Diagram

```
User Uploads PDF/XML
    ↓
┌───────────────────────────────┐
│ _decode_attachment()          │
│ Detect type: XML/PDF/Binary   │
│ Extract embedded XML from PDF │
└───────────────────────────────┘
    ↓
┌───────────────────────────────────────┐
│ Loop through EDI formats              │
│ (UBL 2.0, UBL 2.1, CII, etc.)         │
└───────────────────────────────────────┘
    ↓
    ├─→ Format recognizes structure?
    │       ↓
    │   YES: Parse XML → Create/Update Invoice ✅
    │       Return invoice
    │
    └─→ NO format recognizes?
            ↓
        Return empty recordset
            ↓
        ┌─────────────────────────────┐
        │ Journal creates empty       │
        │ invoice, attaches file      │
        └─────────────────────────────┘
            ↓
        🎯 LLM-OCR ENTRY POINT HERE
            ↓
        Process PDF with Mistral OCR
            ↓
        Extract data with Claude
            ↓
        Fill invoice via analyzer/updater
```

---

## Key Takeaways

1. **EDI tries ALL formats** - loops until one succeeds
2. **Silent failure** - errors logged, not shown to user
3. **Empty invoice created** - if all decoders fail (new invoice flow)
4. **No update** - if all decoders fail (existing invoice flow)
5. **PDF text NOT parsed** - EDI only extracts embedded XML
6. **Regular PDFs always fail** - triggers empty invoice creation
7. **Our LLM-OCR hook point**: After EDI returns empty, before showing empty invoice to user

---

## Next Steps for Integration

### Phase 0: EDI Pre-Check (As per workflow discussion)

Before our OCR runs, check if EDI can handle it:

```python
def should_use_ocr(attachment):
    # Try EDI first
    edi_formats = self.env['account.edi.format'].search([])
    decoded = edi_formats._decode_attachment(attachment)

    for file_data in decoded:
        if file_data['type'] == 'xml':
            # Has embedded XML - let EDI handle it
            return False

    # No XML found - use OCR
    return True
```

### Phase 1: Register LLM Decoder

Add to `_get_create_document_from_attachment_decoders()` with priority 15

### Phase 2: Analyzer Uses EDI Helpers

Reuse `_retrieve_partner()`, `_retrieve_product()` for matching

### Phase 3: Updater Delegates to EDI

Build minimal XML, call `_import_fill_invoice_form()`

---

## File References

- **Decoder Registration**: `/src/odoo/addons/account_edi/models/account_move.py:414-424`
- **Journal Entry**: `/src/odoo/addons/account/models/account_journal.py:810-860`
- **Attachment Decode**: `/src/odoo/addons/account_edi/models/account_edi_format.py:298-322`
- **Create Flow**: `/src/odoo/addons/account_edi/models/account_edi_format.py:324-351`
- **Update Flow**: `/src/odoo/addons/account_edi/models/account_edi_format.py:353-383`
- **Update Hook**: `/src/odoo/addons/account/models/account_move.py:4356-4389`
- **UBL Parser**: `/src/odoo/addons/account_edi_ubl_cii/models/account_edi_xml_ubl_20.py`
- **CII Parser**: `/src/odoo/addons/account_edi_ubl_cii/models/account_edi_xml_cii_facturx.py`
