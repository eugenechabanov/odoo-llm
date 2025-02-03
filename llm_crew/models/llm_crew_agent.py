from odoo import models, fields, _
from crewai import Agent, LLM

class LLMCrewAgent(models.Model):
    _name = 'llm.crew.agent'
    _description = 'LLM Crew Agent'
    _inherit = ['mail.thread']

    name = fields.Char(required=True, tracking=True)
    user_id = fields.Many2one('res.users', required=True, tracking=True)
    llm_provider_id = fields.Many2one('llm.provider', required=True, tracking=True)
    llm_model_id = fields.Many2one('llm.model', required=True, tracking=True)
    role = fields.Text(required=True, tracking=True)
    goal = fields.Text(required=True, tracking=True)
    backstory = fields.Text(tracking=True)
    active = fields.Boolean(default=True)
    allow_delegation = fields.Boolean(default=False)

    _sql_constraints = [
        ('unique_user', 'unique(user_id)', 'An agent already exists for this user!')
    ]

    def _to_crewai_agent(self):
        return Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            allow_delegation=self.allow_delegation,
            llm=LLM(temperature=0.5, model=self.llm_model_id.name, api_key=self.llm_provider_id.api_key, base_url=self.llm_provider_id.api_base)
        )
