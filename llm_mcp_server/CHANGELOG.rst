16.0.1.2.0 (2025-12-02)
~~~~~~~~~~~~~~~~~~~~~~~

* [ADD] New MCP Key wizard - generates API key with ready-to-copy client configurations
* [ADD] "New MCP Key" button in user preferences (Account Security section)
* [ADD] "New MCP Key" button in MCP Server Config form for quick key generation
* [ADD] Client Configuration tab with nested notebook tabs for each MCP client
* [IMP] Client configs now use Jinja2 templates for maintainable config generation
* [IMP] CopyClipboardButton widgets for easy config copying
* [IMP] DRY refactoring - shared config generation between wizard and config form

16.0.1.1.0 (2025-11-03)
~~~~~~~~~~~~~~~~~~~~~~~

* [IMP] Updated Odoo App Store description page (static/description/index.html)
* [IMP] Improved module presentation with modern Bootstrap 5 layout
* [IMP] Enhanced mobile responsiveness and visual design
* [IMP] Added comprehensive MCP feature descriptions and use cases
* [IMP] Optimized for Odoo App Store HTML sanitization requirements

16.0.1.0.0 (2025-10-23)
~~~~~~~~~~~~~~~~~~~~~~~

* [INIT] Initial release of the module
* [ADD] MCP 2025-06-18 protocol implementation
* [ADD] Bearer token authentication with Odoo API keys
* [ADD] Dynamic tool discovery from llm.tool registry
* [ADD] Real-time tool execution with proper Odoo context
* [ADD] Health monitoring and session management
* [ADD] Support for Claude Desktop, Claude Code, Cursor, Windsurf, VS Code, and Codex
