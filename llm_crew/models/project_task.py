from bdb import effective
from odoo import fields, models, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)
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

    @api.depends('user_ids')
    def _compute_can_execute_ai(self):
        """Determine if the task can be executed by AI"""
        for task in self:
            task.can_execute_ai = task._is_ai_agent() and not task.kanban_state in ('normal')

    def _is_ai_agent(self):
        """Check if the assigned user is an AI agent"""
        self.ensure_one()
        return bool(self.env['llm.crew.agent'].search_count([
            ('user_id', 'in', self.user_ids.ids),
            ('active', '=', True)
        ]))

    def _get_agent(self):
        """Get the AI agent for the assigned user"""
        self.ensure_one()
        return self.env['llm.crew.agent'].search([
            ('user_id', 'in', self.user_ids.ids),
            ('active', '=', True)
        ], limit=1)

    def action_execute_ai_task(self):
        """Action triggered by the Execute AI Task button"""
        self.ensure_one()
        if not self.can_execute_ai:
            raise UserError(_("This task cannot be executed by AI. Please ensure it is assigned to an AI agent."))
        return self.execute_task()

    def execute_task(self):
        """Execute the task using a CrewAI crew. If the task has subtasks, they will be executed in sequence order."""
        self.ensure_one()
        
        if not self.user_ids:
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

        tasks = []
        agents_to_use = []
        
        # Create main task
        main_task = Task(
            description=self.description,
            expected_output=self.expected_output or "Complete the task successfully",
            agent=agent._to_crewai_agent() if self.process == 'sequential' else None,
        )
        tasks.append(main_task)
        
        # Handle subtasks if allowed and present
        if self.allow_subtasks and self.child_ids:
            # Sort subtasks by sequence
            sorted_subtasks = self.child_ids.sorted(lambda t: t.sequence)
            
            for subtask in sorted_subtasks:
                # For sequential process, ensure each subtask has an AI agent assigned
                if self.process == 'sequential':
                    subtask_agent = None
                    # Check if any assigned user is an AI agent
                    for user in subtask.user_ids:
                        potential_agent = self.env['llm.crew.agent'].search([
                            ('user_id', '=', user.id),
                            ('active', '=', True)
                        ], limit=1)
                        if potential_agent:
                            subtask_agent = potential_agent
                            break
                    
                    # If no AI agent found among assigned users, use main task's agent
                    if not subtask_agent:
                        raise UserError(_("No AI agent found among assigned users for subtask"))
                        
                    subtask_crew_agent = subtask_agent._to_crewai_agent()
                    if subtask_crew_agent not in agents_to_use:
                        agents_to_use.append(subtask_crew_agent)
                else:
                    subtask_crew_agent = None
                
                # Create CrewAI task for subtask
                subtask_task = Task(
                    description=subtask.description or f"Subtask of {self.name}",
                    expected_output=subtask.expected_output or "Complete the subtask successfully",
                    agent=subtask_crew_agent if self.process == 'sequential' else None,
                )
                tasks.append(subtask_task)
        
        try:
            # Create and execute the crew
            import time
            start_time = time.time()
            
            crew_kwargs = {
                'tasks': tasks,
                'process': self.process,
                'verbose': True,
            }
            effective_agents = []
            # If hierarchical process, use manager and team members
            if self.process == 'hierarchical':
                if not agent.member_ids or not agent.is_manager:
                    raise UserError(_("Hierarchical process requires a manager agent with team members"))
                effective_agents.append(agent._to_crewai_agent())
                effective_agents.extend([member._to_crewai_agent() for member in agent.member_ids])
                crew_kwargs.update({
                    'agents': effective_agents,
                    'manager_agent': agent._to_crewai_agent(),
                })
            else:
                if agents_to_use:
                    effective_agents.extend(agents_to_use)
                else:
                    effective_agents.append(agent._to_crewai_agent())
                # For sequential process, use the collected agents or just the main agent
                crew_kwargs['agents'] = effective_agents
            
            crew = Crew(**crew_kwargs)
            # log the tasks and agents
            
            
            for task in tasks:
                _logger.info(f"Task: {task.description} - {task.agent.role if task.agent else 'No Agent'}")
            for agent in effective_agents:
                _logger.info(f"Agent: {agent.role}")
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
                message += f"Manager: {agent.role}<br/>"
                message += f"Team Size: {len(agent.member_ids)}<br/>"
            if self.child_ids:
                message += f"Subtasks Executed: {len(self.child_ids)}<br/>"
            message += f"<br/>{result}"
            
            self.message_post(
                body=message,
                message_type="comment",
                author_id=agent.user_id.partner_id.id
            )
            
        except Exception as e:
            # Mark task as blocked on failure
            self.kanban_state = 'blocked'
            self.message_post(
                body=f"<b>AI Task Failed</b><br/>{str(e)}",
                message_type="comment",
                author_id=agent.user_id.partner_id.id
            )
            raise UserError(_("AI task execution failed: %s") % str(e))
