/** @odoo-module **/

import { LLMPanel } from "./llm_panel";
import { registry } from "@web/core/registry";

// Register LLMPanel as a main component so it persists across navigations.
// MainComponentsContainer renders these at the WebClient root level.
registry.category("main_components").add("llm_thread.LLMPanel", {
    Component: LLMPanel,
});
