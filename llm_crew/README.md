# Odoo LLM Crew Module

This module integrates CrewAI capabilities into Odoo, enabling AI-powered teams to collaborate on tasks within your Odoo environment.

## Features

- AI Agent Management
- AI Crew Teams
- Integration with Project Management
- Hierarchical Task Processing

## Setup Guide

### 1. Prerequisites
- Installed and configured `llm` module
- Valid LLM provider configuration (e.g., OpenAI API key)

### 2. Configuration Steps

#### 2.1 Create AI Agents
1. Go to `CRM > Configuration > AI Agents`
2. Create a new AI agent:
   - Select User
   - Set Role (e.g., "Research Specialist")
   - Set Goal (e.g., "Conduct thorough market research")
   - Add Backstory (optional)
   - Select LLM Provider and Model
   - Enable/disable delegation

#### 2.2 Setup AI Crew
1. Go to `CRM > Configuration > Sales Teams`
2. Create or select a team
3. Enable "Is AI Crew"
4. Configure crew settings:
   - Select Project
   - Assign Team Leader (will act as crew manager)
   - Add team members (must have AI agents configured)

### 3. Usage

#### Creating Tasks
1. Go to the project associated with your AI crew
2. Create tasks with:
   - Clear descriptions
   - Expected outputs
   - Assigned AI agents

#### Executing Crew Tasks
- Tasks are automatically processed when messages are posted in the chatter
- The crew manager (team leader) oversees task execution
- Results are posted back in the chatter

## Technical Details

### Models

#### llm.crew.agent
- Extends users with AI capabilities
- Manages agent configuration (role, goal, backstory)
- Integrates with LLM providers

#### crm.team (Extended)
- Adds AI crew capabilities to sales teams
- Manages crew configuration and execution
- Integrates with project management

### Process Flow
1. Message posted in chatter triggers crew execution
2. Team leader's AI agent manages task distribution
3. AI agents process tasks based on their roles
4. Results are formatted and posted back to chatter

### Integration Points
- Uses `llm` module for LLM provider management
- Integrates with Odoo's project management
- Extends mail thread for communication