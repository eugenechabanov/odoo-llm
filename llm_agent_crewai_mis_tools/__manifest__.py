{
    "name": "LLM Agent CrewAI MIS Tools",
    "version": "16.0.1.0.0",
    "category": "Accounting/Reports",
    "summary": "CrewAI tools for MIS Builder report generation",
    "description": """
        This module provides CrewAI tools for generating MIS Builder reports:
        - MIS Template Generator: Create MIS report templates
        - MIS Report Instance Generator: Create report instances from templates
    """,
    "author": "Apexive",
    "website": "https://www.apexive.com",
    "depends": [
        "base",
        "base_accounting_kit",  # For MIS report generation
        "mis_builder",  # For MIS report generation
        "mis_builder_demo",  # For MIS report generation
        "llm_agent",  # Base LLM agent functionality
        "llm_agent_crewai",  # CrewAI integration
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/llm_agent_tool_data.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}
