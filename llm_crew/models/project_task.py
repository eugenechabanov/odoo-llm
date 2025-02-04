from odoo import fields, models, api, _
from odoo.exceptions import UserError


class ProjectTask(models.Model):
    _inherit = "project.task"

    expected_output = fields.Text(string="Expected Output", tracking=True,
                                help="Expected output format or success criteria for AI task execution")
    ai_result = fields.Text(string="AI Result", tracking=True)
    execution_time = fields.Float(string="Execution Time (s)", tracking=True)
    process = fields.Selection([
        ('sequential', 'Sequential'),
        ('hierarchical', 'Hierarchical')
    ], default='sequential', required=True)
    can_execute_ai = fields.Boolean(compute='_compute_can_execute_ai')

    @api.depends('user_id')
    def _compute_can_execute_ai(self):
        """Determine if the task can be executed by AI"""
        for task in self:
            task.can_execute_ai = task._is_ai_agent() and not task.ai_result

    def _is_ai_agent(self):
        """Check if the assigned user is an AI agent"""
        self.ensure_one()
        return bool(self.env['llm.crew.agent'].search_count([
            ('user_id', '=', self.user_id.id),
            ('active', '=', True)
        ]))

    def _get_agent(self):
        """Get the AI agent for the assigned user"""
        self.ensure_one()
        return self.env['llm.crew.agent'].search([
            ('user_id', '=', self.user_id.id),
            ('active', '=', True)
        ], limit=1)

    def action_execute_ai_task(self):
        """Action triggered by the Execute AI Task button"""
        self.ensure_one()
        if not self.can_execute_ai:
            raise UserError(_("This task cannot be executed by AI. Please ensure it is assigned to an AI agent."))
        return self.execute_task()

    def execute_task(self):
        """Execute the task using a CrewAI crew"""
        self.ensure_one()
        
        if not self.user_id:
            raise UserError(_("Cannot execute AI task: No assignee specified"))
            
        if not self._is_ai_agent():
            raise UserError(_("Cannot execute AI task: Assignee is not an AI agent"))
            
        if not self.description:
            raise UserError(_("Cannot execute AI task: No description provided"))

        # Get the executing agent
        agent = self._get_agent()
        if not agent:
            raise UserError(_("Cannot execute AI task: AI agent not found"))
            
        # Set kanban state to in progress
        self.kanban_state = 'normal'
        
        # Create CrewAI task and agents
        from crewai import Task, Crew
        
        # Create task for the agent
        crew_task = Task(
            description=self.description,
            expected_output=self.expected_output or "Complete the task successfully",
            agent=agent._to_crewai_agent() if self.process == 'sequential' else None,
        )
        
        try:
            # Create and execute the crew
            import time
            start_time = time.time()
            
            crew_kwargs = {
                'agents': [agent._to_crewai_agent()],
                'tasks': [crew_task],
                'process': self.process,
                'verbose': True,
            }
            
            # If hierarchical process, ensure agent can manage
            if self.process == 'hierarchical':
                if not agent.member_ids or not agent.is_manager:
                    raise UserError(_("Hierarchical process requires a manager agent with team members"))
                crew_kwargs.update({
                    'agents': [member._to_crewai_agent() for member in agent.member_ids],
                    'manager_agent': agent._to_crewai_agent(),
                })
            
            crew = Crew(**crew_kwargs)
            result = crew.kickoff()
            execution_time = time.time() - start_time
            
            # Update task with results and mark as ready
            self.write({
                'ai_result': result,
                'execution_time': execution_time,
                'kanban_state': 'done'
            })
            
            # Post result as a message
            message = f"<b>AI Task Completed</b><br/>"
            message += f"Execution Time: {execution_time:.2f}s<br/>"
            message += f"Process: {self.process}<br/>"
            if self.process == 'hierarchical':
                message += f"Manager: {agent.name}<br/>"
                message += f"Team Size: {len(agent.member_ids)}<br/>"
            message += f"<br/>{result}"
            
            self.message_post(
                body=message,
                message_type="comment",
                author_id=self.user_id.partner_id.id
            )
            
        except Exception as e:
            # Mark task as blocked on failure
            self.kanban_state = 'blocked'
            self.message_post(
                body=f"<b>AI Task Failed</b><br/>{str(e)}",
                message_type="comment",
                author_id=self.user_id.partner_id.id
            )
            raise UserError(_("AI task execution failed: %s") % str(e))
