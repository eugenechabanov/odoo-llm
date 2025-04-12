# Website LLM Models

This module adds a public website page that displays all available LLM models in the system, categorized by their use and provider.

## Features

- Public website page accessible at `/llm/models`
- Models displayed by type (chat, completion, embedding, multimodal)
- Models displayed by provider
- Publishers section with logos and descriptions
- Automatically added to website menu
- Mobile-friendly responsive design

## Dependencies

- `llm`: Base LLM integration module
- `website`: Odoo Website module

## Installation

Install this module along with its dependencies to enable the public models page.

## Usage

After installation, the module automatically adds an "AI Models" entry to your website's main menu. Visitors can access the page to view all active models in the system.

The page displays:
- Models categorized by type
- Models categorized by provider
- Model publishers with their details

## Security

The module provides read-only public access to the following models:
- `llm.model`
- `llm.provider`
- `llm.publisher`

Only active models are displayed on the website page.

## Customization

You can customize the appearance of the page by:
1. Editing the `models_page` template in the `templates.xml` file
2. Adding your own styles through website theme customization

## Feedback and Support

For support, please contact the module author or visit the GitHub repository.
