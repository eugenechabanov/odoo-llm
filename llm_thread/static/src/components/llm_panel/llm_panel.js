/** @odoo-module **/

import { Component, onWillDestroy, useRef, useState } from "@odoo/owl";
import { LLMChatContainer } from "@llm_thread/components/llm_chat_container/llm_chat_container";
import { useService } from "@web/core/utils/hooks";

/**
 * LLM Side Panel - persistent chat panel that slides in from the right.
 * Rendered at the WebClient level so it persists across action navigations.
 * Resizable via a drag handle on the left edge.
 */
export class LLMPanel extends Component {
    static components = { LLMChatContainer };
    static props = {};
    static template = "llm_thread.LLMPanel";

    setup() {
        this.panelService = useService("llm.panel");
        this.state = useState({ isOpen: false, width: 600 });
        this.panelRef = useRef("panel");
        this._onMouseMove = this._onMouseMove.bind(this);
        this._onMouseUp = this._onMouseUp.bind(this);


        const onToggle = (ev) => {
            this.state.isOpen = ev.detail.isOpen;
        };
        this.panelService.bus.addEventListener("toggle", onToggle);
        onWillDestroy(() => {
            this.panelService.bus.removeEventListener("toggle", onToggle);
            document.removeEventListener("mousemove", this._onMouseMove);
            document.removeEventListener("mouseup", this._onMouseUp);
        });
    }

    get isOpen() {
        return this.state.isOpen;
    }

    closePanel() {
        this.panelService.close();
    }

    onResizeStart(ev) {
        ev.preventDefault();
        this._resizing = true;
        document.body.style.cursor = "ew-resize";
        document.body.style.userSelect = "none";
        document.addEventListener("mousemove", this._onMouseMove);
        document.addEventListener("mouseup", this._onMouseUp);
    }

    _onMouseMove(ev) {
        if (!this._resizing) return;
        const newWidth = window.innerWidth - ev.clientX;
        this.state.width = Math.max(320, Math.min(newWidth, window.innerWidth * 0.8));
    }

    _onMouseUp() {
        this._resizing = false;
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        document.removeEventListener("mousemove", this._onMouseMove);
        document.removeEventListener("mouseup", this._onMouseUp);
    }
}
