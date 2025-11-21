/** @odoo-module **/

import { registerMessagingComponent } from "@mail/utils/messaging_component";
import { useModels } from "@mail/component_hooks/use_models";
const { Component } = owl;

export class LLMChatSidebar extends Component {
  setup() {
    useModels();
    super.setup();
    console.log("[LLMChatSidebar] setup - llmChatView:", this.llmChatView);
    console.log("[LLMChatSidebar] setup - llmChatView.isSmall:", this.llmChatView.isSmall);
    console.log("[LLMChatSidebar] setup - llmChatView.isThreadListVisible:", this.llmChatView.isThreadListVisible);
    console.log("[LLMChatSidebar] setup - llmChatView.isSidebarCollapsed:", this.llmChatView.isSidebarCollapsed);
  }

  /**
   * @returns {LLMChatView}
   */
  get llmChatView() {
    const record = this.props.record;
    console.log("[LLMChatSidebar] get llmChatView - isSmall:", record.isSmall, "isThreadListVisible:", record.isThreadListVisible);
    return record;
  }

  /**
   * Handle backdrop click to close sidebar on mobile
   */
  _onBackdropClick() {
    if (this.llmChatView.isSmall) {
      this.llmChatView.update({ isThreadListVisible: false });
    }
  }

  /**
   * Toggle sidebar collapsed state (desktop only)
   */
  _onClickToggleSidebar() {
    this.llmChatView.toggleSidebar();
  }

  /**
   * Handle click on New Chat button
   */
  async _onClickNewChat() {
    const llmChat = this.llmChatView.llmChat;

    // If in chatter mode, create thread for the record
    if (llmChat.isChatterMode) {
      const name = `New Chat ${new Date().toLocaleString()}`;
      const thread = await llmChat.createThread({
        name,
        relatedThreadModel: llmChat.relatedThreadModel,
        relatedThreadId: llmChat.relatedThreadId,
      });

      if (thread) {
        llmChat.update({ activeThread: thread });

        // Close sidebar on mobile/aside
        if (this.llmChatView.isSmall) {
          this.llmChatView.update({ isThreadListVisible: false });
        }
      }
    } else {
      // Standalone mode - existing behavior
      await llmChat.createNewThread();
      if (this.llmChatView.isSmall) {
        this.llmChatView.update({ isThreadListVisible: false });
      }
    }
  }
}

Object.assign(LLMChatSidebar, {
  props: { record: Object },
  template: "llm_thread.LLMChatSidebar",
});

registerMessagingComponent(LLMChatSidebar);
