odoo.define('llm.tours', ['web.core', 'web_tour.tour'], function(require) {
    "use strict";

    var core = require('web.core');
    var tour = require('web_tour.tour'); // Import the tour manager
    var _t = core._t;
    
    // --- Your existing Tour Definition ---
    tour.register('fetch_models_tour', {
        url: "/web",
        sequence: 250,
    }, [...tour.stepUtils.goToAppSteps('llm.menu_llm_root', _t('Set up LLM providers and knowledge base with <br>LLM App</br>')),
        {
            trigger: ".o_form_sheet .oe_title input#name",
            content: _t("You should be on the Provider configuration form."),
            position: 'bottom',
        },
        {
            trigger: '.o_statusbar_buttons button.btn-primary:contains("Fetch Models")',
            content: _t("<b>Crucial step:</b> After saving provider details, click <b>Fetch Models</b> to import compatible AI models."),
            position: 'bottom',
        },
    ]);


    // --- NEW: Client Action Handler ---
    // Define a function to handle the client action
    function runLlmTour(parent, action) { // Standard signature often includes parent
        // Extract the tour name from the action parameters
        const tourName = action.params.tour_name;
        if (tourName) {
            // Use the tour manager (imported as 'tour') to run the tour
            console.log(`Client Action: Running tour '${tourName}'`); // Add log
            tour.run(tourName);
            // Standard client actions should return a Promise
            return Promise.resolve();
        } else {
            console.error("Tour name not provided in action parameters for tag 'llm_run_tour'");
            return Promise.reject("Tour name missing");
        }
    }

    // Register this handler function using core's registry
    core.action_registry.add('llm_run_tour', runLlmTour);

});