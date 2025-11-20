/** @odoo-module **/

import { clear } from "@mail/model/model_field_command";
import { registerPatch } from "@mail/model/model_core";

registerPatch({
  name: "MessagingNotificationHandler",
  recordMethods: {
    /**
     * @override
     * @private
     * @param {Object} message
     */
    _handleNotification(message) {
      if (message.type === "llm.thread/delete") {
        return this._handleLLMThreadsDelete(message);
      }
      if (message.type === "llm.thread/open_in_chatter") {
        return this._handleLLMThreadOpenInChatter(message);
      }
      super._handleNotification(message);
    },

    _handleLLMThreadsDelete(message) {
      const ids = message.payload.ids;
      for (const id of ids) {
        this._handleLLMThreadDelete(id);
      }
    },

    /**
     * @private
     * @param {Number} id
     */
    _handleLLMThreadDelete(id) {
      const thread = this.messaging.models.Thread.findFromIdentifyingData({
        id,
        model: "llm.thread",
      });
      if (thread) {
        const llmChat = thread.llmChat;
        if (llmChat) {
          const isActiveThread =
            llmChat.activeThread && llmChat.activeThread.id === thread.id;
          if (isActiveThread) {
            const composer = llmChat.llmChatView?.composer;
            if (composer && composer.isStreaming) {
              composer._closeEventSource();
            }
          }
          const updatedData = {
            threads: llmChat.threads.filter((t) => t.id !== thread.id),
          };
          if (isActiveThread) {
            updatedData.activeThread = clear();
          }
          llmChat.update(updatedData);
        }
        thread.delete();
      }
    },

    /**
     * Handle opening an LLM thread in the chatter
     * Triggered when backend action_open_llm_assistant sends notification
     * @private
     * @param {Object} message
     * @param {Number} message.payload.thread_id - ID of llm.thread to open
     * @param {String} message.payload.model - Model name of related document
     * @param {Number} message.payload.res_id - ID of related document
     */
    async _handleLLMThreadOpenInChatter(message) {
      const { thread_id } = message.payload;

      // Validate payload
      if (!thread_id) {
        return;
      }

      try {
        // Find or fetch the thread
        let thread = this.messaging.models.Thread.findFromIdentifyingData({
          id: thread_id,
          model: "llm.thread",
        });

        if (!thread) {
          // Thread doesn't exist in frontend yet, fetch it from server
          const threadData = await this.messaging.rpc({
            model: "llm.thread",
            method: "read",
            args: [[thread_id], ["name", "model", "res_id"]],
          });

          if (threadData && threadData.length > 0) {
            thread = this.messaging.models.Thread.insert({
              id: thread_id,
              model: "llm.thread",
              name: threadData[0].name,
              relatedThreadModel: threadData[0].model,
              relatedThreadId: threadData[0].res_id,
              llmChat: this.messaging.llmChat,
            });
          }
        }

        if (!thread) {
          console.error("Could not find/create thread", thread_id);
          return;
        }

        // Use the unified Odoo pattern to open the thread
        await thread.openLLMThread({ focus: true });

        // Auto-trigger generation (if needed)
        const llmChat = this.messaging.llmChat;
        if (llmChat?.llmChatView?.composer) {
          await llmChat.llmChatView.composer.startGeneration();
        }
      } catch (error) {
        console.error("Error opening LLM thread in chatter:", error);
        this.messaging.notify({
          title: "Error Opening AI Chat",
          message: error.message || "An unexpected error occurred",
          type: "danger",
        });
      }
    },
  },
});
