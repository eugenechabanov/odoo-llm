"""
MCP Protocol Types - Custom implementation for Python 3.9+ compatibility.

This module provides type definitions that mirror the official mcp.types module,
allowing the llm_mcp_server to work without the mcp package dependency
(which requires Python 3.10+).

All types are compliant with the MCP specification.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# JSON-RPC 2.0 Error Codes (standard spec)
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


# Content Types
class TextContent(BaseModel):
    """Text content in tool results."""

    type: str = "text"
    text: str


# Tool Types
class ToolAnnotations(BaseModel):
    """Optional annotations for tool behavior hints."""

    title: Optional[str] = None
    readOnlyHint: Optional[bool] = None
    destructiveHint: Optional[bool] = None
    idempotentHint: Optional[bool] = None
    openWorldHint: Optional[bool] = None


class Tool(BaseModel):
    """MCP Tool definition."""

    name: str
    description: Optional[str] = None
    inputSchema: Dict[str, Any] = Field(default_factory=dict)
    annotations: Optional[ToolAnnotations] = None


class ListToolsResult(BaseModel):
    """Result of tools/list method."""

    tools: List[Tool]


class CallToolResult(BaseModel):
    """Result of tools/call method."""

    content: List[TextContent]
    isError: bool = False


# Server Types
class Implementation(BaseModel):
    """Server or client implementation info."""

    name: str
    version: str


class ToolsCapability(BaseModel):
    """Tools capability declaration."""

    listChanged: bool = False


class ServerCapabilities(BaseModel):
    """Server capabilities container."""

    tools: Optional[ToolsCapability] = None


class InitializeResult(BaseModel):
    """Result of initialize method."""

    protocolVersion: str
    capabilities: ServerCapabilities
    serverInfo: Implementation
