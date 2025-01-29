from odoo import api, models, _
from odoo.exceptions import UserError
import re


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _message_post_after_hook(self, message, msg_vals):
        """Handle AI agent mentions after message post."""
        result = super()._message_post_after_hook(message, msg_vals)
        
        # Only process if there are mentions
        if not message.partner_ids:
            return result
            
        # Get mentioned users that are AI agents
        User = self.env['res.users']
        mentioned_users = User.search([
            ('partner_id', 'in', message.partner_ids.ids),
            ('llm_enabled', '=', True),
        ])
        
        if not mentioned_users:
            return result
            
        # Process each AI agent mention
        for user in mentioned_users:
            try:
                self._process_ai_agent_mention(message, user)
            except Exception as e:
                message.message_post(
                    body=_(
                        "Failed to process mention for AI agent %(name)s: %(error)s",
                        name=user.name,
                        error=str(e)
                    ),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )
                
        return result
        
    def _process_ai_agent_mention(self, message, agent_user):
        """Process mention of an AI agent in a message.
        
        Args:
            message: mail.message record that contains the mention
            agent_user: res.users record of the mentioned AI agent
        """
        # Extract message content
        content = self._extract_message_content(message)
        if not content:
            return
            
        # Create task for agent
        task = self.env['project.task'].create({
            'name': _('Chat Response: %s', message.subject or 'Untitled'),
            'description': content,
            'user_id': agent_user.id,
            'llm_enabled': True,
            'llm_provider_id': agent_user.llm_provider_id.id,
            'llm_model_id': agent_user.llm_model_id.id,
            'llm_memory_enabled': agent_user.llm_memory_enabled,
            'llm_memory_config': agent_user.llm_memory_config,
            'llm_expected_output': 'Provide a helpful response to the user\'s message',
            'llm_output_format': 'markdown',
            'llm_async_execution': False,  # Execute synchronously for chat
        })
        
        # Execute task
        try:
            task.execute_task()
            
            # Post response
            message.message_post(
                body=task.llm_result,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
            
        finally:
            # Clean up task
            task.unlink()
            
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
