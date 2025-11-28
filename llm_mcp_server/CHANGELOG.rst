Changelog
=========

16.0.1.1.0 (2025-11-29)
-----------------------

* [ADD] Added "Client Configuration" tab to MCP Server Config form with copy-paste setup instructions
* [ADD] Included configuration snippets for Claude Desktop, Claude Code, and Codex CLI
* [ADD] Added prerequisites section with mcp-remote installation command
* [IMP] Better onboarding experience with inline API key guidance

16.0.1.0.0 (2025-01-29)
-----------------------

**Initial Release - Odoo 16.0 Backport**

* Model Context Protocol (MCP) 2025-06-18 server implementation
* Bearer token authentication backported from Odoo 18.0
* Claude Desktop, Letta, and MCP client integration support
* Stateful/stateless session management
* Core MCP methods: initialize, tools/list, tools/call, ping
* Health monitoring endpoint at /mcp/health
