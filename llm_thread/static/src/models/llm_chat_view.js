/** @odoo-module **/
import { attr, one } from "@mail/model/model_field";
import { clear } from "@mail/model/model_field_command";
import { registerModel } from "@mail/model/model_core";

registerModel({
  name: "LLMChatView",
  lifecycleHooks: {
    _created() {
      // Initialize thread list visibility and collapse state
      const isSmall = this._isSmall();
      const isChatterMode = Boolean(this.llmChat.isChatterMode);

      console.log("[LLMChatView] _created - isSmall:", isSmall, "isChatterMode:", isChatterMode);

      this.update({
        // Set isSmall as stored value (not computed)
        isSmall: isSmall,
        // Thread list visibility:
        // - Desktop (!isSmall): always visible
        // - Mobile/Aside (isSmall): hidden by default, toggled by hamburger
        isThreadListVisible: !isSmall,
        // Desktop: collapse state (default collapsed in chatter, expanded standalone)
        isSidebarCollapsed: isChatterMode,
      });
    },
  },
  recordMethods: {
    /**
     * @private
     */
    _onLLMChatActiveThreadChanged() {
      this.env.services.router.pushState({
        action: this.llmChat.llmChatView.actionId,
        active_id: this.llmChat.activeId,
      });
    },

    /**
     * Check if should use mobile/small layout
     * - On actual mobile devices (window < 768px)
     * - In chatter positioned on the side (narrow panel)
     *
     * @returns {Boolean}
     * @private
     */
    _isSmall() {
      const isActuallySmall = this.messaging.device.isSmall;

      // Check if in chatter aside mode (chatter in side panel)
      // When hasMessageListScrollAdjust is true, the chatter is on the form view's side
      const chatters = this.messaging.models.Chatter.all();
      const isChatterAside = chatters.some(
        (chatter) => chatter.hasMessageListScrollAdjust
      );

      const result = isActuallySmall || isChatterAside;

      console.log("[LLMChatView] _isSmall() check:", {
        isActuallySmall,
        isChatterAside,
        chatterCount: chatters.length,
        chattersWithScrollAdjust: chatters.filter(c => c.hasMessageListScrollAdjust).length,
        result,
      });

      return result;
    },

    /**
     * Toggle sidebar collapsed state (desktop only)
     */
    toggleSidebar() {
      this.update({ isSidebarCollapsed: !this.isSidebarCollapsed });
    },
  },
  fields: {
    actionId: attr(),
    isThreadListVisible: attr({
      default: true,
    }),
    isSidebarCollapsed: attr({
      default: false,
    }),
    isSmall: attr({
      default: false,
    }),
    llmChat: one("LLMChat", {
      inverse: "llmChatView",
      required: true,
    }),
    isActive: attr({
      compute() {
        return Boolean(this.llmChat);
      },
    }),
    thread: one("Thread", {
      compute() {
        return this.llmChat.activeThread;
      },
    }),
    threadViewer: one("ThreadViewer", {
      compute() {
        if (!this.llmChat.activeThread) {
          return clear();
        }
        return {
          hasThreadView: true,
          thread: this.llmChat.activeThread,
          threadCache: this.llmChat.threadCache,
        };
      },
    }),
    threadView: one("ThreadView", {
      compute() {
        if (!this.threadViewer) {
          return clear();
        }
        return {
          threadViewer: this.threadViewer,
          messageListView: {},
          llmChatThreadHeaderView: {},
        };
      },
    }),
    composer: one("Composer", {
      compute() {
        if (!this.threadViewer) {
          return clear();
        }
        return { thread: this.threadViewer.thread };
      },
    }),
  },
  onChanges: [
    {
      dependencies: ["llmChat.activeThread"],
      methodName: "_onLLMChatActiveThreadChanged",
    },
  ],
});
