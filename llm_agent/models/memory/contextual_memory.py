from odoo import models, fields, api, _

class LLMContextualMemory(models.AbstractModel):
    _name = 'llm.memory.contextual'
    _description = 'Contextual Memory Manager'
    
    @api.model
    def build_context_for_task(self, task_id, context="", user=None, message_content=None):
        """Build context for a task using various memory sources
        
        Args:
            task_id: ID of the task to build context for
            context: Additional context string to include in the search
            user: res.users record for user-specific context
            message_content: Optional message content to search for relevant memories
        """
        task = self.env['llm.agent.task'].browse(task_id)
        query = f"{task.description} {context}".strip()
        
        if not query:
            return ""
            
        context_parts = []
        
        # Get long-term memory context
        ltm = self.env['llm.memory.long_term']
        ltm_results = ltm.search_memory(task.description)
        if ltm_results:
            context_parts.append("Previous similar tasks:")
            for mem in ltm_results:
                context_parts.append(f"- Task: {mem.task_description}")
                if mem.expected_output:
                    context_parts.append(f"  Output: {mem.expected_output}")
                if mem.quality_score > 0:
                    context_parts.append(f"  Quality: {mem.quality_score}")
        
        # Get short-term memory context
        stm = self.env['llm.memory.short_term']
        stm_results = stm.search_memory(query)
        if stm_results:
            context_parts.append("\nRecent relevant context:")
            for mem in stm_results:
                context_parts.append(f"- {mem.data}")
        
        # Get user-related context if a user is provided
        if user:
            um = self.env['llm.memory.user']
            
            # Get user preferences using search_memory
            user_prefs = um.search_memory("user preference", limit=5)
            if user_prefs:
                context_parts.append("\nUser preferences:")
                for pref in user_prefs:
                    context_parts.append(f"- {pref.data}")
            
            # Get message-specific memories if message content is provided
            if message_content:
                context_memories = um.search_memory(message_content, limit=3)
                if context_memories:
                    context_parts.append("\nRelevant user context:")
                    for mem in context_memories:
                        context_parts.append(f"- {mem.data}")
        
        return "\n".join(context_parts)
    
    @api.model
    def save_task_result(self, task_id, result, quality_score=None):
        """Save task result to both short-term and long-term memory"""
        task = self.env['llm.agent.task'].browse(task_id)
        
        # Save to short-term memory
        self.env['llm.memory.short_term'].save(
            data=result,
            metadata={'task_id': task_id},
            agent=task.agent_id.id,
            task_id=task_id
        )
        
        # Save to long-term memory if quality score is provided
        if quality_score is not None:
            self.env['llm.memory.long_term'].save(
                task=task.description,
                expected_output=result,
                agent=task.agent_id.id,
                quality=quality_score,
                metadata={'task_id': task_id}
            )
