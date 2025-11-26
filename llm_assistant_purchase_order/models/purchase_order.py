from odoo import models


class PurchaseOrder(models.Model):
    _name = "purchase.order"
    _inherit = ["purchase.order", "llm.assistant.action.mixin"]

    def action_process_with_ai(self):
        """
        Parse vendor quotation with AI assistant.
        Creates a fresh thread every time (no context carryover).
        Frontend opens AI chat for OCR parsing and follow-up questions.
        """
        return self.action_open_llm_assistant(
            "odoo_purchase_order_assistant", force_new_thread=True
        )
