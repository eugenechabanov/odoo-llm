from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _message_post_after_hook(self, message, msg_vals):
        """Handle AI agent responses to messages."""
        res = super()._message_post_after_hook(message, msg_vals)
        _logger.info(
            "Processing message post hook - Message ID: %s, Author: %s, Content: %s",
            message.id, message.author_id.name, msg_vals.get('body', '')[:100]
        )

        # Skip if we're installing the module
        if self.env.context.get('module') == 'llm_agent':
            _logger.info("Skipping during module installation")
            return res

        # Skip if message is from an agent (to avoid loops)
        author = message.author_id.user_ids and message.author_id.user_ids[0]
        if not author:
            _logger.info("Skipping - No author user found for partner %s", message.author_id.name)
            return res
        if author.is_user_agent():
            _logger.info("Skipping - Message is from an agent %s", author.name)
            return res

        # Find mentioned agents
        mentioned_partners = message.partner_ids
        _logger.info("Checking mentioned partners: %s", mentioned_partners.mapped('name'))
        
        mentioned_agents = self.env['res.users'].search([
            ('partner_id', 'in', mentioned_partners.ids),
            ('is_active', '=', True)
        ]).filtered(lambda u: u.is_user_agent())
        
        if mentioned_agents:
            _logger.info("Found mentioned agents: %s", mentioned_agents.mapped('name'))

        # Also check for private chat with agent
        if not mentioned_agents and self._name == 'mail.channel' and self.channel_type == 'chat':
            _logger.info("No mentioned agents, checking if private chat")
            if len(self.channel_partner_ids) == 2:
                other_partner = self.channel_partner_ids - message.author_id
                _logger.info("Private chat with: %s", other_partner.name)
                
                other_user = self.env['res.users'].search([
                    ('partner_id', '=', other_partner.id),
                    ('is_active', '=', True)
                ], limit=1)
                
                if other_user and other_user.is_user_agent():
                    _logger.info("Found agent in private chat: %s", other_user.name)
                    mentioned_agents = other_user
                else:
                    _logger.info("Other user is not an agent or not active")

        # Generate debug response for each mentioned agent
        for agent in mentioned_agents:
            if agent.model_id:
                _logger.info(
                    "Generating response for agent %s using model %s",
                    agent.name, agent.model_id.name
                )
                message.reply(
                    body=f"Debug: Agent {agent.name} would respond using {agent.model_id.name}\n"
                         f"Message received: {msg_vals.get('body', '')}"
                )
            else:
                _logger.warning("Agent %s has no model configured, skipping response", agent.name)

        return res
