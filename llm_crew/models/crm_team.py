from odoo import models, fields, api, _
from odoo.exceptions import UserError
from crewai import Agent, Crew, Process, Task
class CRMTeam(models.Model):
    _inherit = 'crm.team'

    is_crew = fields.Boolean(string="Is AI Crew", default=False, tracking=True)
    project_id = fields.Many2one('project.project', string="AI Project", tracking=True)
    crew_manager_id = fields.Many2one(
        'res.users', 
        string="Crew Manager",
        domain="[('id', 'in', member_ids)]",
        tracking=True
    )

    def execute_crew_prompt(self, prompt):
        self.ensure_one()
        if not self.is_crew:
            raise UserError(_("This team is not configured as an AI crew"))

        if not self.crew_manager_id:
            raise UserError(_("Please assign a crew manager"))

        if not self.project_id:
            raise UserError(_("Please assign an AI project"))

        # Get manager agent
        manager_agent = self.env['llm.crew.agent'].search([
            ('user_id', '=', self.crew_manager_id.id)
        ])
        if not manager_agent:
            raise UserError(_("Crew manager must have an AI agent configuration"))

        # Get crew agents
        crew_agents = self.env['llm.crew.agent'].search([
            ('user_id', 'in', self.member_ids.ids)
        ])
        if not crew_agents:
            raise UserError(_("No AI agents found in the crew"))

        # Get project tasks and format with prompt
        tasks = self.project_id.task_ids.filtered(
            lambda t: t.is_crew_task
        )
        if not tasks:
            raise UserError(_("No active crew tasks found in the project"))

        crew_tasks = []
        for task in tasks:
            agent = crew_agents.filtered(lambda a: a.user_id.id in task.user_ids.ids)
                
            crew_tasks.append(Task(
                description=task.description.format(prompt=prompt),
                expected_output=task.expected_output,
                agent=agent._to_crewai_agent() if agent else None
            ))

        # Create and execute crew
        crew = Crew(
            agents=[agent._to_crewai_agent() for agent in crew_agents],
            tasks=crew_tasks,
            manager_agent=manager_agent._to_crewai_agent(),
            process='hierarchical'
        )
        
        return crew.kickoff()
