from odoo import models, _
import logging

_logger = logging.getLogger(__name__)

class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _message_post_after_hook(self, message, msg_vals):
        """Handle agent responses after message post"""
        res = super()._message_post_after_hook(message, msg_vals)
        
        # Check if message is from a human user
        if msg_vals.get('author_id'):
            author = self.env['res.partner'].browse(msg_vals['author_id'])
            if author.user_ids and not any(user.user_type == 'agent' for user in author.user_ids):
                # Get mentioned partners
                mentioned_partners = message.partner_ids
                
                # Find mentioned agents
                mentioned_agents = self.env['res.users'].search([
                    ('partner_id', 'in', mentioned_partners.ids),
                    ('user_type', '=', 'agent'),
                    ('is_active', '=', True)
                ])

                # Check for private chat with agent
                if not mentioned_agents and self._name == 'mail.channel' and self.channel_type == 'chat':
                    if len(self.channel_partner_ids) == 2:
                        agent_partner = self.channel_partner_ids - author
                        agent_user = self.env['res.users'].search([
                            ('partner_id', '=', agent_partner.id),
                            ('user_type', '=', 'agent'),
                            ('is_active', '=', True)
                        ], limit=1)
                        if agent_user:
                            mentioned_agents = agent_user

                # Generate debug response for each mentioned agent
                for agent in mentioned_agents:
                    try:
                        response = _(
                            "Hello, I am %(name)s! "
                            "I'm using the %(model)s model. "
                            "Message received: %(msg)s"
                        ) % {
                            'name': agent.name,
                            'model': agent.model_id.name,
                            'msg': msg_vals.get('body', '')
                        }

                        # Post response
                        self.with_context(mail_create_nosubscribe=True).message_post(
                            body=response,
                            author_id=agent.partner_id.id,
                            message_type='comment',
                            subtype_xmlid='mail.mt_comment'
                        )
                        _logger.info("Agent %s responded to message", agent.name)
                    except Exception as e:
                        _logger.exception("Error generating debug response for agent %s", agent.name)
        
        return res
