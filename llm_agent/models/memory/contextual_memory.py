from odoo import models, fields, api, _

class LLMContextualMemory(models.AbstractModel):
    _name = 'llm.memory.contextual'
    _description = 'Contextual Memory Manager'
    
    @api.model
    def build_context_for_task(self, task_id, context=""):
        """Build context for a task using various memory sources"""
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
        
        # Get user preferences if available
        if task.create_uid:
            um = self.env['llm.memory.user']
            user_prefs = um.get_user_preferences(task.create_uid.id)
            if user_prefs:
                context_parts.append("\nUser preferences:")
                for pref in user_prefs:
                    context_parts.append(f"- {pref.preference_type}: {pref.data}")
        
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
