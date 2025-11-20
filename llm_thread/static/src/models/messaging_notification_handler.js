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
      const { thread_id, model, res_id } = message.payload;

      // Validate payload
      if (!thread_id || !model || !res_id) {
        return;
      }

      // Ensure LLMChat exists
      let llmChat = this.messaging.llmChat;

      if (!llmChat) {
        this.messaging.update({ llmChat: { isInitThreadHandled: false } });
        llmChat = this.messaging.llmChat;
      }

      try {
        // Find the chatter for this specific record
        let targetChatter = null;

        for (const chatter of this.messaging.models['Chatter'].all()) {
          if (chatter.thread && chatter.thread.model === model && chatter.thread.id === res_id) {
            targetChatter = chatter;
            break;
          }
        }

        if (!targetChatter) {
          throw new Error(
            `No chatter found for ${model}:${res_id}. Make sure the form view has a chatter.`
          );
        }

        // Toggle the LLM chat if not already open
        if (!targetChatter.is_chatting_with_llm) {
          await targetChatter.toggleLLMChat();
        }

        // Trigger auto-generation with prepended messages
        const composer = llmChat.llmChatView?.composer;
        if (composer) {
          try {
            await composer.startGeneration();
          } catch (genError) {
            // Don't fail the whole operation if generation fails
            console.error("Error starting generation:", genError);
          }
        }

        // Success notification
        this.messaging.notify({
          message: `AI Chat opened for ${model} #${res_id}`,
          type: "info",
        });
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
