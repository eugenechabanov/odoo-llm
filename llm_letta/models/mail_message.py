import logging

from odoo import models, tools

_logger = logging.getLogger(__name__)


class MailMessage(models.Model):
    _inherit = "mail.message"

    def letta_format_message(self):
        """Provider-specific formatting for Letta."""
        self.ensure_one()
        body = self.body
        if body:
            body = tools.html2plaintext(body)

        if self.is_llm_user_message()[self]:
            formatted_message = {"role": "user"}
            if body:
                formatted_message["content"] = body
            return formatted_message

        elif self.is_llm_assistant_message()[self]:
            formatted_message = {"role": "assistant"}
            formatted_message["content"] = body

            # Note: Letta handles tool calls differently than OpenAI
            # For now, we'll keep it simple and not include tool calls

            return formatted_message

        elif self.is_llm_tool_message()[self]:
            # Format tool messages for Letta (similar to OpenAI format)
            tool_data = self.body_json
            if not tool_data:
                _logger.warning(
                    f"Letta Format: Skipping tool message {self.id}: no tool data found."
                )
                return None

            tool_call_id = tool_data.get("tool_call_id")
            if not tool_call_id:
                _logger.warning(
                    f"Letta Format: Skipping tool message {self.id}: missing tool_call_id."
                )
                return None

            # Get result content
            if "result" in tool_data:
                content = str(tool_data["result"])  # Letta prefers string content
            elif "error" in tool_data:
                content = f"Error: {tool_data['error']}"
            else:
                content = ""

            formatted_message = {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": content,
            }
            return formatted_message

        else:
            return None
