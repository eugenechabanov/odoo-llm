import logging
import re

import markdown2

from odoo import models, api, tools, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        return super(MailThread, self).message_post(**kwargs)

    def _message_post_after_hook(self, message, msg_vals):
        """Handle AI agent responses to messages and LLM agent mentions."""
        res = super()._message_post_after_hook(message, msg_vals)

        try:
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
                agent_config = agent.agent_config_id
                if not agent_config:
                    _logger.warning("Agent %s has no configuration, skipping response", agent.name)
                    continue
                    
                if agent_config.model_id:  # Only respond if agent has a model configured
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
                        "Agent %s has no model configured in their configuration, skipping response", agent.name
                    )

            # Check for LLM agent mentions
            if msg_vals.get('partner_ids'):
                mentioned_partners = self.env['res.partner'].browse(msg_vals['partner_ids'])
                mentioned_users = self.env['res.users'].search([
                    ('partner_id', 'in', mentioned_partners.ids),
                    ('is_agent', '=', True)
                ])
                
                if mentioned_users:
                    # Get the message content without HTML tags
                    body = tools.html2plaintext(msg_vals['body'])
                    
                    # Create and execute task for each mentioned agent
                    for agent in mentioned_users:
                        try:
                            # Create task
                            task = self.env['llm.agent.task'].create({
                                'name': f"Response to mention in {self._description}",
                                'description': body,
                                'agent_id': agent.id,
                                'expected_output': "Provide a helpful response to the user's message",
                                'output_format': 'raw',
                                'state': 'pending',
                                'prompt_context': f"""This task was created in response to a mention in a {self._description}.
                                Model: {self._name}
                                Record ID: {self.id}
                                Message ID: {message.id}
                                """,
                                'conversation_history': f"Original message: {body}"
                            })
                            
                            # Execute task synchronously
                            task.action_start()
                            
                            if task.state == 'failed':
                                error_msg = _("Task execution failed for agent %s") % agent.name
                                if task.output_raw:
                                    error_msg += f": {task.output_raw}"
                                raise UserError(error_msg)
                            
                            # Post the response
                            if task.state == 'completed' and task.output_raw:
                                self.message_post(
                                    body=task.output_raw,
                                    message_type='comment',
                                    subtype_xmlid='mail.mt_comment',
                                    author_id=agent.partner_id.id
                                )
                            else:
                                raise UserError(_("Task completed but no output was generated for agent %s") % agent.name)
                                
                        except Exception as e:
                            # Log the error and notify in the thread
                            _logger.error("Error processing LLM agent task: %s", str(e))
                            self.message_post(
                                body=_("Error processing request for agent %s: %s") % (agent.name, str(e)),
                                message_type='comment',
                                subtype_xmlid='mail.mt_comment'
                            )
                            
        except Exception as e:
            # Log any unexpected errors
            _logger.error("Unexpected error in _message_post_after_hook: %s", str(e))
            self.message_post(
                body=_("An unexpected error occurred while processing the LLM agent mention: %s") % str(e),
                message_type='comment',
                subtype_xmlid='mail.mt_comment'
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
        text = tools.html2plaintext(str(content))
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
        
        # Get agent configuration
        agent_config = agent.agent_config_id
        if not agent_config:
            raise ValidationError(_("Agent %s has no configuration") % agent.name)
            
        # Add system context as first message
        messages.append({"role": "system", "content": agent_config.get_context_prompt()})

        # Add custom system prompt if configured
        if agent_config.system_prompt:
            messages.append({"role": "system", "content": agent_config.system_prompt})

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
            
            agent_config = agent.agent_config_id
            if not agent_config or not agent_config.model_id:
                return {"error": f"Agent {agent.name} has no model configured"}

            return agent_config.model_id.chat(messages=messages)
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
