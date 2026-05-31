/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * AI Chat Systray Button - sits in the top navigation bar.
 * Toggles a persistent side panel with the LLM chat.
 */
export class LLMSystray extends Component {
    static props = [];
    static template = "llm_thread.LLMSystray";

    setup() {
        this.panelService = useService("llm.panel");
        this.state = useState({ isOpen: false });
    }

    togglePanel() {
        this.panelService.toggle();
        this.state.isOpen = this.panelService.isOpen;
    }

    get isOpen() {
        return this.state.isOpen;
    }
}

registry
    .category("systray")
    .add("llm_thread.AIChatMenu", { Component: LLMSystray }, { sequence: 90 });
