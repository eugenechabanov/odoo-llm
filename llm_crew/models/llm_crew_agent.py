from odoo import models, fields, api, _
from odoo.exceptions import UserError

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

    _sql_constraints = [
        ('unique_user', 'unique(user_id)', 'An agent already exists for this user!')
    ]

    def _to_crewai_agent(self):
        from crewai import Agent
        return Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            llm=self.llm_provider_id._get_llm()
        )
