# LLM Agent Module

Create and manage AI agents powered by LLM models in Odoo.

## Overview

The LLM Agent module enables you to create AI agents that can interact with users through Odoo's chat interface. Each agent can be configured with a specific LLM model and system prompt to define its role and behavior.

## Features

- Create and manage LLM agents as Odoo users
- Configure agents with specific LLM models
- Define custom system prompts for each agent
- Chat with agents in Odoo's interface
- Real-time message streaming
- Automatic avatar management from model publishers

## Installation

### Prerequisites

- Odoo 16.0 or later
- LLM module installed and configured

### Dependencies

- `base`
- `mail`
- `llm`

## Configuration

1. Install the module
2. Go to Settings > LLM Agents
3. Create a new agent and configure:
   - Name and login
   - LLM model
   - System prompt
4. Start chatting with your agent in any Odoo chat by mentioning them in message or opening a private chat

## Technical Details

### Models

- `res.users` (inherited)
  - Added fields:
    - `model_id`: Many2one relation to `llm.model`
    - `system_prompt`: Text field for agent instructions
    - `is_active`: Boolean for agent status
    - `is_agent`: Computed Boolean field

### Security

- New security group: `LLM Agent / Agent`
- Access rights for managing agents
- Automatic group assignment on agent creation

### Views

- Form view for agent configuration
- Tree view for agent list
- Menu item under Settings

## License

LGPL-3

## Support

For questions or support needs, please contact:
[Apexive](https://apexive.com)
