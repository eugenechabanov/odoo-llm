from odoo import api, models, _
from odoo.exceptions import UserError
import re


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _message_post_after_hook(self, message, msg_vals):
        """Handle AI agent mentions and trigger crew execution.
        
        If a mentioned user is an AI agent:
        1. Find their associated crew (team)
        2. Execute the prompt with the message content
        3. Post the response as a message from the AI agent
        """
        res = super()._message_post_after_hook(message, msg_vals)
        
        # Check for AI agent mentions
        if message.partner_ids:
            mentioned_users = self.env['res.users'].search([
                ('partner_id', 'in', message.partner_ids.ids)
            ])
            
            for user in mentioned_users:
                # Check if user is an AI agent
                ai_agent = self.env['llm.crew.agent'].search([
                    ('user_id', '=', user.id),
                    ('active', '=', True)
                ], limit=1)
                
                if not ai_agent:
                    continue
                    
                # Find the crew (team) this agent belongs to
                crew = self.env['crm.team'].search([
                    ('is_crew', '=', True),
                    ('member_ids', 'in', [user.id])  
                ], limit=1)
                
                if not crew:
                    self.with_context(mail_create_nosubscribe=True).message_post(
                        body="Crew not found for AI agent %s" % user.name,
                        message_type='comment',
                        subtype_xmlid='mail.mt_comment',
                        author_id=user.partner_id.id
                    )
                    continue
                
                try:
                    # Execute the prompt
                    result = crew.execute_crew_prompt(message.body)
                    
                    # Post response as the AI agent
                    self.with_context(mail_create_nosubscribe=True).message_post(
                        body=result,
                        message_type='comment',
                        subtype_xmlid='mail.mt_comment',
                        author_id=user.partner_id.id
                    )
                    
                except Exception as e:
                    error_msg = _(
                        "Error while processing request for AI agent %s: %s"
                    ) % (user.name, str(e))
                    self.with_context(mail_create_nosubscribe=True).message_post(
                        body=error_msg,
                        message_type='comment',
                        subtype_xmlid='mail.mt_comment',
                        author_id=user.partner_id.id
                    )
                    
        return res

    def _extract_message_content(self, message):
        """Extract clean message content from a mail message.
        
        Args:
            message: mail.message record
            
        Returns:
            str: Clean message content
        """
        content = message.body
        
        # Remove HTML tags
        content = re.sub(r'<[^>]+>', '', content)
        
        # Remove quoted content
        content = re.sub(r'On.*wrote:', '', content)
        
        # Remove extra whitespace
        content = re.sub(r'\s+', ' ', content).strip()
        
        return content
