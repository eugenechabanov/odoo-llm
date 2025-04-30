odoo.define('llm.tours', ['web.core', 'web_tour.tour', 'web.Dialog'], function(require) {
    "use strict";

    var core = require('web.core');
    var tour = require('web_tour.tour');
    var Dialog = require('web.Dialog');
    var _t = core._t;
    
    // Helper function to check if provider modules are installed
    function checkProviderModulesInstalled() {
        return new Promise(function(resolve) {
            $.ajax({
                url: '/llm/check_providers',
                type: 'GET',
                dataType: 'json',
                success: function(data) {
                    resolve(data && data.has_providers);
                },
                error: function() {
                    console.error("Error checking for provider modules");
                    resolve(false);
                }
            });
        });
    }
    
    // Function to show provider modules required dialog
    function showProviderModulesRequiredDialog() {
        new Dialog(null, {
            title: _t("Provider Modules Required"),
            $content: $('<div>').html(
                _t("<p>No AI service providers are available.</p>" +
                   "<p>You need to install at least one provider module such as:</p>" +
                   "<ul>" +
                   "<li><strong>llm_openai</strong> - For OpenAI integration</li>" +
                   "<li><strong>llm_ollama</strong> - For local Ollama integration</li>" +
                   "<li><strong>llm_anthropic</strong> - For Anthropic Claude integration</li>" +
                   "</ul>" +
                   "<p>Please install one of these modules from the Apps menu and try again.</p>")
            ),
            buttons: [{
                text: _t("Go to Apps"),
                classes: 'btn-primary',
                click: function () {
                    window.location.href = '/web#action=base.open_module_tree';
                    this.close();
                }
            }, {
                text: _t("Close"),
                close: true
            }]
        }).open();
    }
    
    // Provider Setup Tour
    tour.register('fetch_models_tour', {
        url: "/web",
        sequence: 250,
        wait_for: Promise.resolve().then(function() {
            // Check if any provider modules are installed before starting the tour
            return checkProviderModulesInstalled().then(function(hasProviders) {
                if (!hasProviders) {
                    // If no providers are installed, show dialog and don't start the tour
                    showProviderModulesRequiredDialog();
                    return new Promise(function() {}); // Never resolve to prevent tour from starting
                }
                return Promise.resolve(); // Continue with tour
            });
        }),
        rainbowMan: true,
        rainbowManMessage: _t("Congratulations! You've successfully set up your first AI provider."),
    }, [
        ...tour.stepUtils.goToAppSteps('llm.menu_llm_root', _t('Set up your AI capabilities with the <b>LLM App</b>')),
        {
            trigger: '.o-kanban-button-new, .o_list_button_add, button[data-menu-xmlid="llm.menu_llm_provider_action"]',
            content: _t('Click here to create a new AI provider configuration.'),
            position: 'bottom',
        },
        {
            trigger: ".o_form_sheet .oe_title input#name",
            content: _t("Give your provider a descriptive name (e.g., 'OpenAI', 'Ollama Local', 'Anthropic')."),
            position: 'bottom',
        },
        {
            trigger: 'div[name="service"] select, select#service',
            content: _t("Select which AI service you want to connect to."),
            position: 'bottom',
            run: function (actions) {
                console.log("Service select element:", this.$anchor);
                actions.click(this.$anchor);
            },
        },
        {
            trigger: 'select#service option:not([value="false"]), div.dropdown-menu .dropdown-item',
            auto: true,
            position: 'bottom',
            run: function (actions) {
                console.log("Service options:", this.$anchor);
                actions.click(this.$anchor);
            },
        },
        {
            trigger: 'div[name="api_key"] input, input#api_key',
            content: _t("Enter your API key. This is required for most providers like OpenAI or Anthropic."),
            position: 'right',
        },
        {
            trigger: 'div[name="api_base"] input, input#api_base',
            content: _t("For some providers like Ollama, you may need to specify the API base URL (e.g., 'http://localhost:11434')."),
            position: 'right',
            run: function (actions) {
                // This field might be optional depending on the provider
                actions.text("", this.$anchor);
            },
        },
        {
            trigger: '.o_form_button_save',
            content: _t("Save your provider configuration before fetching models."),
            position: 'bottom',
        },
        {
            trigger: '.o_statusbar_buttons button.btn-primary:contains("Fetch Models")',
            content: _t("<b>Crucial step:</b> Click <b>Fetch Models</b> to import compatible AI models from the provider."),
            position: 'bottom',
        },
        {
            trigger: 'div[name="model_ids"] .o_data_row',
            content: _t("Great! Models have been fetched. You can now use this provider with your LLM features."),
            position: 'bottom',
            run: function () {
                // Just show the message, no action needed
            },
        }
    ]);

    // --- Client Action Handler ---
    function runLlmTour(parent, action) {
        const tourName = action.params.tour_name;
        if (tourName) {
            console.log(`Client Action: Running tour '${tourName}'`);
            tour.run(tourName);
            return Promise.resolve();
        } else {
            console.error("Tour name not provided in action parameters for tag 'llm_run_tour'");
            return Promise.reject("Tour name missing");
        }
    }

    // Register this handler function using core's registry
    core.action_registry.add('llm_run_tour', runLlmTour);

});