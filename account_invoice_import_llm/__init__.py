import logging

from . import models
from . import wizard

_logger = logging.getLogger(__name__)


def pre_init_hook(cr):
    """
    Pre-installation hook to adopt orphaned records from old module.

    This handles the case where llm_assistant_account_invoice was uninstalled
    but left orphaned records in the database. We handle both cases:
    1. Records with ir_model_data from old module → update module name
    2. Records without ir_model_data → create new ownership
    """
    _logger.info("=" * 80)
    _logger.info("Running pre-init hook for account_invoice_import_llm")
    _logger.info("Adopting orphaned records from previous module")
    _logger.info("=" * 80)

    # Step 1: Update ir_model_data records from old module name
    cr.execute("""
        UPDATE ir_model_data
        SET module = 'account_invoice_import_llm'
        WHERE module = 'llm_assistant_account_invoice'
    """)

    if cr.rowcount > 0:
        _logger.info(f"Updated {cr.rowcount} ir_model_data records from old module")

    # Step 2: Adopt orphaned prompt without ir_model_data
    cr.execute("""
        SELECT id
        FROM llm_prompt
        WHERE name = 'Invoice Data Extraction (One-Shot)'
        AND id NOT IN (
            SELECT res_id FROM ir_model_data
            WHERE model = 'llm.prompt'
        )
    """)

    prompt_record = cr.fetchone()
    if prompt_record:
        prompt_id = prompt_record[0]
        _logger.info(f"Found orphaned llm_prompt (ID: {prompt_id})")

        # Create ir_model_data entry to adopt it
        cr.execute("""
            INSERT INTO ir_model_data (name, module, model, res_id, noupdate)
            VALUES ('llm_prompt_invoice_extraction', 'account_invoice_import_llm', 'llm.prompt', %s, false)
            ON CONFLICT DO NOTHING
        """, (prompt_id,))

        _logger.info(f"Adopted orphaned llm_prompt record (ID: {prompt_id})")

    # Adopt orphaned assistant: "invoice_extraction"
    cr.execute("""
        SELECT id
        FROM llm_assistant
        WHERE code = 'invoice_extraction'
        AND id NOT IN (
            SELECT res_id FROM ir_model_data
            WHERE model = 'llm.assistant'
        )
    """)

    assistant_record = cr.fetchone()
    if assistant_record:
        assistant_id = assistant_record[0]
        _logger.info(f"Found orphaned llm_assistant (ID: {assistant_id})")

        # Create ir_model_data entry to adopt it
        cr.execute("""
            INSERT INTO ir_model_data (name, module, model, res_id, noupdate)
            VALUES ('llm_assistant_invoice_extraction', 'account_invoice_import_llm', 'llm.assistant', %s, false)
            ON CONFLICT DO NOTHING
        """, (assistant_id,))

        _logger.info(f"Adopted orphaned llm_assistant record (ID: {assistant_id})")

    _logger.info("Pre-init hook completed successfully")
    _logger.info("=" * 80)
