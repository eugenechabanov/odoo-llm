import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

class OnboardingStep(models.Model):
    _inherit = 'onboarding.onboarding.step'

    # --- Helper method to find and mark progress step ---
    def _find_and_mark_progress_step_done(self, step_xml_id):
        """
        Finds the relevant onboarding.progress.step record and marks it done.
        Called from @api.model methods where 'self' is the model class.
        """
        onboarding_panel_id = self.env.ref('llm.onboarding_llm_provider_panel', raise_if_not_found=False)
        onboarding_step_id = self.env.ref(step_xml_id, raise_if_not_found=False)

        if not onboarding_panel_id or not onboarding_step_id:
            _logger.warning(f"Could not find onboarding panel or step ref '{step_xml_id}' for marking step done.")
            return

        # Find the progress record for this onboarding and current company
        # Use _search_or_create_progress to ensure it exists
        onboarding_record = self.env['onboarding.onboarding'].browse(onboarding_panel_id.id)
        progress_record = onboarding_record._search_or_create_progress() # Gets/Creates for current company

        if not progress_record:
             _logger.warning(f"Could not find or create progress record for onboarding {onboarding_panel_id.id} and company {self.env.company.id}")
             return

        # Find or create the specific progress step record
        progress_step = self.env['onboarding.progress.step'].search([
            ('progress_id', '=', progress_record.id),
            ('step_id', '=', onboarding_step_id.id),
        ], limit=1)

        if not progress_step:
            try:
                progress_step = self.env['onboarding.progress.step'].create({
                    'progress_id': progress_record.id,
                    'step_id': onboarding_step_id.id,
                    'onboarding_id': onboarding_panel_id.id,
                })
                _logger.info(f"Created new progress_step {progress_step.id} for step {step_xml_id}")
            except Exception as e:
                _logger.error(f"Failed to create progress step for step {step_xml_id}: {e}")
                return # Cannot proceed without a progress_step record

        # Mark as done
        _logger.info(f"Attempting to mark progress_step {progress_step.id} (step {step_xml_id}) as just_done.")
        progress_step.action_set_just_done()


    # --- Decorated Methods ---

    @api.model
    def action_llm_open_provider_form(self, **kwargs):
        _logger.info(f"Executing @api.model action_llm_open_provider_form with kwargs: {kwargs}")
        # Mark corresponding step done
        self._find_and_mark_progress_step_done('llm.onboarding_llm_step_create_provider')
        # Execute the original action
        server_action = self.env.ref('llm.action_open_llm_provider_form')
        action_vals = server_action.sudo().run()
        return action_vals

    @api.model
    def action_llm_launch_fetch_models_tour(self, **kwargs):
        _logger.info(f"Executing @api.model action_llm_launch_fetch_models_tour with kwargs: {kwargs}")
        # Mark corresponding step done
        self._find_and_mark_progress_step_done('llm.onboarding_llm_step_fetch_models')
        # Execute the original action
        server_action = self.env.ref('llm.action_launch_fetch_models_tour')
        action_vals = server_action.sudo().run()
        return action_vals

    @api.model
    def action_llm_onboarding_step_done(self, **kwargs):
        _logger.info(f"Executing @api.model action_llm_onboarding_step_done with kwargs: {kwargs}")
        # Mark corresponding step done
        self._find_and_mark_progress_step_done('llm.onboarding_llm_step_done')
        # No further UI action needed for this specific step
        return False