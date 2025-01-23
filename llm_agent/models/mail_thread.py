from odoo import models, api
import logging
import re

import markdown2

_logger = logging.getLogger(__name__)


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _message_post_after_hook(self, message, msg_vals):
        """Handle AI agent responses to messages."""
        res = super()._message_post_after_hook(message, msg_vals)

        # Skip if we're installing the module
        if self.env.context.get('module') == 'llm_agent':
            return res

        # Skip if message is from an agent (to avoid loops)
        author = message.author_id.user_ids and message.author_id.user_ids[0]
        if not author or author.is_user_agent():
            return res

        # Find mentioned agents
        mentioned_partners = message.partner_ids
        mentioned_agents = self.env['res.users'].search([
            ('partner_id', 'in', mentioned_partners.ids),
            ('is_active', '=', True)
        ]).filtered(lambda u: u.is_user_agent())

        # Also check for private chat with agent
        if not mentioned_agents and self._name == 'mail.channel' and self.channel_type == 'chat':
            if len(self.channel_partner_ids) == 2:
                other_partner = self.channel_partner_ids - message.author_id
                other_user = self.env['res.users'].search([
                    ('partner_id', '=', other_partner.id),
                    ('is_active', '=', True)
                ], limit=1)
                if other_user and other_user.is_user_agent():
                    mentioned_agents = other_user

        # Generate debug response for each mentioned agent
        for agent in mentioned_agents:
            if agent.model_id:  # Only respond if agent has a model configured
                debug_response = f"Debug: Agent {agent.name} would respond using {agent.model_id.name}\nMessage received: {msg_vals.get('body', '')}"
                self._post_ai_response(
                    content=debug_response,
                    author=agent,
                    parent_id=message.id
                )
            else:
                _logger.warning("Agent %s has no model configured, skipping response", agent.name)

        return res

    def _markdown_to_html(self, content):
        """Convert markdown content to HTML suitable for Odoo messages.

        Args:
            content (str): Markdown formatted content

        Returns:
            str: HTML content wrapped in appropriate Odoo classes
        """
        # Convert markdown to HTML with extras for better formatting
        html_content = markdown2.markdown(
            content,
            extras=[
                "fenced-code-blocks",  # Support ```code blocks```
                "tables",  # Support markdown tables
                "break-on-newline",  # Convert newlines to <br>
                "header-ids",  # Add ids to headers
                "code-friendly",  # Better code block handling
                "smarty-pants",  # Smart quotes, dashes, etc.
            ],
        )

        # Clean up any existing div wrappers
        html_content = re.sub(r"<div[^>]*>", "", html_content)
        html_content = html_content.replace("</div>", "")

        # Wrap code blocks with pre tags and add syntax highlighting class
        html_content = html_content.replace(
            "<code>", '<pre class="o_codeblock"><code>'
        ).replace("</code>", "</code></pre>")

        # Ensure proper wrapping without double-escaping
        return f'<div class="o_mail_note_content">{html_content}</div>'

    def _post_ai_response(self, content, author, parent_id=None):
        """Post AI response message with proper settings.
        
        Args:
            content (str): Message content in markdown format
            author (res.users): The AI agent user posting the message
            parent_id (int, optional): ID of the parent message to reply to
        """
        safe_content = self._markdown_to_html(content)

        return self.message_post(
            body=safe_content,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            author_id=author.partner_id.id,
            parent_id=parent_id,
            partner_ids=[],  # No additional notifications
        )