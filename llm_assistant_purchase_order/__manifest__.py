{
    "name": "LLM Purchase Order Assistant",
    "summary": "AI-powered purchase order assistant with OCR document parsing",
    "description": """
        Intelligent purchase order assistant that helps create and process purchase orders
        from vendor quotation documents using AI. Features document parsing with OCR,
        automated data extraction, product matching, and smart validation.
    """,
    "category": "Inventory/Purchase/AI",
    "version": "18.0.1.0.0",
    "depends": [
        "purchase",  # Purchase Order model (purchase.order)
        "llm_assistant",  # Includes llm, llm_thread, llm_tool
        "llm_tool_ocr_mistral",  # OCR tool
    ],
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "data": [
        "data/llm_prompt_po_data.xml",
        "data/llm_assistant_data.xml",
        "views/purchase_order_views.xml",
    ],
    "images": [
        "static/description/banner.jpeg",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
}
