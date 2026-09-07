/** @odoo-module **/

import { Component, onWillDestroy, useRef, useState } from "@odoo/owl";
import { LLMChatContainer } from "@llm_thread/components/llm_chat_container/llm_chat_container";
import { browser } from "@web/core/browser/browser";
import { useService } from "@web/core/utils/hooks";

const PANEL_MIN_WIDTH = 320;
const PANEL_DEFAULT_WIDTH = 1200;
const PANEL_WIDTH_STORAGE_KEY = "llm_thread.panelWidth";

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
        this.state = useState({ isOpen: false, width: this._initialWidth() });
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

    /**
     * Keep the panel between the minimum and 80% of the viewport, so it can
     * never be dragged (or restored) to a size that clips its own toolbar.
     */
    _clampWidth(width) {
        return Math.max(
            PANEL_MIN_WIDTH,
            Math.min(width, window.innerWidth * 0.8)
        );
    }

    /**
     * Restore the width the user last dragged to, falling back to the default.
     */
    _initialWidth() {
        const stored = parseInt(
            browser.localStorage.getItem(PANEL_WIDTH_STORAGE_KEY),
            10
        );
        return this._clampWidth(
            Number.isNaN(stored) ? PANEL_DEFAULT_WIDTH : stored
        );
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
        this.state.width = this._clampWidth(window.innerWidth - ev.clientX);
    }

    _onMouseUp() {
        if (this._resizing) {
            browser.localStorage.setItem(
                PANEL_WIDTH_STORAGE_KEY,
                String(Math.round(this.state.width))
            );
        }
        this._resizing = false;
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        document.removeEventListener("mousemove", this._onMouseMove);
        document.removeEventListener("mouseup", this._onMouseUp);
    }
}
