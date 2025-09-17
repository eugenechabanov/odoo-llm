import json
import logging
from datetime import datetime, timedelta

import yaml

from odoo import api, fields, models
from odoo.exceptions import UserError

# Import render_template from llm_assistant utils
from odoo.addons.llm_assistant.utils import render_template

_logger = logging.getLogger(__name__)

# Constants
LETTA_SERVICE = "letta"
DEFAULT_API_KEY_DURATION = 90.0
LETTA_AGENT_KEY_PREFIX = "Letta Agent - Thread"
DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-3-small"

# Default memory block values
DEFAULT_PERSONA_BLOCK = "I am a helpful AI assistant."
DEFAULT_HUMAN_BLOCK_TEMPLATE = "The human's name is {user_name}."


class LLMThread(models.Model):
    _inherit = "llm.thread"

    external_id = fields.Char(
        string="External ID",
        help="External system identifier (e.g., Letta agent ID)",
        index=True,
    )
    metadata = fields.Json(
        string="Metadata",
        help="Store additional data like API keys for Letta agents",
    )
    is_letta_provider = fields.Boolean(
        string="Is Letta Provider",
        compute="_compute_is_letta_provider",
        store=False,
    )

    @api.depends("provider_id.service")
    def _compute_is_letta_provider(self):
        """Compute if thread uses Letta provider"""
        for thread in self:
            thread.is_letta_provider = (
                thread.provider_id and thread.provider_id.service == LETTA_SERVICE
            )

    def _prepare_chat_kwargs(self, message_history, use_streaming):
        """Override to add thread context for Letta provider."""
        chat_kwargs = super()._prepare_chat_kwargs(message_history, use_streaming)

        # Add thread context for Letta
        if self.provider_id.service == LETTA_SERVICE:
            chat_kwargs["thread_context"] = {"id": self.id}

        return chat_kwargs

    # Metadata helper methods
    def _get_stored_api_key(self, thread):
        """Get API key from thread metadata"""
        if thread.metadata and thread.metadata.get("api_key"):
            return thread.metadata["api_key"]
        return None

    def _store_api_key(self, thread, api_key, api_key_id):
        """Store API key info in thread metadata"""
        thread.metadata = {"api_key": api_key, "api_key_id": api_key_id}

    def _clear_api_key_metadata(self, thread):
        """Clear API key from thread metadata"""
        thread.metadata = {}

    def _get_api_key_name(self, thread_id):
        """Get standardized API key name for thread"""
        return f"{LETTA_AGENT_KEY_PREFIX} {thread_id}"

    @api.model_create_multi
    def create(self, vals_list):
        """Override to create Letta agents when thread is created with Letta provider."""
        threads = super().create(vals_list)

        for thread in threads:
            if thread.provider_id.service == LETTA_SERVICE:
                agent_id = self._create_letta_agent(thread)
                if agent_id:
                    thread.external_id = agent_id

        return threads

    def write(self, vals):
        """Override to handle model/provider changes that require agent recreation."""
        # Handle provider changes first
        self._handle_provider_change(vals)

        result = super().write(vals)

        # Handle Letta-specific updates after write
        if "provider_id" in vals or "model_id" in vals or "assistant_id" in vals:
            self._handle_model_or_provider_change()

        if "tool_ids" in vals:
            self._handle_tool_changes()

        # Note: Changes to assistant.prompt_id or assistant.default_values
        # would require manual agent recreation via UI action

        return result

    def _handle_provider_change(self, vals):
        """Handle cleanup when switching away from Letta provider"""
        if "provider_id" not in vals:
            return

        for thread in self:
            if thread.provider_id.service == LETTA_SERVICE:
                new_provider = self.env["llm.provider"].browse(vals["provider_id"])
                if new_provider.service != LETTA_SERVICE:
                    self._cleanup_letta_resources(thread)

    def _handle_model_or_provider_change(self):
        """Handle agent updates when model or provider changes"""
        for thread in self:
            if thread.provider_id.service == LETTA_SERVICE:
                self._update_or_create_agent(thread)

    def _handle_tool_changes(self):
        """Handle tool synchronization for Letta agents"""
        for thread in self:
            if thread.provider_id.service == LETTA_SERVICE and thread.external_id:
                thread.provider_id.letta_sync_agent_tools(
                    thread.external_id, thread.tool_ids
                )

    def _update_or_create_agent(self, thread):
        """Update existing agent or create new one"""
        if thread.external_id:
            # Agent exists - update it
            client = thread.provider_id.letta_get_client()

            # Build system instruction for updates
            system_instruction = None
            if thread.assistant_id and thread.assistant_id.prompt_id:
                context = thread.get_context()
                system_instruction = render_template(
                    template=thread.assistant_id.prompt_id.template, context=context
                )

            modify_params = {
                "agent_id": thread.external_id,
                "model": thread.model_id.name,
            }
            if system_instruction:
                modify_params["system"] = system_instruction

            client.agents.modify(**modify_params)
        else:
            # No agent exists - create one
            agent_id = self._create_letta_agent(thread)
            thread.external_id = agent_id

    def unlink(self):
        """Clean up Letta resources when thread is deleted"""
        for thread in self:
            if thread.provider_id.service == LETTA_SERVICE:
                self._cleanup_letta_resources(thread)
        return super().unlink()

    def _cleanup_letta_resources(self, thread):
        """Clean up API keys and Letta agent when thread is deleted or provider changed"""
        # Delete API key if exists
        if thread.metadata and thread.metadata.get("api_key_id"):
            api_key_record = (
                self.env["res.users.apikeys"]
                .sudo()
                .browse(thread.metadata["api_key_id"])
            )
            if api_key_record.exists():
                api_key_record.unlink()

        # Delete Letta agent if exists (allow this to fail silently as resource might be already gone)
        if thread.external_id:
            try:
                client = thread.provider_id.letta_get_client()
                client.agents.delete(thread.external_id)
                _logger.info(f"Deleted Letta agent {thread.external_id}")
            except Exception:
                # Agent might already be deleted or server unreachable - this is OK during cleanup
                _logger.debug(
                    f"Could not delete Letta agent {thread.external_id} (may already be gone)"
                )

        # Clear metadata and external_id
        self._clear_api_key_metadata(thread)
        thread.external_id = False

    def _create_letta_agent(self, thread):
        """Create a Letta agent for the given thread.

        Args:
            thread: llm.thread record

        Returns:
            str: Agent ID if successful, None otherwise
        """
        if not thread.model_id:
            return None

        # Get Letta client from provider
        client = thread.provider_id.letta_get_client()
        # Build agent configuration
        agent_config = self._build_agent_config(thread)
        # Create agent
        agent = client.agents.create(**agent_config)
        agent_id = agent.id

        # Sync tools after creation if thread has any
        if thread.tool_ids:
            thread.provider_id.letta_sync_agent_tools(agent_id, thread.tool_ids)

        return agent_id

    def _build_agent_config(self, thread):
        """Build agent configuration from thread context.

        Args:
            thread: llm.thread record

        Returns:
            dict: Agent configuration for Letta API
        """
        # Get Letta-specific context using hook method
        letta_context = thread.letta_get_agent_config_context()
        full_context = thread.get_context(letta_context)

        # Build memory blocks and system instruction
        memory_blocks = None
        system_instruction = None

        if thread.assistant_id and thread.assistant_id.prompt_id:
            prompt = thread.assistant_id.prompt_id
            # Pass the full context (including user context) to assistant for default value evaluation
            evaluated_values = thread.assistant_id.get_evaluated_default_values(full_context)

            # Check if prompt is Letta-compatible (has memory_blocks structure)
            if self._is_letta_compatible_prompt(prompt, full_context):
                # Letta-compatible: extract memory blocks
                try:
                    messages = prompt.get_messages(evaluated_values)
                    memory_blocks = self._extract_memory_blocks_from_messages(messages, prompt)
                    if not memory_blocks:
                        # Fallback to simple persona/human from default_values
                        memory_blocks = self._build_memory_blocks_from_defaults(evaluated_values, thread)
                except Exception as e:
                    _logger.warning(
                        "Error extracting memory blocks from Letta prompt %s: %s",
                        prompt.name, str(e)
                    )
                    # Fallback to hardcoded defaults
                    memory_blocks = self._get_default_memory_blocks(thread)
            else:
                # Traditional prompt: render as system instruction
                
                system_instruction = render_template(
                    template=prompt.template, context=full_context
                )
                

                # Use default memory blocks for traditional prompts
                memory_blocks = self._get_default_memory_blocks(thread)
        else:
            # No assistant: use default memory blocks
            memory_blocks = self._get_default_memory_blocks(thread)

        # Use the actual selected model (should already include provider prefix)
        model_name = thread.model_id.name

        # Get or create API key for MCP authentication
        api_key = self._ensure_api_key_for_agent(thread)
        
        embedding = thread.provider_id.letta_get_embedding_model()
        if not embedding:
            raise UserError(
                f"No embedding models found for Letta provider '{thread.provider_id.name}'. "
                "Please run 'Fetch Models' first to import available embedding models."
            )

        # Build full configuration
        agent_config = {
            "name": f"thread_{thread.id}",
            "model": model_name,
            "embedding": embedding,
            "memory_blocks": memory_blocks,
            "tools": thread.provider_id.letta_format_tools([]),  # Basic tools for now
        }

        # Add system instruction if available
        if system_instruction:
            agent_config["system"] = system_instruction

        agent_config["tool_exec_environment_variables"] = {
            "ODOO_API_KEY": api_key,
        }

        return agent_config

    def _ensure_api_key_for_agent(self, thread):
        """Get or create API key for Letta agent MCP authentication"""
        # Check if we already have an API key
        existing_key = self._get_stored_api_key(thread)
        if existing_key:
            return existing_key

        # Generate new API key with scope 'rpc'
        max_duration = max(
            (
                group.api_key_duration
                for group in thread.user_id.groups_id
                if group.api_key_duration
            ),
            default=DEFAULT_API_KEY_DURATION,
        )

        expiration_date = datetime.now() + timedelta(days=max_duration)
        api_key_name = self._get_api_key_name(thread.id)

        # Generate API key programmatically
        api_key = (
            self.env["res.users.apikeys"]
            .sudo()
            .with_user(thread.user_id)
            ._generate(scope="rpc", name=api_key_name, expiration_date=expiration_date)
        )

        # Find the created API key record to get its ID
        api_key_record = (
            self.env["res.users.apikeys"]
            .sudo()
            .search(
                [
                    ("user_id", "=", thread.user_id.id),
                    ("name", "=", api_key_name),
                ],
                limit=1,
                order="create_date desc",
            )
        )

        # Store API key info in metadata
        self._store_api_key(
            thread, api_key, api_key_record.id if api_key_record else None
        )

        return api_key

    def get_letta_agent_id(self):
        """Get the Letta agent ID for this thread.

        Returns:
            str: Agent ID if available, None otherwise
        """
        self.ensure_one()

        if self.provider_id.service == "letta":
            return self.external_id
        else:
            return None

    def ensure_letta_agent(self):
        """Ensure this thread has a valid Letta agent.

        Returns:
            str: Agent ID

        Raises:
            UserError: If agent cannot be created or verified
        """
        self.ensure_one()

        if self.provider_id.service != "letta":
            raise UserError("This thread is not configured for Letta provider")

        agent_id = self.external_id

        # Verify agent exists in Letta
        if agent_id:
            client = self.provider_id.letta_get_client()
            client.agents.retrieve(agent_id=agent_id)
            return agent_id

        # Create new agent if needed
        if not agent_id:
            agent_id = self._create_letta_agent(self)
            if agent_id:
                self.external_id = agent_id
            else:
                raise UserError("Failed to create Letta agent for this thread")

        return agent_id

    def sync_letta_tools(self):
        """Manual tool synchronization for Letta agent"""
        self.ensure_one()

        if self.provider_id.service != "letta":
            raise UserError("This action is only available for Letta threads")

        if not self.external_id:
            raise UserError("No Letta agent found for this thread")

        self.provider_id.letta_sync_agent_tools(self.external_id, self.tool_ids)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "message": f"Tools synchronized successfully for agent {self.external_id}",
                "type": "success",
            },
        }

    def _process_llm_body(self, body):
          """Override to handle Letta's specific escape sequence formatting."""
          if not body:
              return body

          # Only apply Letta-specific cleaning if using Letta provider
          # This preserves emojis and other unicode characters
          if self.provider_id and self.provider_id.service == "letta":
              # Handle Letta's split escape sequences
              body = body.replace('\\n', '\n').replace('\\t', '\t').replace('\\r', '\r')

          # Call parent's implementation for standard markdown processing
          return super()._process_llm_body(body)

    def letta_get_agent_config_context(self, base_context=None):
        """Hook method to build context for Letta agent configuration templates.

        Override this method to add custom context for Letta agent templates.

        Args:
            base_context (dict): Additional context from caller

        Returns:
            dict: Context for Letta agent configuration template rendering
        """
        context = base_context or {}

        # Add standard user context
        if self.user_id:
            context["user"] = self.user_id.read(['id', 'name', 'email'])[0]

        # Add standard thread context
        context.update({
            "thread_id": self.id,
            "thread_name": self.name,
        })
        return context

    def _is_letta_compatible_prompt(self, prompt, context=None):
        """Check if a prompt is Letta-compatible (has memory_blocks structure)

        Args:
            prompt (llm.prompt): Prompt record to check
            context (dict): Real context to use for checking (optional)

        Returns:
            bool: True if prompt contains memory_blocks structure
        """
        if not prompt or prompt.format not in ('json', 'yaml'):
            return False

        try:
            # Use provided context or fallback to sample context
            if context:
                check_context = context
            else:
                # Fallback sample context if no real context provided
                check_context = {
                    "user": {"id": 1, "name": "Sample User", "email": "sample@example.com"},
                    "thread_id": 1,
                    "thread_name": "Sample Thread",
                }

            messages = prompt.get_messages(check_context)

            for message in messages:
                content = message.get('content', '')
                if isinstance(content, list) and content:
                    content = content[0].get('text', '')

                if not content.strip():
                    continue

                if prompt.format == 'json':
                    data = json.loads(content)
                elif prompt.format == 'yaml':
                    data = yaml.safe_load(content)

                if isinstance(data, dict) and 'memory_blocks' in data:
                    return True
        except Exception as e:
            _logger.error(f"Error parsing prompt '{prompt.name}': {e}")
            # If parsing fails, assume not Letta-compatible
            return False

        return False

    def _extract_memory_blocks_from_messages(self, messages, prompt=None):
        """Extract memory blocks from prompt messages

        Args:
            messages (list): List of messages from prompt template
            prompt (llm.prompt): Prompt record for format information

        Returns:
            list or None: List of memory blocks if found, None otherwise
        """
        for message in messages:
            content = message.get('content', '')
            if isinstance(content, list) and content:
                content = content[0].get('text', '')

            if not content.strip():
                continue

            # Only JSON and YAML formats are supported for memory blocks
            if prompt.format not in ('json', 'yaml'):
                raise UserError(
                    f"Prompt '{prompt.name}' uses format '{prompt.format}' but Letta memory blocks "
                    "only support 'json' and 'yaml' formats. Please change the prompt format."
                )

            if prompt.format == 'json':
                data = json.loads(content)
            elif prompt.format == 'yaml':
                data = yaml.safe_load(content)

            if isinstance(data, dict) and 'memory_blocks' in data:
                return data['memory_blocks']

        return None

    def _build_memory_blocks_from_defaults(self, evaluated_values, thread):
        """Build memory blocks from assistant default_values

        Args:
            evaluated_values (dict): Evaluated default values from assistant
            thread: Thread record for fallback values

        Returns:
            list: List of memory blocks
        """
        user_name = thread.user_id.name or "User"
        return [
            {
                "label": "persona",
                "value": evaluated_values.get("persona", DEFAULT_PERSONA_BLOCK)
            },
            {
                "label": "human",
                "value": evaluated_values.get("human", DEFAULT_HUMAN_BLOCK_TEMPLATE.format(user_name=user_name))
            },
        ]

    def _get_default_memory_blocks(self, thread):
        """Fallback to hardcoded defaults

        Args:
            thread: Thread record

        Returns:
            list: List of default memory blocks
        """
        user_name = thread.user_id.name or "User"
        return [
            {"label": "persona", "value": DEFAULT_PERSONA_BLOCK},
            {"label": "human", "value": DEFAULT_HUMAN_BLOCK_TEMPLATE.format(user_name=user_name)},
        ]
