from odoo import api, models, _
from odoo.exceptions import UserError

from crewai import Task, Crew


class LLMCrewExecutor(models.AbstractModel):
    """CrewAI implementation of task executor."""
    _inherit = 'llm.agent.task.executor'

    @api.model
    def _get_available_services(self):
        """Register CrewAI service."""
        services = super()._get_available_services()
        services.append(('crewai', 'CrewAI'))
        return services

    def crewai_execute_task(self, task_record, **kwargs):
        """CrewAI specific task execution.
        
        This follows the service dispatch pattern naming:
        {service}_{method}
        
        Args:
            task_record: Record containing task information
            **kwargs: Additional arguments including:
                - process: 'sequential' or 'hierarchical'
                
        Returns:
            str: Execution result
        """
        # For hierarchical, we need to validate the manager agent
        if kwargs.get('process') == 'hierarchical':
            agent = self._validate_manager_agent(task_record)
        else:
            agent = self.validate_task_execution(task_record)

        # Prepare crew configuration based on process
        tasks, agents = self._prepare_crew_tasks(task_record, agent, kwargs.get('process'))
        crew_kwargs = self._prepare_crew_kwargs(tasks, agents, agent, kwargs.get('process'))

        # Execute and return results
        return self._execute_crew(crew_kwargs)

    def _validate_manager_agent(self, task_record):
        """Validate manager agent for hierarchical process."""
        agent = self._get_agent_for_task(task_record)
        if not agent:
            raise UserError(_("Hierarchical process requires a manager agent assigned to the main task"))
        
        if not agent.is_manager:
            raise UserError(_("Agent assigned to main task must be a manager for hierarchical process"))
            
        if not agent.member_ids:
            raise UserError(_("Manager agent must have team members for hierarchical process"))
            
        return agent

    def _prepare_crew_tasks(self, task_record, agent, process):
        """Prepare CrewAI tasks and agents based on process type.
        
        Args:
            task_record: The main task record
            agent: The main agent (or manager for hierarchical)
            process: 'sequential' or 'hierarchical'
            
        Returns:
            tuple: (tasks, agents) where:
                - tasks is list of CrewAI Task objects
                - agents is list of CrewAI Agent objects (for sequential)
                  or None (for hierarchical)
        """
        if process == 'sequential':
            return self._prepare_sequential_tasks(task_record, agent)
        else:
            return self._prepare_hierarchical_tasks(task_record), None

    def _prepare_sequential_tasks(self, task_record, agent):
        """Prepare tasks and agents for sequential process."""
        tasks = []
        agents = []

        # Main task with its agent
        main_task = Task(
            description=task_record.description,
            expected_output=task_record.expected_output or "Complete the task successfully",
            agent=agent.get_instance()  # This will use crewai_get_instance
        )
        tasks.append(main_task)
        agents.append(agent.get_instance())

        # Handle subtasks
        if task_record.child_ids:
            for subtask in task_record.child_ids.sorted(lambda t: t.sequence):
                subtask_agent = self._get_agent_for_task(subtask)
                if not subtask_agent:
                    raise UserError(_(
                        "Sequential process requires each subtask to have an AI agent assigned. "
                        "Missing agent for subtask: %s"
                    ) % subtask.name)

                crew_agent = subtask_agent.get_instance()
                if crew_agent not in agents:
                    agents.append(crew_agent)

                tasks.append(Task(
                    description=subtask.description or f"Subtask of {task_record.name}",
                    expected_output=subtask.expected_output or "Complete the subtask successfully",
                    agent=crew_agent
                ))

        return tasks, agents

    def _prepare_hierarchical_tasks(self, task_record):
        """Prepare tasks for hierarchical process."""
        tasks = []

        # Main task without pre-assigned agent
        tasks.append(Task(
            description=task_record.description,
            expected_output=task_record.expected_output or "Complete the task successfully"
        ))

        # Add subtasks without pre-assigned agents
        if task_record.child_ids:
            for subtask in task_record.child_ids.sorted(lambda t: t.sequence):
                tasks.append(Task(
                    description=subtask.description or f"Subtask of {task_record.name}",
                    expected_output=subtask.expected_output or "Complete the subtask successfully"
                ))

        return tasks

    def _prepare_crew_kwargs(self, tasks, agents, main_agent, process):
        """Prepare CrewAI configuration based on process type."""
        crew_kwargs = {
            "tasks": tasks,
            "process": process,
            "verbose": True
        }

        if process == 'hierarchical':
            # For hierarchical, use manager's team members
            crew_kwargs.update({
                "manager_agent": main_agent.get_instance(),
                "agents": [member.get_instance() for member in main_agent.member_ids]
            })
        else:
            # For sequential, use the pre-assigned agents
            crew_kwargs["agents"] = agents

        return crew_kwargs

    def _execute_crew(self, crew_kwargs):
        """Execute the CrewAI crew.
        
        Args:
            crew_kwargs: Configuration for CrewAI Crew
            
        Returns:
            str: Execution result
        """
        crew = Crew(**crew_kwargs)
        return crew.kickoff()
