import logging
import re

import markdown2

from odoo import models
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    def _message_post_after_hook(self, message, msg_vals):
        """Handle AI agent responses to messages."""
        res = super()._message_post_after_hook(message, msg_vals)

        # Skip if we're installing the module
        if self.env.context.get("module") == "llm_agent":
            return res

        # Skip if message is from an agent (to avoid loops)
        author = message.author_id.user_ids[:1]
        if author.is_user_agent():
            return res

        # Find mentioned agents
        mentioned_partners = message.partner_ids
        mentioned_agents = (
            self.env["res.users"]
            .search(
                [("partner_id", "in", mentioned_partners.ids), ("is_active", "=", True)]
            )
            .filtered(lambda u: u.is_user_agent())
        )

        # Also check for private chat with agent
        if (
            not mentioned_agents
            and self._name == "mail.channel"
            and self.channel_type == "chat"
        ):
            if len(self.channel_partner_ids) == 2:
                other_partner = self.channel_partner_ids - message.author_id
                other_user = self.env["res.users"].search(
                    [("partner_id", "=", other_partner.id), ("is_active", "=", True)],
                    limit=1,
                )
                if other_user and other_user.is_user_agent():
                    mentioned_agents = other_user

        # Generate AI response for each mentioned agent
        for agent in mentioned_agents:
            if agent.model_id:  # Only respond if agent has a model configured
                try:
                    # Get AI response (non-streaming for hook)
                    accumulated_content = ""
                    for response in self.generate_ai_response(agent, message, msg_vals):
                        if response.get("error"):
                            _logger.error(
                                "Error getting AI response: %s", response["error"]
                            )
                            break

                        content = response.get("content", "")
                        if content:
                            accumulated_content += content

                    # Post accumulated response
                    if accumulated_content:
                        self.with_context(
                            mail_create_nosubscribe=True
                        )._post_ai_response(
                            content=accumulated_content,
                            author=agent,
                            parent_id=message.id,
                        )

                except Exception:
                    _logger.exception("Failed to generate AI response")
            else:
                _logger.warning(
                    "Agent %s has no model configured, skipping response", agent.name
                )

        return res

    def _get_message_role(self, message_author, agent):
        """Determine the role of a message based on its author.

        Args:
            message_author (res.users): Author of the message
            agent (res.users): The AI agent user

        Returns:
            str: 'assistant' if message is from agent, 'user' otherwise
        """
        return "assistant" if message_author == agent else "user"

    def _get_message_history_domain(self, agent):
        """Get domain for fetching message history.

        Args:
            agent (res.users): The AI agent user

        Returns:
            list: Domain for message search
        """
        domain = [("model", "=", self._name), ("res_id", "=", self.id)]

        if self._name == "mail.channel":
            # For channels, only include messages after the agent joined
            membership = self.env["mail.channel.member"].search(
                [
                    ("channel_id", "=", self.id),
                    ("partner_id", "=", agent.partner_id.id),
                ],
                limit=1,
            )
            if membership:
                domain.append(("create_date", ">=", membership.create_date))

        return domain

    def _clean_message_content(self, content):
        """Clean message content by removing HTML and unnecessary markup.

        Args:
            content: Message content that may contain HTML

        Returns:
            str: Cleaned message content
        """
        if not content:
            return ""

        # Convert HTML to plain text using Odoo's built-in function
        text = html2plaintext(str(content))
        # Clean up any remaining markup artifacts
        text = text.replace("Markup(", "").replace(")", "")
        return text.strip()

    def _prepare_chat_messages(self, agent, message, msg_vals):
        """Prepare messages for chat completion.

        Args:
            agent (res.users): The AI agent user
            message (mail.message): Current message
            msg_vals (dict): Message values

        Returns:
            list: List of message dictionaries for chat completion
        """
        messages = []

        # Add system prompt if configured
        if agent.system_prompt:
            messages.append({"role": "system", "content": agent.system_prompt})

        # Get last 20 messages from the thread
        domain = self._get_message_history_domain(agent)
        history = self.env["mail.message"].search(domain, order="id DESC", limit=20)

        # Add messages in chronological order (oldest first)
        for msg in reversed(history):
            msg_author = msg.author_id.user_ids[:1]
            role = self._get_message_role(msg_author, agent)
            content = self._clean_message_content(msg.body)
            if content:
                messages.append({"role": role, "content": content})

        # Add the current message
        message_author = message.author_id.user_ids[:1]
        role = self._get_message_role(message_author, agent)

        return messages

    def generate_ai_response(self, agent, message, msg_vals):
        """Generate AI response using the agent's configured model.

        Args:
            agent (res.users): The AI agent user
            message (mail.message): The message to respond to
            msg_vals (dict): Message values including body

        Returns:
            generator: Yields response chunks with content or error
        """
        try:
            # Prepare messages for the LLM
            messages = self._prepare_chat_messages(agent, message, msg_vals)

            return agent.model_id.chat(messages=messages)
        except Exception as e:
            _logger.exception("Failed to generate AI response")
            return {"error": str(e)}

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
