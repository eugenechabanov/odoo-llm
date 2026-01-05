# Using llm.assistant for One-Shot Invoice Extraction

## Summary

How to leverage `llm.assistant` configuration (provider, model, system instructions) for one-shot LLM calls without creating persistent threads or running conversation loops.

---

## Architecture Overview

### llm.assistant Configuration

**Model**: `llm.assistant`
**Purpose**: Pre-configured assistant with provider, model, and system prompt

**Key Fields**:
```python
class LLMAssistant(models.Model):
    _name = "llm.assistant"

    provider_id = fields.Many2one("llm.provider")      # e.g., Anthropic
    model_id = fields.Many2one("llm.model")            # e.g., claude-3-5-sonnet
    prompt_id = fields.Many2one("llm.prompt")          # System instructions template
    default_values = fields.Text()                     # JSON with prompt variables
    tool_ids = fields.Many2many("llm.tool")            # Tools assistant can use
```

**Where System Instructions Come From**:
- `prompt_id` points to `llm.prompt` record
- `llm.prompt` contains the template (Jinja2 format)
- `default_values` provides variables for template rendering
- Result: Rendered system prompt

---

## How Assistant Infrastructure Works

### Full Flow in Interactive Mode (UI)

```
User clicks button → action_open_llm_assistant()
    ↓
Creates/finds thread, sets assistant
    ↓
Returns client action → Opens chat UI
    ↓
Frontend calls /llm/thread/generate endpoint
    ↓
Controller calls thread.generate(user_message_body)
    ↓
thread.generate():
    ├─→ Posts user message (if provided)
    └─→ Calls generate_messages(last_message)
    ↓
generate_messages():
    ├─→ Loops while _should_continue()
    ├─→ Calls _generate_assistant_response()
    │   ├─→ get_prepend_messages() → Renders system + user from prompt_id
    │   ├─→ get_llm_messages() → Gets conversation history
    │   └─→ model_id.chat(messages, tools, prepend_messages)
    ├─→ Executes tool calls if any
    └─→ Loops back if tools were called
```

**Key Discovery**: The user message can be **embedded in the prompt template** (see llm_prompt_invoice_data.xml)!

**Prompt Template with Auto-Trigger**:
```json
[
  {
    "type": "system",
    "content": "You are an invoice processor..."
  },
  {
    "type": "user",
    "content": "Process this invoice by analyzing the attached document..."
  }
]
```

This means when `get_prepend_messages()` is called, it returns **both** system and user messages!

---

## Solution: One-Shot Using Assistant + generate()

### Research Findings

**How action_open_llm_assistant Works** (`llm_assistant_action_mixin.py:33-102`):
1. Finds or creates thread for the record
2. Sets assistant on thread
3. Returns client action that opens chat UI
4. **Frontend automatically calls** `/llm/thread/generate` endpoint
5. **Controller calls** `thread.generate(user_message_body=None)`
6. **generate() triggers** `generate_messages()` loop

**Key Method** (`llm_thread/controllers/main.py:86-99`):
```python
@http.route("/llm/thread/generate", type="http", auth="user", csrf=True)
def llm_thread_generate(self, thread_id, message=None, **kwargs):
    # ... streaming headers ...
    return Response(
        self._llm_thread_generate(
            request.cr.dbname, request.env, thread_id, message, **kwargs
        ),
        direct_passthrough=True,
        headers=headers,
    )
```

**Core Generation** (`llm_thread/models/llm_thread.py:316-337`):
```python
def generate(self, user_message_body, **kwargs):
    """Main generation method with PostgreSQL advisory locking."""
    with self._generation_lock():
        last_message = False
        # Post user message if provided
        if user_message_body:
            last_message = self.message_post(
                body=user_message_body,
                llm_role="user",
                ...
            )
            yield {"type": "message_create", "message": last_message.message_format()[0]}

        # Call the actual generation implementation
        last_message = yield from self.generate_messages(last_message)
        return last_message
```

**If user_message_body is None** → Uses auto-trigger message from prompt template!

---

### Approach: Dynamic Context with Auto-Trigger

**Concept**:
- OCR text is **computed on-the-fly** when thread context is built
- Override `llm.thread.get_context()` to compute OCR from attachment
- Use **dynamic defaults** in llm.assistant to inject computed OCR text
- Assistant's `default_values` uses template syntax: `{{ ocr_text }}`
- Call `thread.generate(None)` - auto-triggers with OCR text injected

**Flow**:
```
Attachment uploaded to invoice
    ↓
Create/get thread for invoice
    ↓
Set assistant (has dynamic defaults)
    ↓
Call thread.generate(None)
    ↓
get_prepend_messages() calls:
    └─→ get_context() [CUSTOM - computes OCR on-the-fly]
        └─→ Finds invoice attachment
        └─→ Runs OCR tool
        └─→ Returns context with 'ocr_text' key
    ↓
assistant.get_evaluated_default_values(context)
    └─→ Evaluates {{ ocr_text }} from context
    └─→ Injects OCR text into defaults
    ↓
Renders prompt template with OCR text
    ↓
Auto-triggers processing
    ↓
Break after first response
```

**Code**:

**1. Override get_context() in custom thread**:
```python
class LLMThreadInvoice(models.Model):
    """Custom thread for invoice processing with OCR context"""
    _inherit = "llm.thread"

    def get_context(self, base_context=None):
        """Override to compute OCR text dynamically"""
        context = super().get_context(base_context)

        # Only for invoice threads
        if self.model == 'account.move' and self.res_id:
            invoice = self.env['account.move'].browse(self.res_id)

            # Get first PDF/image attachment
            attachment = self.env['ir.attachment'].search([
                ('res_model', '=', 'account.move'),
                ('res_id', '=', invoice.id),
                ('mimetype', 'in', ['application/pdf', 'image/png', 'image/jpeg'])
            ], limit=1)

            if attachment:
                # Compute OCR on-the-fly
                ocr_text = self._compute_ocr_for_attachment(attachment)
                if ocr_text:
                    # Add to context for dynamic defaults
                    context['ocr_text'] = ocr_text

        return context

    def _compute_ocr_for_attachment(self, attachment):
        """Run Mistral OCR on attachment and return extracted text"""
        try:
            # Get OCR tool
            ocr_tool = self.env['llm.tool.ocr.mistral'].search([], limit=1)
            if not ocr_tool:
                return None

            # Call OCR
            result = ocr_tool._parse_attachment(
                attachment_id=attachment.id,
                provider=ocr_tool.provider_id,
                ocr_model=ocr_tool.model_id,
            )

            return result.get('extracted_text', '')
        except Exception as e:
            _logger.error(f"OCR failed for attachment {attachment.id}: {e}")
            return None
```

**3. Trigger assistant processing**:
```python
def action_process_invoice_with_ai(self):
    """Process invoice using AI assistant (one-shot)"""
    self.ensure_one()

    # Ensure OCR text is available
    if not self.invoice_ocr_text:
        raise UserError("No OCR text available. Please upload invoice first.")

    # Get or create thread
    thread = self.env['llm.thread'].search([
        ('model', '=', 'account.move'),
        ('res_id', '=', self.id)
    ], limit=1)

    if not thread:
        # Get assistant
        assistant = self.env['llm.assistant'].get_assistant_by_code('invoice_extraction')
        if not assistant:
            raise UserError("Invoice extraction assistant not configured")

        # Create thread
        thread = self.env['llm.thread'].create({
            'name': f'Invoice Extraction - {self.name or "Draft"}',
            'assistant_id': assistant.id,
            'model_id': assistant.model_id.id,
            'model': 'account.move',
            'res_id': self.id,
        })

    # Call generate() - auto-triggers with OCR text from dynamic defaults
    invoice_data = None
    for response_event in thread.generate(user_message_body=None):
        if response_event.get('type') == 'message_create':
            message = response_event.get('message', {})
            if message.get('author_id'):  # Assistant message
                body = message.get('body', '')
                invoice_data = self._parse_invoice_json(body)
                break  # ONE response only!

    # Now use invoice_data to populate invoice fields
    if invoice_data:
        self._apply_extracted_data(invoice_data)

    return True
```

**Benefits**:
- ✅ OCR text stored in database field (can be reviewed/edited)
- ✅ Dynamic defaults inject data via Jinja2 templates
- ✅ No hardcoded prompts in Python - all in data
- ✅ Can test prompt in UI with real data
- ✅ Auto-triggers processing without manual user message
- ✅ Clean separation: OCR → Storage → Assistant → Processing

---

## Setting Up the Invoice Extraction Assistant

### 1. Create llm.prompt (Multi-Message Template with Auto-Trigger)

**Model**: `llm.prompt`
**Code**: `invoice_extraction`
**Format**: `json` (returns array of messages)

**Template** (Jinja2 - returns JSON array):
```jinja2
[
  {
    "type": "system",
    "content": {{ ('You are a ' + role + '.\\n\\nYour goal is to ' + goal + '\\n\\nBackground: ' + background + '\\n\\nInstructions: ' + instructions + '\\n\\n' + footer) | tojson }}
  },
  {
    "type": "user",
    "content": {{ ('Extract invoice data from the following OCR text and return as JSON:\\n\\n' + ocr_text) | tojson }}
  }
]
```

**Note**: The `ocr_text` variable will come from dynamic defaults!

**Arguments Schema**:
```json
{
  "role": {
    "type": "string",
    "description": "The role of the assistant",
    "required": true
  },
  "goal": {
    "type": "string",
    "description": "The primary goal",
    "required": true
  },
  "background": {
    "type": "string",
    "description": "Background information",
    "required": true
  },
  "instructions": {
    "type": "string",
    "description": "Specific instructions",
    "required": true
  },
  "footer": {
    "type": "string",
    "description": "Optional footer",
    "required": false,
    "default": ""
  },
  "ocr_text": {
    "type": "string",
    "description": "OCR extracted text from invoice (injected via dynamic defaults)",
    "required": true
  }
}
```

**Key Features**:
- ✅ **Multi-message**: Returns array with system + user messages
- ✅ **Auto-trigger**: User message automatically starts processing
- ✅ **Variables**: Role, goal, background, instructions customizable via default_values
- ✅ **Jinja2**: Uses template rendering with assistant's default_values

---

### 2. Create llm.assistant Record with Dynamic Defaults

**Model**: `llm.assistant`
**Code**: `invoice_extraction`

**Fields**:
```python
{
    "name": "Invoice Data Extraction",
    "code": "invoice_extraction",
    "provider_id": <Anthropic provider ID>,
    "model_id": <claude-3-5-sonnet model ID>,
    "prompt_id": <invoice_extraction prompt ID>,
    "has_dynamic_defaults": True,  # CRITICAL: Enable template evaluation!
    "default_values": {
        "role": "Invoice Data Extraction Assistant",
        "goal": "extract structured invoice data from OCR text and return as JSON",
        "background": "You process invoices for Odoo ERP. Extract vendor info, invoice details, and line items.",
        "instructions": """
Extract the following fields from invoice documents:

**Required**:
- vendor_name, vat, invoice_number, invoice_date, total_amount

**Optional**:
- currency, due_date, payment_reference, lines (array)

**Line Items** (if available):
- description, quantity, unit_price, tax_amount, total_amount

**Output Format**: Return ONLY valid JSON, no markdown or explanations.

**Example**:
{
  "vendor_name": "Supplier Inc.",
  "vat": "BE0123456789",
  "invoice_number": "INV-2024-001",
  "invoice_date": "2024-01-15",
  "total_amount": 1210.00,
  "currency": "EUR",
  "lines": [...]
}
        """,
        "footer": "Important: Return ONLY the JSON object. Dates in YYYY-MM-DD. Amounts as numbers.",
        "ocr_text": "{{ ocr_text }}"  # DYNAMIC! Computed from attachment via get_context()
    },
    "tool_ids": [],  # No tools needed for one-shot extraction
    "is_public": False,
}
```

**Key Point**: `has_dynamic_defaults = True` enables Jinja2 template evaluation in `default_values`!

**Setup via Data File** (`data/llm_assistant_invoice_extraction.xml`):
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Invoice Extraction Prompt (Multi-Message Template) -->
    <record id="prompt_invoice_extraction" model="llm.prompt">
        <field name="name">Invoice Data Extraction Multi-Message Prompt</field>
        <field name="code">invoice_extraction</field>
        <field name="description">Multi-message prompt with system instructions and auto-trigger for invoice extraction</field>
        <field name="format">json</field>
        <field name="template"><![CDATA[[
  {
    "type": "system",
    "content": {{ ('You are a ' + role + '.\\n\\nYour goal is to ' + goal + '\\n\\nBackground: ' + background + '\\n\\nInstructions: ' + instructions + '\\n\\n' + footer) | tojson }}
  },
  {
    "type": "user",
    "content": "Extract invoice data from the OCR text and return as JSON. Use the attached OCR text file."
  }
]]]></field>
        <field name="arguments_json"><![CDATA[{
    "role": {
        "type": "string",
        "description": "The role of the assistant",
        "required": true
    },
    "goal": {
        "type": "string",
        "description": "The primary goal",
        "required": true
    },
    "background": {
        "type": "string",
        "description": "Background information",
        "required": true
    },
    "instructions": {
        "type": "string",
        "description": "Specific instructions",
        "required": true
    },
    "footer": {
        "type": "string",
        "description": "Optional footer",
        "required": false,
        "default": ""
    }
}]]></field>
        <field name="active" eval="True"/>
    </record>

    <!-- Invoice Extraction Assistant with DYNAMIC Default Values -->
    <record id="assistant_invoice_extraction" model="llm.assistant">
        <field name="name">Invoice Data Extraction</field>
        <field name="code">invoice_extraction</field>
        <field name="provider_id" ref="llm_anthropic.provider_anthropic"/>
        <field name="model_id" ref="llm_anthropic.model_claude_3_5_sonnet"/>
        <field name="prompt_id" ref="prompt_invoice_extraction"/>
        <field name="has_dynamic_defaults" eval="True"/>  <!-- CRITICAL! -->
        <field name="default_values"><![CDATA[{
  "role": "Invoice Data Extraction Assistant",
  "goal": "extract structured invoice data from OCR text and return as JSON",
  "background": "You process invoices for Odoo ERP. Extract vendor info, invoice details, and line items.",
  "instructions": "Extract the following fields from invoice documents:\n\n**Required**:\n- vendor_name, vat, invoice_number, invoice_date, total_amount\n\n**Optional**:\n- currency, due_date, payment_reference, lines (array)\n\n**Line Items** (if available):\n- description, quantity, unit_price, tax_amount, total_amount\n\n**Output Format**: Return ONLY valid JSON, no markdown or explanations.\n\n**Example**:\n{\n  \"vendor_name\": \"Supplier Inc.\",\n  \"vat\": \"BE0123456789\",\n  \"invoice_number\": \"INV-2024-001\",\n  \"invoice_date\": \"2024-01-15\",\n  \"total_amount\": 1210.00,\n  \"currency\": \"EUR\",\n  \"lines\": [...]\n}",
  "footer": "Important: Return ONLY the JSON object. Dates in YYYY-MM-DD. Amounts as numbers.",
  "ocr_text": "{{ ocr_text }}"
}]]></field>
        <field name="is_public" eval="False"/>
    </record>
</odoo>
```

**How Dynamic Context Works**:
1. Thread is created for `account.move` record
2. When `thread.get_prepend_messages()` is called:
   - Calls `thread.get_context()` [CUSTOM - overridden]
   - Custom `get_context()` finds attachment
   - Runs OCR tool on attachment
   - Returns context with `ocr_text` key
3. Calls `assistant.get_evaluated_default_values(context)`
   - Template `{{ ocr_text }}` is evaluated from context
   - OCR text (computed on-the-fly) is injected!
4. Renders `prompt_id.template` with evaluated values
5. Returns messages with OCR text embedded in user message
6. **Auto-triggers** processing with computed OCR data!

---

## Complete Decoder Implementation

### account_move.py

```python
import json
import logging
import re
from odoo import api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def _get_create_document_from_attachment_decoders(self):
        """Register LLM-OCR decoder at priority 15 (after EDI)"""
        res = super()._get_create_document_from_attachment_decoders()

        # Priority 10: EDI (XML formats) - already registered
        # Priority 15: Our LLM-OCR (PDFs with AI)
        res.append((15, self._llm_ocr_decoder_oneshot))

        return res

    @api.model
    def _llm_ocr_decoder_oneshot(self, attachment):
        """
        One-shot LLM-OCR decoder for invoice attachments.

        NOTE: This decoder is registered at priority 15, AFTER EDI (priority 10).
        If EDI successfully processes the attachment (has embedded XML), this decoder
        is never called! We only process attachments that EDI couldn't handle.

        Flow:
        1. Check if suitable for OCR (PDF, image)
        2. Create invoice record for the thread
        3. Create thread with assistant (computes OCR in context)
        4. Call thread.generate(None) - auto-triggers with OCR text
        5. Extract JSON from assistant response
        6. Apply extracted data to invoice

        Args:
            attachment (ir.attachment): Invoice attachment

        Returns:
            account.move: Created invoice (or empty recordset if failed)
        """
        try:
            # 1. Check if we should process this attachment
            if not self._should_process_with_llm_ocr(attachment):
                _logger.info(f"Skipping attachment {attachment.name} - not suitable for LLM-OCR")
                return self.env['account.move']  # Return empty, try next decoder

            # 2. Create draft invoice for the thread to attach to
            invoice = self.create({
                'move_type': 'in_invoice',
                'state': 'draft',
            })

            # 3. Attach the file to invoice (makes it findable by thread.get_context())
            attachment.write({'res_model': 'account.move', 'res_id': invoice.id})

            # 4. Get or create thread for invoice with assistant
            assistant = self.env['llm.assistant'].get_assistant_by_code('invoice_extraction')
            if not assistant:
                _logger.error("Invoice extraction assistant not configured")
                invoice.unlink()
                return self.env['account.move']

            thread = self.env['llm.thread'].create({
                'name': f'Invoice Extraction - {attachment.name}',
                'assistant_id': assistant.id,
                'model_id': assistant.model_id.id,
                'model': 'account.move',
                'res_id': invoice.id,
            })

            # 5. Call generate() - auto-triggers with OCR computed in context
            invoice_data = None
            for response_event in thread.generate(user_message_body=None):
                if response_event.get('type') == 'message_create':
                    message = response_event.get('message', {})
                    if message.get('author_id'):  # Assistant message
                        body = message.get('body', '')
                        invoice_data = self._parse_invoice_json(body)
                        break  # ONE response only!

            # 6. Apply extracted data to invoice
            if invoice_data:
                self._apply_extracted_data(invoice, invoice_data)
                _logger.info(f"Successfully created invoice from {attachment.name}")
                return invoice
            else:
                _logger.warning(f"LLM extraction failed for attachment {attachment.name}")
                invoice.unlink()
                return self.env['account.move']

        except Exception as e:
            _logger.error(f"Error in LLM-OCR decoder: {str(e)}", exc_info=True)
            return self.env['account.move']  # Return empty, try next decoder

    def _should_process_with_llm_ocr(self, attachment):
        """Check if attachment is suitable for LLM-OCR processing

        NOTE: We don't need to check for embedded XML here!
        EDI decoder (priority 10) runs before us (priority 15).
        If EDI succeeds, our decoder never gets called.
        We only see attachments that EDI couldn't process.
        """
        # Only process PDFs and images
        if attachment.mimetype not in ('application/pdf', 'image/png', 'image/jpeg'):
            return False

        return True

    def _extract_invoice_with_assistant_oneshot(self, ocr_text, attachment):
        """Extract invoice data using llm.assistant in one-shot mode"""
        # Get the invoice extraction assistant
        assistant = self.env['llm.assistant'].get_assistant_by_code('invoice_extraction')

        if not assistant:
            raise UserError("Invoice extraction assistant not configured")

        # Create temporary thread (not committed to DB)
        temp_thread = self.env['llm.thread'].new({
            'assistant_id': assistant.id,
            'model_id': assistant.model_id.id,
            'prompt_id': assistant.prompt_id.id,
        })

        # Build user message with OCR text
        user_message = {
            "role": "user",
            "content": f"""Extract invoice data from the following OCR text and return as JSON:

{ocr_text}

Return ONLY the JSON object, no explanations."""
        }

        # Get system prompt from assistant
        prepend_messages = temp_thread.get_prepend_messages()

        # Make ONE chat call (no loop, no streaming, no tools)
        response = assistant.model_id.chat(
            messages=[user_message],
            prepend_messages=prepend_messages,
            stream=False,
            max_tokens=4096,
        )

        # Extract response (generator with single item)
        response_data = next(response)
        response_text = response_data.get('content', '')

        # Parse JSON from response
        return self._parse_invoice_json(response_text)

    def _parse_invoice_json(self, response_text):
        """Parse JSON from LLM response, handling markdown code blocks"""
        # Extract JSON from markdown code blocks if present
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            json_text = json_match.group(1)
        else:
            json_text = response_text.strip()

        try:
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            _logger.error(f"Failed to parse LLM response as JSON: {response_text}")
            raise UserError(f"LLM returned invalid JSON: {str(e)}")

    def _build_ubl_from_invoice_data(self, invoice_data):
        """Build minimal UBL XML tree from extracted invoice data

        Args:
            invoice_data (dict): Extracted invoice data from LLM

        Returns:
            lxml.etree.Element: UBL XML tree
        """
        from lxml import etree

        # Namespaces
        ns = {
            'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
            'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        }

        # Create root element
        root = etree.Element(
            '{urn:oasis:names:specification:ubl:schema:xsd:Invoice-2}Invoice',
            nsmap={
                None: 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2',
                'cac': ns['cac'],
                'cbc': ns['cbc'],
            }
        )

        # Add basic invoice fields
        etree.SubElement(root, f"{{{ns['cbc']}}}ID").text = invoice_data.get('invoice_number', '')
        etree.SubElement(root, f"{{{ns['cbc']}}}IssueDate").text = invoice_data.get('invoice_date', '')

        if invoice_data.get('due_date'):
            etree.SubElement(root, f"{{{ns['cbc']}}}DueDate").text = invoice_data['due_date']

        # Document currency
        currency = invoice_data.get('currency', 'EUR')
        etree.SubElement(root, f"{{{ns['cbc']}}}DocumentCurrencyCode").text = currency

        # Supplier party (vendor)
        supplier_party = etree.SubElement(root, f"{{{ns['cac']}}}AccountingSupplierParty")
        party = etree.SubElement(supplier_party, f"{{{ns['cac']}}}Party")

        # Party name
        party_name = etree.SubElement(party, f"{{{ns['cac']}}}PartyName")
        etree.SubElement(party_name, f"{{{ns['cbc']}}}Name").text = invoice_data.get('vendor_name', '')

        # VAT
        if invoice_data.get('vat'):
            party_tax_scheme = etree.SubElement(party, f"{{{ns['cac']}}}PartyTaxScheme")
            company_id = etree.SubElement(party_tax_scheme, f"{{{ns['cbc']}}}CompanyID")
            company_id.text = invoice_data['vat']

        # Invoice lines
        lines = invoice_data.get('lines', [])
        for idx, line_data in enumerate(lines, start=1):
            invoice_line = etree.SubElement(root, f"{{{ns['cac']}}}InvoiceLine")
            etree.SubElement(invoice_line, f"{{{ns['cbc']}}}ID").text = str(idx)

            # Quantity
            quantity_elem = etree.SubElement(invoice_line, f"{{{ns['cbc']}}}InvoicedQuantity")
            quantity_elem.set('unitCode', 'C62')  # Default unit: items
            quantity_elem.text = str(line_data.get('quantity', 1.0))

            # Line total
            line_extension = etree.SubElement(invoice_line, f"{{{ns['cbc']}}}LineExtensionAmount")
            line_extension.set('currencyID', currency)
            line_extension.text = str(line_data.get('unit_price', 0) * line_data.get('quantity', 1.0))

            # Item
            item = etree.SubElement(invoice_line, f"{{{ns['cac']}}}Item")
            etree.SubElement(item, f"{{{ns['cbc']}}}Description").text = line_data.get('description', '')

            # Price
            price = etree.SubElement(invoice_line, f"{{{ns['cac']}}}Price")
            price_amount = etree.SubElement(price, f"{{{ns['cbc']}}}PriceAmount")
            price_amount.set('currencyID', currency)
            price_amount.text = str(line_data.get('unit_price', 0))

        # Tax total
        tax_total = etree.SubElement(root, f"{{{ns['cac']}}}TaxTotal")
        tax_amount = etree.SubElement(tax_total, f"{{{ns['cbc']}}}TaxAmount")
        tax_amount.set('currencyID', currency)

        # Calculate total tax from lines
        total_tax = sum(line.get('tax_amount', 0) for line in lines)
        tax_amount.text = str(total_tax)

        # Legal monetary total
        legal_total = etree.SubElement(root, f"{{{ns['cac']}}}LegalMonetaryTotal")

        # Tax exclusive amount
        tax_exclusive = etree.SubElement(legal_total, f"{{{ns['cbc']}}}TaxExclusiveAmount")
        tax_exclusive.set('currencyID', currency)
        total_excl_tax = invoice_data.get('total_amount', 0) - total_tax
        tax_exclusive.text = str(total_excl_tax)

        # Tax inclusive amount
        tax_inclusive = etree.SubElement(legal_total, f"{{{ns['cbc']}}}TaxInclusiveAmount")
        tax_inclusive.set('currencyID', currency)
        tax_inclusive.text = str(invoice_data.get('total_amount', 0))

        # Payable amount
        payable = etree.SubElement(legal_total, f"{{{ns['cbc']}}}PayableAmount")
        payable.set('currencyID', currency)
        payable.text = str(invoice_data.get('total_amount', 0))

        return root
```

---

## Summary: Dynamic Context Architecture

### The Complete Flow

```
1. User uploads invoice attachment
   ↓
2. Create thread for invoice with assistant
   ↓
3. Call thread.generate(None)
   ↓
4. get_prepend_messages() chain:
   ├─→ Calls thread.get_context()
   │   ├─→ Finds invoice attachment
   │   ├─→ Runs Mistral OCR tool on-the-fly
   │   └─→ Returns context with 'ocr_text' key
   ├─→ Calls assistant.get_evaluated_default_values(context)
   │   └─→ Evaluates {{ ocr_text }} from context
   └─→ Renders prompt template with OCR text
   ↓
5. Returns: [{type: "system", ...}, {type: "user", content: "Extract from: <OCR TEXT>"}]
   ↓
6. Auto-triggers LLM processing
   ↓
7. Break after first assistant response
   ↓
8. Parse JSON from response
   ↓
9. Apply extracted data to invoice
```

### Key Advantages

**1. Clean Separation of Concerns**:
- OCR computation → `thread.get_context()` override (on-demand)
- System instructions → `llm.prompt` (editable in UI)
- Variable values → `llm.assistant.default_values` (configurable)
- Logic → Python code (clean, focused)

**2. Dynamic Data Injection**:
- `has_dynamic_defaults = True` enables Jinja2 evaluation
- Template expressions: `{{ ocr_text }}` (computed, not stored)
- Context computed on-the-fly from attachment
- OCR text injected at runtime, never persisted

**3. No Storage Overhead**:
- OCR text computed only when needed
- No database field pollution
- Attachment is the single source of truth
- Can re-compute if attachment changes

**4. Testability**:
- Can test OCR computation independently
- Can test prompt template in chat UI with real invoice
- Can test full flow end-to-end
- Can modify prompt without code changes

**5. Maintainability**:
- Update instructions: Edit `default_values` in XML
- Update template: Edit `llm.prompt` in UI
- Update OCR logic: Change `get_context()` override
- Update extraction logic: Change `_apply_extracted_data()`

**6. Reusability**:
- Same assistant for manual chat + automatic processing
- Same OCR computation for any invoice thread
- Same prompt template across different entry points

---

## Comparison Table

| Aspect | Hardcoded Approach | Dynamic Context Approach |
|--------|-------------------|--------------------------|
| **OCR Text** | Passed as parameter | Computed on-the-fly |
| **Storage** | N/A | No storage (computed from attachment) |
| **System Prompt** | Hardcoded in Python | Configured in llm.prompt |
| **Data Injection** | Manual string formatting | Jinja2 template evaluation |
| **Prompt Updates** | Requires code change | Edit in UI |
| **Testing** | Code only | Can test in chat UI |
| **User Message** | Hardcoded in Python | Auto-trigger in template |
| **Configuration** | Scattered | Centralized in assistant |
| **Debugging** | Check logs | Check context + chat history |
| **Performance** | N/A | OCR on-demand (cached in context) |

---

## Next Steps

1. **Override `llm.thread.get_context()`** to compute OCR dynamically
2. **Create prompt template** with `ocr_text` variable
3. **Create assistant** with `has_dynamic_defaults=True`
4. **Set dynamic default**: `"ocr_text": "{{ ocr_text }}"`
5. **Implement `action_process_invoice_with_ai()`**
6. **Test end-to-end** flow

---

## Conclusion

**Dynamic context + auto-trigger** provides the cleanest architecture:
- ✅ **No hardcoded prompts** in Python
- ✅ **No manual user messages** needed
- ✅ **No OCR text storage** (computed on-demand)
- ✅ **Template-based injection** via Jinja2
- ✅ **Fully configurable** via UI
- ✅ **Testable** at every layer
- ✅ **Single source of truth** (attachment only)

This approach leverages the full power of `llm.assistant` infrastructure while maintaining clean separation between OCR computation, prompt configuration, and processing logic. OCR is computed only when needed, directly from the attachment.
