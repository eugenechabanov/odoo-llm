# Odoo LLM Agent Module (Prototype)

This module integrates AI capabilities into Odoo, focusing on MIS report generation and task management. Currently in prototype phase.

## 🎯 Key Features

- **AI Agent Integration**: Configure and use AI agents for various tasks
- **MIS Report Generation**: AI-powered financial report template creation
- **Task Automation**: AI-assisted task processing
- **LLM Provider Integration**: Support for various LLM providers

## 🔧 Prerequisites

### System Requirements
- Odoo 16.0
- Python >= 3.10.0
- Valid LLM provider API key (e.g., OpenAI)

### Required Python Packages
- crewai: For AI agent and task management

### Required Odoo Modules
- base: Base Odoo functionalities
- project: Project and task management
- llm: Base LLM module for provider integration
- base_accounting_kit: Required for financial report generation
- mis_builder: MIS report template creation and management
- mis_builder_demo: Demo data and examples for MIS reports

## ⚙️ Configuration Steps

### 1. LLM Provider Setup

1. Navigate to `LLM > Configuration > LLM Providers`
2. Create a new LLM Provider:
   - Name (e.g., "OpenAI")
   - API Key
   - Base URL (e.g., "https://api.openai.com/v1" for OpenAI)
   - Save to fetch available models

### 2. LLM Model Configuration

1. Go to `LLM > Configuration > LLM Models`
2. Available models will be automatically fetched from configured providers
3. Enable/disable models as needed

### 3. AI Agent Setup

1. First, create an internal user:
   - Navigate to `Settings > Users & Companies > Users`
   - Create new user with:
     - Name
     - Email
     - Internal User access rights

2. Create AI Agent:
   - Go to `LLM > AI Agents`
   - Click Create
   - Configure:
     - Select the internal user
     - Define Role (e.g., "Financial Analyst")
     - Set Goal
     - Add Backstory
     - Select LLM Provider and Model
     - Enable "Allow Odoo Tools" for MIS report generation capabilities

## 💻 Usage

### Setting Up Tasks

1. Create a Project:
   - Navigate to `Project > Projects`
   - Create new project
   - Configure basic project settings

2. Create Task:
   - Create new task in the project
   - Assign the AI Agent
   - Provide detailed description
   - Specify expected output
   - Click "Execute AI Task" to start processing

### MIS Report Generation

When an AI agent has "Allow Odoo Tools" enabled, it can:
- Create MIS report templates
- Generate report instances
- Configure KPIs and styling

Example task description for MIS report generation:
```
Create a Profit & Loss statement template with the following sections:
- Revenue
- Cost of Goods Sold
- Gross Profit
- Operating Expenses
- Net Profit

Include year-to-date comparisons and percentage changes.
```

## ⚠️ Prototype Limitations

- Limited to specific LLM providers
- Basic task management features
- Experimental AI integration
- Manual configuration required
- Style options may need adjustment

## 🛠️ Development Notes

- This is a prototype version
- API interfaces may change
- Testing needed for complex reports
- Performance optimization pending

## 📚 Related Documentation

- [Odoo Development Guide](https://www.odoo.com/documentation/16.0/developer.html)
- [MIS Builder Documentation](https://github.com/OCA/mis-builder)

## 🎮 Demo & Examples

For detailed examples of AI agent tasks and configurations, please refer to the [DEMO.md](DEMO.md) file. It includes:
- Sample task descriptions
- AI agent role configurations
- Expression handling examples
- Styling guidelines
- Report generation examples
