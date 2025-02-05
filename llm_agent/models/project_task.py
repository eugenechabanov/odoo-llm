from odoo import fields, models, api, _
from odoo.exceptions import UserError
import logging
from crewai import Task, Crew

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
    is_ai_executable = fields.Boolean(compute='_compute_is_ai_executable')

    @api.depends('user_ids')
    def _compute_is_ai_executable(self):
        """Determine if the task can be executed by AI.
        
        A task can be executed by AI if:
        1. It has an AI agent assigned
        3. It has a description (this is checked in execute_task)
        """
        for task in self:
            task.is_ai_executable = task._has_ai_agent_assigned() 

    def _has_ai_agent_assigned(self):
        """Check if any of the task's assigned users is an AI agent"""
        self.ensure_one()
        return bool(self.env['llm.agent'].search_count([
            ('user_id', 'in', self.user_ids.ids),
            ('active', '=', True)
        ]))

    def _get_agent(self):
        """Get the AI agent for the assigned user"""
        self.ensure_one()
        return self.env['llm.agent'].search([
            ('user_id', 'in', self.user_ids.ids),
            ('active', '=', True)
        ], limit=1)

    def action_execute_ai_task(self):
        """Action triggered by the Execute AI Task button"""
        self.ensure_one()
        if not self.is_ai_executable:
            raise UserError(_("This task cannot be executed by AI. Please ensure it is assigned to an AI agent."))
        return self.execute_task()

    def _validate_task_execution(self):
        """Validate if task can be executed by AI"""
        if not self.user_ids:
            raise UserError(_("Cannot execute AI task: No assignee specified"))
        if not self._has_ai_agent_assigned():
            raise UserError(_("Cannot execute AI task: Assignee is not an AI agent"))
        if not self.description:
            raise UserError(_("Cannot execute AI task: No description provided"))
        
        agent = self._get_agent()
        if not agent:
            raise UserError(_("Cannot execute AI task: AI agent not found"))
        return agent

    def _prepare_crew_tasks_and_agents(self, agent):
        """Prepare CrewAI tasks and agents based on process type.
        
        For sequential process:
        - Each task (main and subtasks) must have their own AI agent
        - Tasks are executed in sequence with their assigned agents
        
        For hierarchical process:
        - Tasks don't have individual agents assigned
        - Manager agent oversees task distribution to team members
        """
        tasks = []
        agents_to_use = []
        
        if self.process == 'sequential':
            # For sequential, each task needs its own agent
            main_task = Task(
                description=self.description,
                expected_output=self.expected_output or "Complete the task successfully",
                agent=agent._to_crewai_agent()
            )
            tasks.append(main_task)
            agents_to_use.append(agent._to_crewai_agent())
            
            # Handle subtasks
            if self.allow_subtasks and self.child_ids:
                for subtask in self.child_ids.sorted(lambda t: t.sequence):
                    subtask_agent = self._get_subtask_agent(subtask)
                    if not subtask_agent:
                        raise UserError(_("Sequential process requires each subtask to have an AI agent assigned"))
                        
                    subtask_crew_agent = subtask_agent._to_crewai_agent()
                    if subtask_crew_agent not in agents_to_use:
                        agents_to_use.append(subtask_crew_agent)
                    
                    tasks.append(Task(
                        description=subtask.description or f"Subtask of {self.name}",
                        expected_output=subtask.expected_output or "Complete the subtask successfully",
                        agent=subtask_crew_agent
                    ))
        else:
            # For hierarchical, tasks don't have individual agents
            main_task = Task(
                description=self.description,
                expected_output=self.expected_output or "Complete the task successfully"
            )
            tasks.append(main_task)
            
            # Handle subtasks
            if self.allow_subtasks and self.child_ids:
                for subtask in self.child_ids.sorted(lambda t: t.sequence):
                    tasks.append(Task(
                        description=subtask.description or f"Subtask of {self.name}",
                        expected_output=subtask.expected_output or "Complete the subtask successfully"
                    ))
            
        return tasks, agents_to_use

    def _get_subtask_agent(self, subtask):
        """Get AI agent for a subtask"""
        for user in subtask.user_ids:
            agent = self.env['llm.agent'].search([
                ('user_id', '=', user.id),
                ('active', '=', True)
            ], limit=1)
            if agent:
                return agent
        return None

    def _prepare_crew_kwargs(self, tasks, agents_to_use, agent):
        """Prepare kwargs for CrewAI initialization based on process type.
        
        For sequential process:
        - Uses list of agents assigned to individual tasks
        - No manager agent needed
        
        For hierarchical process:
        - Uses manager agent and their team members
        - Tasks are distributed by the manager to team members
        """
        crew_kwargs = {
            'tasks': tasks,
            'process': self.process,
            'verbose': True,
        }

        if self.process == 'hierarchical':
            if not agent.member_ids or not agent.is_manager:
                raise UserError(_("Hierarchical process requires a manager agent with team members"))
                
            # For hierarchical, we use manager's team members as agents
            crew_kwargs.update({
                'manager_agent': agent._to_crewai_agent(),
                'agents': [member._to_crewai_agent() for member in agent.member_ids]
            })
        else:
            # For sequential, we use the agents assigned to individual tasks
            crew_kwargs['agents'] = agents_to_use
            
        return crew_kwargs

    def _update_subtask_results(self, tasks):
        """Update subtask results from CrewAI task outputs.
        
        Args:
            tasks: List of CrewAI Task objects, where tasks[1:] are subtasks
        """
        if self.allow_subtasks and self.child_ids and len(tasks) > 1:
            for task in tasks[1:]:  # Skip the first task (main task)
                if task.output:
                    matching_tasks = self.child_ids.filtered(lambda t: t.description == task.output.description)
                    if matching_tasks:
                        # Calculate execution time if start_time and end_time are available
                        execution_time = None
                        if task.start_time and task.end_time:
                            execution_time = (task.end_time - task.start_time).total_seconds()
                        
                        matching_tasks[0].write({
                            'ai_result': task.output.raw,
                            'kanban_state': 'done',
                            'execution_time': execution_time
                        })

    def _create_result_message(self, execution_time, result):
        """Create message for task completion"""
        message = f"<b>AI Task Completed</b><br/>"
        message += f"Execution Time: {execution_time:.2f}s<br/>"
        message += f"Process: {self.process}<br/>"
        if self.process == 'hierarchical':
            message += f"Manager: {self._get_agent().role}<br/>"
        message += f"<br/>{result}"
        return message

    def execute_task(self):
        """Execute the AI task."""
        self.ensure_one()
        
        # Validate and get agent
        agent = self._validate_task_execution()
        self.kanban_state = 'normal'
        
        try:
            # Prepare tasks and agents
            tasks, agents_to_use = self._prepare_crew_tasks_and_agents(agent)
            crew_kwargs = self._prepare_crew_kwargs(tasks, agents_to_use, agent)
            
            # Execute crew
            import time
            start_time = time.time()
            crew = Crew(**crew_kwargs)
            result = crew.kickoff()
            execution_time = time.time() - start_time
            
            # Update task results
            self.write({
                'execution_time': execution_time,
                'ai_result': result,
                'kanban_state': 'done'
            })
            
            # Update subtask results
            self._update_subtask_results(tasks)
            
            # Post result message
            message = self._create_result_message(execution_time, result)
            self.message_post(
                body=message,
                message_type="comment",
                author_id=agent.user_id.partner_id.id
            )
            
        except Exception as e:
            self.kanban_state = 'blocked'
            self.message_post(
                body=f"<b>AI Task Failed</b><br/>{str(e)}",
                message_type="comment",
                author_id=agent.user_id.partner_id.id
            )
            raise UserError(_("AI task execution failed: %s") % str(e))
