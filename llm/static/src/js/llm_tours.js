odoo.define('llm.tours', ['web.core', 'web_tour.tour', 'web.Dialog'], function(require) {
    "use strict";

    var core = require('web.core');
    var tour = require('web_tour.tour');
    var _t = core._t;
    
    // Provider Setup Tour
    tour.register('fetch_models_tour', {
        url: "/web",
        sequence: 250,
        test: false,
        rainbowMan: true,
        rainbowManMessage: _t("Congratulations! You've successfully set up your first AI provider."),
    }, [
        ...tour.stepUtils.goToAppSteps('llm.menu_llm_root', _t('Set up your AI capabilities with the <b>LLM App</b>')),
        {
            trigger: '.o-kanban-button-new, .o_list_button_add, button[data-menu-xmlid="llm.menu_llm_provider_action"]',
            content: _t('Click here to create a new AI provider configuration.'),
            position: 'bottom',
            auto: false,
        },
        {
            trigger: ".o_form_sheet .oe_title input#name",
            content: _t("Give your provider a descriptive name (e.g., 'OpenAI', 'Ollama Local', 'Anthropic')."),
            position: 'bottom',
            auto: false,
        },
        {
            trigger: 'div[name="service"] select, select#service',
            content: _t("Select which AI service you want to connect to."),
            position: 'bottom',
            auto: false,
        },
        {
            trigger: 'div[name="api_key"] input, input#api_key',
            content: _t("Enter your API key. This is required for most providers like OpenAI or Anthropic."),
            position: 'right',
            auto: false,
        },
        {
            trigger: 'div[name="api_base"] input, input#api_base',
            content: _t("For some providers like Ollama, you may need to specify the API base URL (e.g., 'http://localhost:11434')."),
            position: 'right',
            auto: false,
        },
        {
            trigger: '.o_form_button_save',
            content: _t("Save your provider configuration before fetching models."),
            position: 'bottom',
            auto: false,
        },
        {
            trigger: '.o_statusbar_buttons button.btn-primary:contains("Fetch Models")',
            content: _t("<b>Crucial step:</b> Click <b>Fetch Models</b> to import compatible AI models from the provider."),
            position: 'bottom',
            auto: false,
        },
        {
            trigger: 'div[name="model_ids"] .o_data_row',
            content: _t("Great! Models have been fetched. You can now use this provider with your LLM features."),
            position: 'bottom',
            auto: false,
        }
    ]);

    // --- Client Action Handler ---
    function runLlmTour(parent, action) {
        const tourName = action.params.tour_name;
        const mode = action.params.mode || 'test';
        
        if (tourName) {
            console.log(`Client Action: Running tour '${tourName}' in ${mode} mode`);
            
            if (mode === 'onboarding') {
                // Interactive mode - user needs to click through each step
                tour.reset(tourName);
            } else {
                // Test mode - automatically runs through steps
                tour.run(tourName);
            }
            
            return Promise.resolve();
        } else {
            console.error("Tour name not provided in action parameters for tag 'llm_run_tour'");
            return Promise.reject("Tour name missing");
        }
    }

    // Register this handler function using core's registry
    core.action_registry.add('llm_run_tour', runLlmTour);

});