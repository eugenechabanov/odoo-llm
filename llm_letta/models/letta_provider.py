import logging

from letta_client import Letta
from letta_client.types import MessageCreate

from odoo import api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LLMProvider(models.Model):
    _inherit = "llm.provider"

    @api.model
    def _get_available_services(self):
        services = super()._get_available_services()
        return services + [("letta", "Letta")]

    def letta_get_client(self):
        """Get Letta client instance"""
        _logger.info(f"Creating Letta client for provider {self.name}")

        if not self.api_base:
            _logger.error("API base URL is required for Letta connection")
            raise UserError("API base URL is required for Letta connection")

        # Simple unified initialization for both local and cloud
        return Letta(
            base_url=self.api_base,
            token=self.api_key  # Will be None for local, which is fine
        )

    def letta_models(self, model_id=None):
        """List available models from Letta"""
        client = self.letta_get_client()
        models_response = client.models.list()

        # Convert Letta model format to our standard format
        models = []
        for model in models_response:
            # Use handle as the name since that's what Letta agent config expects
            model_handle = getattr(model, "handle", None)
            if not model_handle:
                # Fallback: construct handle if not provided
                provider = getattr(model, "model_endpoint_type", "unknown")
                model_handle = f"{provider}/{model.model}"

            model_data = {
                "name": model_handle,  # Use handle as name for Letta compatibility
                "provider": model.provider_name
                if hasattr(model, "provider_name")
                else "letta",
                "context_window": getattr(model, "context_window", None),
                "model_endpoint_type": getattr(model, "model_endpoint_type", None),
                "temperature": getattr(model, "temperature", None),
                "max_tokens": getattr(model, "max_tokens", None),
                "raw_model_name": model.model,  # Keep raw name for reference
            }

            # Filter by specific model if requested
            if model_id and model_data["name"] != model_id:
                continue

            models.append(model_data)

        return models

    def letta_chat(self, messages, model=None, stream=False, **kwargs):  # pylint: disable=unused-argument
        """Chat completion using Letta agents.

        Args:
            messages: List of messages (only latest user message is used)
            model: Model to use (ignored - agent already has model)
            stream: Whether to stream response
            **kwargs: Additional parameters, including thread context

        Returns:
            Generator of response chunks if streaming, else complete response
        """
        client = self.letta_get_client()

        # Get thread from context
        thread_context = kwargs.get("thread_context", {})
        thread_id = thread_context.get("id")

        if not thread_id:
            raise UserError("Thread ID is required for Letta chat")

        # Get thread record and ensure it has a Letta agent
        thread_record = self.env["llm.thread"].browse(thread_id)
        if not thread_record.exists():
            raise UserError(f"Thread {thread_id} not found")

        agent_id = thread_record.ensure_letta_agent()

        # Extract latest user message - Letta agents maintain their own history
        latest_message = messages[-1] if messages else None
        if not latest_message:
            raise UserError("No messages provided")

        # Use the standard dispatch to format the message
        _logger.info("Formatting latest message: ID=%s, llm_role=%s",
                    getattr(latest_message, 'id', 'N/A'),
                    getattr(latest_message, 'llm_role', 'N/A'))
        formatted_message = self._dispatch("format_message", record=latest_message)
        _logger.info("Formatted message result: %s", formatted_message)
        if not formatted_message or not formatted_message.get("content"):
            raise UserError("Could not format message content")

        user_content = formatted_message["content"]

        try:
            if stream:
                return self._letta_stream_agent_response(client, agent_id, user_content, thread_record)
            else:
                return self._letta_get_agent_response(client, agent_id, user_content)

        except Exception as e:
            _logger.error(f"Letta chat failed for agent {agent_id}: {str(e)}")
            raise UserError(f"Chat failed: {str(e)}") from e

    def letta_embedding(self, texts, model=None):  # pylint: disable=unused-argument
        """Text embedding - not implemented yet"""
        raise NotImplementedError(
            "Letta embedding functionality is not yet implemented. "
            "This provider currently only supports model fetching and chat."
        )

    def letta_generate(self, input_data, model=None, stream=False, **kwargs):  # pylint: disable=unused-argument
        """Content generation - not implemented yet"""
        raise NotImplementedError(
            "Letta generation functionality is not yet implemented. "
            "This provider currently only supports model fetching and chat."
        )

    def letta_format_tools(self, tools):  # pylint: disable=unused-argument
        """Format tools for Letta (not used - tools are managed via MCP/API)."""
        return []

    def letta_ensure_mcp_server(self):
        """Ensure Odoo MCP server is registered with Letta."""
        _logger.info("Ensuring Odoo MCP server is registered with Letta")
        client = self.letta_get_client()

        # Get MCP server config
        mcp_config_model = self.env["llm.mcp.server.config"]
        mcp_config = mcp_config_model.get_active_config()
        server_name = mcp_config.name

        try:
            # Check if server already exists
            _logger.debug("Checking existing MCP servers")
            servers = client.tools.list_mcp_servers()
            _logger.debug(f"Found {len(servers)} existing MCP servers")

            # Check if our server is already registered
            server_exists = False
            for server in servers:
                if isinstance(server, str):
                    if server == server_name:
                        server_exists = True
                        break
                else:
                    # Server object has server_name attribute
                    if (
                        hasattr(server, "server_name")
                        and server.server_name == server_name
                    ):
                        server_exists = True
                        break

            if server_exists:
                _logger.info(f"MCP server '{server_name}' already registered")
                return True

            # Get MCP server URL from configuration
            server_url = mcp_config.get_mcp_server_url()
            _logger.info(f"Registering MCP server at {server_url}")

            # Create the proper MCP server config using Letta client types
            from letta_client.types import StreamableHttpServerConfig

            mcp_config = StreamableHttpServerConfig(
                server_name=server_name, 
                server_url=server_url, 
                type="streamable_http",
                custom_headers={
                    # Letta will replace this template with API key from environment variables
                    "Authorization": "Bearer {{ ODOO_API_KEY }}",
                },
            )

            # Register the MCP server using the correct API
            response = client.tools.add_mcp_server(request=mcp_config)
            _logger.info(f"Successfully registered Odoo MCP server: {response}")
            return True

        except Exception as e:
            _logger.error(f"Failed to register MCP server: {e}")
            raise UserError(f"Failed to register MCP server: {str(e)}") from e

    def letta_attach_tool(self, agent_id, tool_name):
        """Attach a specific tool to a Letta agent."""
        _logger.info(f"Attaching tool '{tool_name}' to Letta agent {agent_id}")
        client = self.letta_get_client()

        try:
            # First ensure MCP server is registered
            _logger.debug("Ensuring MCP server is registered before tool attachment")
            self.letta_ensure_mcp_server()

            # Get MCP server config for server name
            mcp_config_model = self.env["llm.mcp.server.config"]
            mcp_config = mcp_config_model.get_active_config()
            server_name = mcp_config.name

            # Get available MCP tools to verify tool exists
            _logger.debug(f"Fetching available MCP tools from {server_name} server")
            mcp_tools = client.tools.list_mcp_tools_by_server(
                mcp_server_name=server_name
            )
            _logger.debug(f"Found {len(mcp_tools)} tools in MCP server")

            # Check if tool exists in MCP server
            tool_exists = False
            for tool in mcp_tools:
                if tool.name == tool_name:
                    tool_exists = True
                    break

            if not tool_exists:
                _logger.error(f"Tool '{tool_name}' not found in Odoo MCP server")
                raise UserError(f"Tool '{tool_name}' not found in Odoo MCP server")

            # Register the tool with Letta from the MCP server using correct API
            _logger.debug(f"Registering tool '{tool_name}' with Letta from MCP server")
            tool_response = client.tools.add_mcp_tool(
                mcp_server_name=server_name, mcp_tool_name=tool_name
            )
            _logger.info(
                f"Successfully registered tool '{tool_name}' with Letta: {tool_response}"
            )

            # Get the registered tool ID
            registered_tools = client.tools.list()
            tool_id = None
            for tool in registered_tools:
                if tool.name == tool_name:
                    tool_id = tool.id
                    break

            if not tool_id:
                _logger.error(f"Could not find registered tool '{tool_name}' ID")
                raise UserError(f"Could not find registered tool '{tool_name}' ID")

            # Attach tool to agent
            _logger.debug(f"Attaching tool {tool_id} to agent {agent_id}")
            attach_response = client.agents.tools.attach(agent_id, tool_id)
            _logger.info(
                f"Successfully attached tool '{tool_name}' (ID: {tool_id}) to agent {agent_id}"
            )
            return attach_response

        except Exception as e:
            _logger.error(
                f"Failed to attach tool '{tool_name}' to agent {agent_id}: {e}"
            )
            raise UserError(f"Failed to attach tool '{tool_name}': {str(e)}") from e

    def letta_detach_tool(self, agent_id, tool_name):
        """Detach a tool from a Letta agent."""
        client = self.letta_get_client()

        try:
            # Get agent's current tools
            agent_tools = client.agents.tools.list(agent_id)

            # Find the tool to detach - agent_tools is List[Tool]
            tool_to_detach = None
            for tool in agent_tools:
                if tool.name == tool_name:
                    tool_to_detach = tool
                    break

            if not tool_to_detach:
                _logger.warning(f"Tool '{tool_name}' not found on agent {agent_id}")
                return False

            # Get tool ID from the Tool object
            if not tool_to_detach.id:
                raise UserError(f"Could not get tool ID for '{tool_name}'")

            # Detach tool from agent
            detach_response = client.agents.tools.detach(agent_id, tool_to_detach.id)
            _logger.info(f"Detached tool '{tool_name}' from agent {agent_id}")
            return detach_response

        except Exception as e:
            _logger.error(
                f"Failed to detach tool '{tool_name}' from agent {agent_id}: {e}"
            )
            raise UserError(f"Failed to detach tool '{tool_name}': {str(e)}") from e

    def letta_sync_agent_tools(self, agent_id, tool_records):
        """Synchronize agent tools with thread tool_ids."""
        _logger.info(
            f"Synchronizing tools for Letta agent {agent_id} with {len(tool_records) if tool_records else 0} tool records"
        )

        if not tool_records:
            # Remove all tools from agent if no tools specified
            _logger.info(
                f"No tools specified, removing all Odoo tools from agent {agent_id}"
            )
            client = self.letta_get_client()
            try:
                agent_tools = client.agents.tools.list(agent_id)
                mcp_tools = []
                for tool in agent_tools:
                    if tool.tool_type == "external_mcp":
                        mcp_tools.append(tool)

                _logger.debug(
                    f"Found {len(mcp_tools)} MCP tools to remove from agent {agent_id}"
                )

                for tool in mcp_tools:
                    self.letta_detach_tool(agent_id, tool.name)
                return True
            except Exception as e:
                _logger.error(f"Failed to remove tools from agent {agent_id}: {e}")
                return False

        # Get all tools from the thread (regardless of implementation type)
        thread_tools = tool_records.filtered(lambda t: t.active)
        _logger.debug(f"Found {len(thread_tools)} active tools to sync for thread")

        if not thread_tools:
            _logger.info(f"No active tools found, agent {agent_id} sync complete")
            return True

        try:
            # Get current agent tools
            client = self.letta_get_client()
            _logger.debug(f"Fetching current tools for agent {agent_id}")
            agent_tools = client.agents.tools.list(agent_id)

            # Extract current MCP tool names from Tool objects
            current_tool_names = set()
            for tool in agent_tools:
                if tool.tool_type == "external_mcp":
                    current_tool_names.add(tool.name)

            _logger.debug(f"Agent {agent_id} currently has tools: {current_tool_names}")

            # Get desired tool names from the thread's tool_ids
            desired_tool_names = set(thread_tools.mapped("name"))
            _logger.debug(f"Desired tools for agent {agent_id}: {desired_tool_names}")

            # Attach new tools
            tools_to_attach = desired_tool_names - current_tool_names
            _logger.info(f"Tools to attach to agent {agent_id}: {tools_to_attach}")
            for tool_name in tools_to_attach:
                self.letta_attach_tool(agent_id, tool_name)

            # Detach removed tools
            tools_to_detach = current_tool_names - desired_tool_names
            _logger.info(f"Tools to detach from agent {agent_id}: {tools_to_detach}")
            for tool_name in tools_to_detach:
                self.letta_detach_tool(agent_id, tool_name)

            _logger.info(
                f"Successfully synced tools for agent {agent_id}: +{len(tools_to_attach)}, -{len(tools_to_detach)}"
            )
            return True

        except Exception as e:
            _logger.error(f"Failed to sync tools for agent {agent_id}: {e}")
            raise UserError(f"Failed to sync agent tools: {str(e)}") from e

    def letta_format_messages(self, messages, system_prompt=None):  # pylint: disable=unused-argument
        """Format messages for Letta (simplified - agent maintains history).

        Note: Letta agents maintain their own conversation history,
        so we only need to return the latest user message.
        """
        if not messages:
            return []

        # Return only the latest message - Letta handles conversation state
        latest_message = messages[-1]
        formatted_message = self._dispatch("format_message", record=latest_message)
        return [formatted_message] if formatted_message else []

    def _letta_stream_agent_response(self, client, agent_id, user_content, thread_record=None):
        """Stream response from Letta agent."""

        stream = client.agents.messages.create_stream(
            agent_id=agent_id,
            messages=[MessageCreate(role="user", content=user_content)],
            stream_tokens=True,
        )

        # Track different phases of the response
        pre_tool_content = ""  # Content before tool calls
        post_tool_content = ""  # Content after tool calls
        tool_calls = {}  # tool_call_id -> {name, arguments}
        tool_results = {}  # tool_call_id -> result
        tool_calls_detected = False
        tools_completed = False

        for chunk in stream:
            # Check if chunk has message_type attribute (Letta's streaming format)
            if hasattr(chunk, "message_type"):
                message_type = getattr(chunk, "message_type", None)

                # Handle assistant message chunks
                if message_type == "assistant_message" and hasattr(chunk, "content"):
                    if chunk.content:
                        if not tool_calls_detected:
                            # Before tool calls - yield immediately and store
                            pre_tool_content += chunk.content
                            yield {"content": chunk.content}
                        elif tools_completed:
                            # After tool completion - this is final assistant response
                            post_tool_content += chunk.content
                            _logger.info("Post-tool content: %s", chunk.content)
                            # Don't yield yet - we'll yield this as final response
                        else:
                            # During tool processing - just store for now
                            _logger.info("Tool processing content (not yielding): %s", chunk.content)

                # Handle reasoning messages (debug level)
                elif message_type == "reasoning_message" and hasattr(
                    chunk, "reasoning"
                ):
                    _logger.info("Agent reasoning: %s", chunk.reasoning)

                # Handle tool call messages
                elif message_type == "tool_call_message" and hasattr(chunk, "tool_call"):
                    # Handle tool call assembly - first chunk has metadata, subsequent chunks have arguments
                    tool_call_id = chunk.tool_call.tool_call_id
                    tool_name = chunk.tool_call.name
                    tool_arguments = chunk.tool_call.arguments

                    # Debug log the chunk details
                    _logger.info("Tool call chunk: ID=%s, name=%s, args=%s",
                               tool_call_id, tool_name, tool_arguments)

                    # Debug: Log the exact raw chunk data
                    _logger.info("Raw chunk attributes: %s", {
                        'tool_call_id': tool_call_id,
                        'tool_name': tool_name,
                        'tool_arguments': tool_arguments,
                        'tool_arguments_type': type(tool_arguments).__name__,
                        'tool_arguments_repr': repr(tool_arguments) if tool_arguments else None
                    })

                    # First chunk: has tool_call_id and name, but arguments might be None
                    if tool_call_id and tool_name:
                        if tool_call_id not in tool_calls:
                            tool_calls[tool_call_id] = {
                                "name": tool_name,
                                "arguments": "",
                                "arguments_chunks": []  # Track individual chunks for better assembly
                            }
                            _logger.info("Created new tool call entry for %s", tool_call_id)
                        # Add arguments if present (could be None in first chunk)
                        if tool_arguments:
                            tool_calls[tool_call_id]["arguments_chunks"].append(tool_arguments)
                            tool_calls[tool_call_id]["arguments"] = "".join(tool_calls[tool_call_id]["arguments_chunks"])
                            _logger.info("Added args chunk to %s: %s", tool_call_id, tool_arguments)
                            _logger.info("Current assembled args for %s: %s", tool_call_id, tool_calls[tool_call_id]["arguments"])
                            _logger.info("All chunks so far for %s: %s", tool_call_id, tool_calls[tool_call_id]["arguments_chunks"])

                    # Subsequent chunks: no tool_call_id/name, but have argument fragments
                    elif tool_arguments and not tool_call_id and not tool_name:
                        # Find the most recent tool call to append arguments to
                        if tool_calls:
                            latest_tool_id = list(tool_calls.keys())[-1]
                            tool_calls[latest_tool_id]["arguments_chunks"].append(tool_arguments)
                            tool_calls[latest_tool_id]["arguments"] = "".join(tool_calls[latest_tool_id]["arguments_chunks"])
                            _logger.info("Appended args chunk to latest tool %s: %s", latest_tool_id, tool_arguments)
                            _logger.info("Current assembled args for %s: %s", latest_tool_id, tool_calls[latest_tool_id]["arguments"])
                            _logger.info("All chunks so far for %s: %s", latest_tool_id, tool_calls[latest_tool_id]["arguments_chunks"])

                    # Mark that we've detected tool calls
                    if not tool_calls_detected and tool_calls:
                        tool_calls_detected = True
                        _logger.info("Tool calls detected - switching to tool processing mode")

                # Handle tool return messages
                elif message_type == "tool_return_message":
                    if hasattr(chunk, "tool_call_id") and hasattr(chunk, "tool_return"):
                        tool_call_id = chunk.tool_call_id
                        tool_results[tool_call_id] = chunk.tool_return
                        _logger.info("Stored tool result for call ID: %s", tool_call_id)

                        # Check if all tools are completed
                        if len(tool_results) == len(tool_calls) and not tools_completed:
                            tools_completed = True
                            _logger.info("All tools completed - switching to final response mode")

            # Handle usage statistics (debug level)
            elif (
                hasattr(chunk, "completion_tokens")
                or getattr(chunk, "message_type", None) == "usage_statistics"
            ):
                _logger.info("Letta usage: %s", chunk)

            # Log unknown chunk types for discovery
            else:
                message_type = getattr(chunk, "message_type", "NO_TYPE")
                if hasattr(chunk, "message_type"):
                    _logger.info("Unknown chunk type: %s", message_type)
                    _logger.info("Unknown chunk attributes: %s", dir(chunk))

        # Return empty content if nothing was streamed (shouldn't happen normally)
        total_content = pre_tool_content + post_tool_content
        if not total_content:
            _logger.warning("No response content received from Letta stream")

        # Prepare final response
        final_response = {"content": "", "finish_reason": "stop"}

        # Handle tool calls and results properly
        if tool_calls:
            # First, yield assistant message with tool calls
            formatted_tool_calls = []
            for tool_call_id, tool_data in tool_calls.items():
                # Debug: Log assembled arguments and validate JSON
                assembled_args = tool_data["arguments"]
                _logger.info("Tool call %s assembled arguments: %r", tool_call_id, assembled_args)
                _logger.info("Tool call %s - Character by character: %s", tool_call_id, [c for c in assembled_args])

                # Try to validate JSON structure
                try:
                    import json
                    json.loads(assembled_args)
                    _logger.info("Tool call %s: JSON is valid", tool_call_id)
                except json.JSONDecodeError as e:
                    _logger.warning("Tool call %s: Invalid JSON - %s", tool_call_id, e)

                formatted_tool_calls.append({
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": tool_data["name"],
                        "arguments": tool_data["arguments"]
                    }
                })

            # Yield tool calls chunk (this will be collected by _handle_streaming_response)
            yield {"tool_calls": formatted_tool_calls}
            _logger.info("Yielded tool calls chunk with %d tool calls", len(formatted_tool_calls))

            # For Letta, we need to create tool messages manually since tools were executed via MCP
            if thread_record:
                for tool_call_id, result in tool_results.items():
                    if tool_call_id in tool_calls:
                        tool_name = tool_calls[tool_call_id]["name"]
                        assembled_args = tool_calls[tool_call_id]["arguments"]

                        # Use the assembled arguments directly - they are correct JSON
                        import json
                        try:
                            parsed_args = json.loads(assembled_args)
                            _logger.info("Successfully parsed tool arguments for %s: %s", tool_call_id, parsed_args)
                        except json.JSONDecodeError as e:
                            _logger.warning("Failed to parse tool arguments for %s: %s", tool_call_id, e)
                            parsed_args = {}

                        tool_data = {
                            "type": "tool_execution",
                            "tool_call_id": tool_call_id,
                            "tool_call": {
                                "id": tool_call_id,
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": assembled_args  # Use the correctly assembled arguments
                                }
                            },
                            "status": "completed",
                            "result": result,
                            "tool_name": tool_name,
                            "arguments": parsed_args,  # Use parsed dict for top-level arguments
                        }
                        tool_message = thread_record.message_post(
                            body=f"Tool executed: {tool_name}",
                            body_json=tool_data,
                            llm_role="tool",
                            author_id=False,
                        )
                        _logger.info("Created tool message for %s with arguments: %s", tool_call_id, assembled_args)

                        # Yield message event for real-time UI update with proper mail store format
                        yield {
                            "type": "message_create",
                            "message": {
                                "id": tool_message.id,
                                "llm_role": "tool",
                                "body": tool_message.body,
                                "body_json": tool_data,
                                "res_id": thread_record.id,
                                "model": "llm.thread",
                            }
                        }

            # Yield final assistant response with post-tool content if any
            if post_tool_content:
                _logger.info("Yielding final response with post-tool content: %s", post_tool_content)
                yield {"content": post_tool_content, "finish_reason": "stop"}
            else:
                _logger.info("No post-tool content, yielding empty final response")
                yield {"content": "", "finish_reason": "stop"}
        else:
            # No tool calls, just regular assistant response
            yield final_response

    def _letta_get_agent_response(self, client, agent_id, user_content):
        """Get non-streaming response from Letta agent."""

        # For non-streaming, we'll collect the full response
        response_content = ""
        completion_tokens = 0

        stream = client.agents.messages.create_stream(
            agent_id=agent_id,
            messages=[MessageCreate(role="user", content=user_content)],
            stream_tokens=False,  # Even non-streaming uses the stream API
        )

        for chunk in stream:
            # Check if chunk has message_type attribute (Letta's streaming format)
            if hasattr(chunk, "message_type"):
                message_type = getattr(chunk, "message_type", None)

                # Handle assistant message chunks
                if message_type == "assistant_message" and hasattr(chunk, "content"):
                    if chunk.content:
                        response_content += chunk.content
            elif hasattr(chunk, "completion_tokens"):
                completion_tokens = getattr(chunk, "completion_tokens", 0)

        # Log if no content was received (shouldn't happen with use_assistant_message=True)
        if not response_content and completion_tokens > 0:
            _logger.error(
                "No assistant content received despite tokens being used - check agent configuration"
            )

        return {
            "content": response_content or "I couldn't generate a response.",
            "finish_reason": "stop",
        }
