# Odoo LLM Chat Module

This module enables AI-powered chat capabilities in Odoo's chatter, allowing seamless interaction with AI agents through the standard Odoo interface.

## Features

- AI-powered responses in chatter
- Markdown support for formatted responses
- Integration with AI crews
- Smart message processing

## Setup Guide

### 1. Prerequisites

- Installed and configured `llm` module
- Configured `llm_crew` module (for crew interactions)

### 2. Configuration

#### 2.1 Enable AI Chat

1. Install the module
2. Configure LLM providers in Settings
3. Set up AI agents and crews (if using crew features)

### 3. Usage

#### Direct Chat

1. Open any record with chatter
2. Post a message mentioning an AI agent or crew
3. Receive formatted responses in the chatter

#### Crew Interactions

1. Post a message in a project task's chatter
2. If the task belongs to an AI crew, the crew will process it
3. Receive formatted responses from the crew

## Technical Details

### Key Components

#### mail.thread Extension

- Enhances standard chatter functionality
- Processes messages for AI interaction
- Handles markdown formatting
- Manages crew execution requests

### Message Flow

1. Message posted in chatter
2. System checks for AI triggers
3. If applicable, routes to appropriate AI agent or crew
4. Processes response through markdown formatter
5. Posts formatted response back to chatter

### Features

- Markdown to HTML conversion
- Code block formatting
- Table support
- Smart quote handling
- Syntax highlighting for code

### Integration Points

- Extends Odoo's mail system
- Integrates with `llm_crew` for team interactions
- Uses markdown2 for formatting
