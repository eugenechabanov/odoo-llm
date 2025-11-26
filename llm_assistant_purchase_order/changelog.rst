16.0.1.0.1 (2025-11-27)
~~~~~~~~~~~~~~~~~~~~~~~

* [FIX] Updated assistant instructions to enforce required fields for PO lines
* [FIX] product_id, product_uom, and date_planned are now marked as REQUIRED
* [ADD] Added Step 4b for creating products when not found in database
* [DOC] Updated ASSISTANT_PROMPT.md with critical required fields documentation

16.0.1.0.0 (2025-11-26)
~~~~~~~~~~~~~~~~~~~~~~~

* [INIT] Initial release of the module
* [ADD] AI-powered purchase order assistant for processing vendor quotations
* [ADD] OCR document parsing for vendor quotation PDFs
* [ADD] Automated product matching with vendor pricing validation
* [ADD] Historical price comparison and deviation alerts
* [ADD] Integration with llm.assistant.action.mixin for seamless AI chat
