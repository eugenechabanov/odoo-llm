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
        _logger.info("Starting _message_post_after_hook for message ID: %s", message.id)

        try:
            # Skip if we're installing the module
            if self.env.context.get("module") == "llm_agent":
                _logger.info("Skipping hook - module installation context detected")
                return res

            # Skip if message is from an agent (to avoid loops)
            author = message.author_id.user_ids[:1]
            _logger.info("Message author: %s (is_agent: %s)", author.name, author.is_user_agent())
            if author.is_user_agent():
                _logger.info("Skipping hook - message is from an agent")
                return res

            # Detect and save user preferences
            contextual_memory = self.env['llm.memory.contextual']
            message_data = {
                'body': message.body,
                'subject': message.subject,
                'email_from': message.email_from,
            }
            contextual_memory.detect_and_save_preferences('message', message_data, author)

            # Find mentioned agents
            mentioned_partners = message.partner_ids
            _logger.info("Mentioned partners: %s", mentioned_partners.mapped('name'))
            mentioned_agents = (
                self.env["res.users"]
                .search(
                    [("partner_id", "in", mentioned_partners.ids), ("is_active", "=", True)]
                )
                .filtered(lambda u: u.is_user_agent())
            )
            _logger.info("Found mentioned agents: %s", mentioned_agents.mapped('name'))

            # Also check for private chat with agent
            if (
                not mentioned_agents
                and self._name == "mail.channel"
                and self.channel_type == "chat"
            ):
                _logger.info("Checking private chat channel")
                if len(self.channel_partner_ids) == 2:
                    other_partner = self.channel_partner_ids - message.author_id
                    _logger.info("Found other chat partner: %s", other_partner.name)
                    other_user = self.env["res.users"].search(
                        [("partner_id", "=", other_partner.id), ("is_active", "=", True)],
                        limit=1,
                    )
                    if other_user and other_user.is_user_agent():
                        _logger.info("Other chat partner is an agent: %s", other_user.name)
                        mentioned_agents = other_user

            # Process mentioned agents
            for agent in mentioned_agents:
                try:
                    _logger.info("Processing agent: %s", agent.name)
                    self._process_agent_response(agent, message, msg_vals)
                except Exception as e:
                    _logger.error("Error processing agent %s: %s", agent.name, str(e))

        except Exception as e:
            # Log any unexpected errors
            _logger.error("Unexpected error in _message_post_after_hook: %s", str(e))
            self.message_post(
                body=_("An unexpected error occurred while processing the LLM agent mention: %s") % str(e),
                message_type='comment',
                subtype_xmlid='mail.mt_comment'
            )

        return res

    def _validate_agent_config(self, agent):
        """Validate agent configuration and model.
        
        Args:
            agent (res.users): The AI agent user
            
        Returns:
            tuple: (agent_config, error_message)
        """
        agent_config = agent.agent_config_id
        if not agent_config:
            error = f"Agent {agent.name} has no configuration"
            _logger.error(error)
            return None, error
            
        if not agent_config.model_id:
            error = f"Agent {agent.name} has no model configured"
            _logger.error(error)
            return None, error
            
        return agent_config, None

    def generate_ai_response(self, agent, message, msg_vals):
        """Generate AI response using the agent's configured model."""
        try:
            _logger.info("Starting AI response generation for agent %s", agent.name)
            
            # Validate agent configuration
            agent_config, error = self._validate_agent_config(agent)
            if error:
                yield {"error": error}
                return

            # Prepare messages and generate response
            messages = self._prepare_chat_messages(agent, message, msg_vals)
            _logger.info("Prepared %d messages for chat completion", len(messages))
            response_generator = agent_config.model_id.chat(messages=messages)
            _logger.info("Successfully initiated chat completion")
            
            for response in response_generator:
                _logger.debug("Received response chunk: %s", response)
                yield response

        except Exception as e:
            _logger.exception("Failed to generate AI response for agent %s", agent.name)
            yield {"error": str(e)}

    def _process_agent_response(self, agent, message, msg_vals):
        """Process agent response using task system."""
        try:
            _logger.info("Processing agent response for agent %s", agent.name)
            
            # Validate agent configuration
            agent_config, error = self._validate_agent_config(agent)
            if error:
                raise ValidationError(error)

            # Create and execute task
            task = self.env['llm.agent.task'].create({
                'name': f"Response to message in {self._description}",
                'description': self._clean_message_content(msg_vals.get('body', '')),
                'agent_id': agent.id,
                'expected_output': "Provide a helpful response to the user's message",
                'output_format': 'raw',
                'state': 'pending',
                'input': msg_vals.get('body', ''),
                'prompt_context': f"""This task was created in response to a message in {self._description}.
                Model: {self._name}
                Record ID: {self.id if hasattr(self, 'id') else 'N/A'}
                Message ID: {message.id}
                """,
                'conversation_history': self._prepare_chat_messages(agent, message, msg_vals),
                'message_id': message.id if message else None,
            })
            
            # Execute task synchronously
            task.action_start()
            
            if task.state == 'failed':
                error_msg = _("Task execution failed for agent %s") % agent.name
                if task.error:
                    error_msg += f": {task.error}"
                raise ValidationError(error_msg)
            
            # Post the response
            if task.state == 'done' and task.output:
                self.with_context(
                    mail_create_nosubscribe=True
                )._post_ai_response(
                    content=task.output,
                    author=agent,
                    parent_id=message.id,
                )
            else:
                _logger.warning("Task state is not 'done' or 'failed': %s", task.state)
                _logger.info("Task output: %s", task.output)
                raise ValidationError(_("Task completed but no output was generated for agent %s") % agent.name)

        except Exception as e:
            _logger.exception("Failed to process agent response for agent %s", agent.name)
            raise e

    def _get_message_role(self, message_author, agent):
        """Determine the role of a message based on its author.

        Args:
            message_author (res.users): Author of the message
            agent (res.users): The AI agent user

        Returns:
            str: 'assistant' if message is from agent, 'user' otherwise
        """
        return "assistant" if message_author == agent else "user"

    def _get_message_history_domain(self, agent, message=None):
        if message:
            # If we have a message, get history from its thread
            domain = [("model", "=", message.model), ("res_id", "=", message.res_id)]
        elif hasattr(self, 'id') and self.id:
            # Get from current record's thread if it exists
            domain = [("model", "=", self._name), ("res_id", "=", self.id)]
        else:
            # Return empty domain if no valid thread context
            domain = [("id", "=", False)]  # Will return no messages

        if self._name == "mail.channel" and hasattr(self, 'id') and self.id:
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

    def _get_message_content(self, message, msg_vals):
        """Get message content from either msg_vals or message."""
        return self._clean_message_content(
            msg_vals.get('body', '') if msg_vals else message.body
        )

    def _prepare_chat_messages(self, agent, message, msg_vals):
        """Prepare messages for chat completion."""
        _logger.info("Preparing chat messages for agent %s", agent.name)
        messages = []
        
        # Get agent configuration
        agent_config = agent.agent_config_id
        if not agent_config:
            _logger.error("Agent %s has no configuration", agent.name)
            raise ValidationError(_("Agent %s has no configuration") % agent.name)
            
        # Add system context as first message
        _logger.info("Adding system context from agent configuration")
        messages.append({"role": "system", "content": agent_config.get_context_prompt()})

        # Add custom system prompt if configured
        if agent_config.system_prompt:
            _logger.info("Adding custom system prompt")
            messages.append({"role": "system", "content": agent_config.system_prompt})

        # Get relevant memories if this is a task
        if hasattr(self, '_name') and self._name == 'llm.agent.task':
            _logger.info("Adding memory context for task")
            if hasattr(self, 'memory_context'):
                memory_context = self.memory_context
            else:
                # Determine the user for context
                message_user = None
                if message.author_id:
                    if hasattr(message, 'create_uid') and message.create_uid:
                        message_user = message.create_uid
                    elif message.author_id.user_id:
                        message_user = message.author_id.user_id
                
                # If no message user or the user is an agent, use the task creator
                if not message_user or message_user.is_agent:
                    message_user = self.create_uid
                
                message_content = self._get_message_content(message, msg_vals) if message_user else None
                
                memory_context = self.env['llm.memory.contextual'].build_context_for_task(
                    self.id,
                    user=message_user,
                    message_content=message_content
                )
            
            if memory_context:
                messages.append({
                    "role": "system",
                    "content": f"Previous relevant context:\n{memory_context}"
                })

        # Get last 20 messages from the thread
        domain = self._get_message_history_domain(agent, message)
        history = self.env["mail.message"].search(domain, order="id DESC", limit=20)
        _logger.info("Found %d historical messages", len(history))

        # Add messages in chronological order (oldest first)
        for msg in reversed(history):
            msg_author = msg.author_id.user_ids[:1]
            role = self._get_message_role(msg_author, agent)
            content = self._clean_message_content(msg.body)
            if content:
                _logger.debug("Adding message: role=%s, content_length=%d", role, len(content))
                messages.append({"role": role, "content": content})

        # Add current message if we have msg_vals
        if msg_vals and msg_vals.get('body'):
            messages.append({
                "role": "user", 
                "content": self._get_message_content(message, msg_vals)
            })

        _logger.info("Prepared total of %d messages for chat completion", len(messages))
        return messages

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
