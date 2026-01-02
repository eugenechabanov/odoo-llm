"""
Migration script for llm_assistant_account_invoice 16.0.1.0.1

Removes threads and messages referencing the old interactive assistant before deletion.
This prevents foreign key constraint violations during module upgrade.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Pre-migration: Clean up threads referencing old interactive assistant"""

    if not version:
        return

    _logger.info("=" * 80)
    _logger.info("Running pre-migration for llm_assistant_account_invoice 16.0.1.0.1")
    _logger.info("=" * 80)

    # Find the old assistant ID
    cr.execute("""
        SELECT res_id
        FROM ir_model_data
        WHERE module = 'llm_assistant_account_invoice'
        AND name = 'llm_assistant_invoice_analyzer'
        AND model = 'llm.assistant'
    """)

    result = cr.fetchone()
    if not result:
        _logger.info("Old assistant not found - nothing to clean up")
        return

    old_assistant_id = result[0]
    _logger.info(f"Found old assistant ID: {old_assistant_id}")

    # Find threads referencing the old assistant
    cr.execute("""
        SELECT id FROM llm_thread
        WHERE assistant_id = %s
    """, (old_assistant_id,))

    thread_ids = [row[0] for row in cr.fetchall()]

    if not thread_ids:
        _logger.info("No threads found referencing old assistant")
        return

    _logger.info(f"Found {len(thread_ids)} thread(s) to delete: {thread_ids}")

    # Delete messages from these threads first (to avoid FK violations)
    cr.execute("""
        DELETE FROM mail_message
        WHERE model = 'llm.thread'
        AND res_id IN %s
    """, (tuple(thread_ids),))

    deleted_messages = cr.rowcount
    _logger.info(f"Deleted {deleted_messages} message(s) from threads")

    # Delete the threads
    cr.execute("""
        DELETE FROM llm_thread
        WHERE id IN %s
    """, (tuple(thread_ids),))

    deleted_threads = cr.rowcount
    _logger.info(f"Deleted {deleted_threads} thread(s)")

    # Also clean up any ir.model.data entries for these threads
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE model = 'llm.thread'
        AND res_id IN %s
    """, (tuple(thread_ids),))

    deleted_data = cr.rowcount
    if deleted_data > 0:
        _logger.info(f"Deleted {deleted_data} ir.model.data record(s)")

    _logger.info("=" * 80)
    _logger.info("Pre-migration completed successfully")
    _logger.info("=" * 80)
