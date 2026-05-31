/** @odoo-module **/

import { EventBus, reactive } from "@odoo/owl";
import { registry } from "@web/core/registry";

/**
 * LLM Panel Service - manages the open/close state of the AI chat side panel.
 * Uses a reactive state + event bus for cross-component communication.
 */
const llmPanelService = {
    start() {
        const bus = new EventBus();
        const state = reactive({
            isOpen: false,
        });

        return {
            bus,
            get isOpen() {
                return state.isOpen;
            },
            toggle() {
                state.isOpen = !state.isOpen;
                bus.trigger("toggle", { isOpen: state.isOpen });
            },
            open() {
                state.isOpen = true;
                bus.trigger("toggle", { isOpen: true });
            },
            close() {
                state.isOpen = false;
                bus.trigger("toggle", { isOpen: false });
            },
        };
    },
};

registry.category("services").add("llm.panel", llmPanelService);
