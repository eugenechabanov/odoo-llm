{
    "name": "LLM Invoice Assistant",
    "summary": "AI-powered invoice analysis assistant with OCR document parsing",
    "description": """
        Intelligent invoice assistant that helps analyze vendor bills and invoices using AI.
        Features document parsing with OCR, automated data extraction, and smart invoice validation.
    """,
    "category": "Accounting/AI",
    "version": "16.0.1.0.2",
    "depends": [
        "account",  # Invoice model (account.move)
        "account_edi",  # EDI integration for decoder chain and UBL processing
        "account_edi_ubl_cii",  # UBL 2.0 XML processing
        "llm_assistant",  # Includes llm, llm_thread, llm_tool
        "llm_tool_ocr_mistral",  # OCR tool
    ],
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "data": [
        "data/llm_prompt_invoice_data.xml",
        "data/llm_assistant_data.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
    "images": [
        "static/description/banner.jpeg",
    ],
}
