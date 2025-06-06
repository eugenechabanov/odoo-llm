{
     "name": "LLM Job Management",
    "summary": "Base and generation jobs for LLM providers",
    "description": "Base and generation jobs for LLM providers",
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "category": "Technical",
    "version": "16.0.1.1.0",
    "depends": ["llm", "llm_thread"],
    "data": [
        "security/ir.model.access.csv",
        "views/llm_generate_job_view.xml",
        "data/ir_cron.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "images": [
        "static/description/banner.jpeg",
    ],
}
