# LLM MCP Server for Odoo

Expose your Odoo tools to Claude Desktop, Letta agents, and any MCP-compatible AI client.

## Quick Start

**3 minutes to connect Claude Desktop:**

**1. Install mcp-remote:**
```bash
npm install -g mcp-remote
```

**2. Get API key from Odoo:**
- User avatar (top right) → Preferences → Account Security → API Keys → New

**3. Add to Claude Desktop config:**

Location: `~/.config/claude_desktop/claude_desktop_config.json` (Linux/macOS) or `%APPDATA%/Claude/claude_desktop_config.json` (Windows)

```json
{
  "mcpServers": {
    "odoo-llm-mcp-server": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:8069/mcp",
               "--header", "Authorization: Bearer YOUR_API_KEY"],
      "env": {"MCP_TRANSPORT": "streamable-http"}
    }
  }
}
```

**For Claude Code users:**
```bash
claude mcp add-json odoo-llm-mcp-server '{
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "mcp-remote", "http://localhost:8069/mcp",
           "--header", "Authorization: Bearer YOUR_API_KEY"],
  "env": {"MCP_TRANSPORT": "streamable-http"}
}'
```

**For Codex CLI users:**

Add to `~/.codex/config.toml`:
```toml
experimental_use_rmcp_client = true

[mcp_servers.odoo-llm-mcp-server]
url = "http://localhost:8069/mcp"
http_headers.Authorization = "Bearer YOUR_API_KEY"
```

**4. Restart Claude Desktop / Codex** → Ask "What tools do you have?"

**That's it!** All your active Odoo tools are now available to Claude.

**✅ Works with:** Claude Desktop • Letta Agents • Any MCP client

**📺 Video Tutorial**: [Watch setup guide](https://drive.google.com/file/d/1TgPrfLuAtql3en3B_McKlMmDWuYn3wXM/view?usp=drive_link) - Complete walkthrough of MCP server setup and Claude Desktop connection

## Architecture

- **Native Odoo**: Pure Odoo implementation using standard HTTP controllers
- **MCP Compliant**: Full MCP 2025-06-18 protocol with JSON-RPC 2.0
- **Auto Discovery**: Exposes all active `llm.tool` records
- **Secure**: Bearer token authentication with Odoo ACL enforcement

## Docker/Remote Setup

If your MCP client runs in Docker or remotely (e.g., Letta server in Docker):

```bash
# Configure external URL in Odoo
# LLM → Configuration → MCP Server → External URL
# Set to: http://host.docker.internal:8069  (Docker accessing host Odoo)
# Or: http://your-server-ip:8069  (remote access)
```

This allows containers/remote clients to access your Odoo MCP server.

## Other MCP Clients

**Letta Agents**: Use `llm_letta` module for automatic integration

**Custom clients**: Connect to `http://your-server:8069/mcp` with Bearer auth

## Security

Tools execute with API key user's permissions - all Odoo ACL rules enforced.
