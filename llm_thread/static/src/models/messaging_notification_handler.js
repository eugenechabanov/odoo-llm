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
      console.log("[DEBUG] Bus notification received, type:", message.type);

      if (message.type === "llm.thread/delete") {
        console.log("[DEBUG] Routing to _handleLLMThreadsDelete");
        return this._handleLLMThreadsDelete(message);
      }
      if (message.type === "llm.thread/open_in_chatter") {
        console.log("[DEBUG] Routing to _handleLLMThreadOpenInChatter");
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
      console.log("[DEBUG] llm.thread/open_in_chatter notification received:", message.payload);

      const { thread_id, model, res_id } = message.payload;

      // Validate payload
      if (!thread_id || !model || !res_id) {
        console.warn("[DEBUG] Invalid open_in_chatter payload:", message.payload);
        return;
      }

      console.log(`[DEBUG] Opening LLM thread ${thread_id} for ${model}:${res_id}`);

      // Ensure LLMChat exists
      let llmChat = this.messaging.llmChat;
      console.log("[DEBUG] LLMChat instance:", llmChat ? "exists" : "creating new");

      if (!llmChat) {
        this.messaging.update({ llmChat: { isInitThreadHandled: false } });
        llmChat = this.messaging.llmChat;
        console.log("[DEBUG] LLMChat created:", llmChat);
      }

      try {
        // Find the chatter for this specific record
        console.log(`[DEBUG] Looking for Chatter for ${model}:${res_id}`);
        let targetChatter = null;

        for (const chatter of this.messaging.models['Chatter'].all()) {
          console.log("[DEBUG] Checking chatter:", {
            hasThread: !!chatter.thread,
            threadModel: chatter.thread?.model,
            threadId: chatter.thread?.id,
          });

          if (chatter.thread && chatter.thread.model === model && chatter.thread.id === res_id) {
            console.log("[DEBUG] Found matching chatter!");
            targetChatter = chatter;
            break;
          }
        }

        if (!targetChatter) {
          throw new Error(
            `No chatter found for ${model}:${res_id}. Make sure the form view has a chatter.`
          );
        }

        console.log("[DEBUG] Target chatter found, current state:", {
          is_chatting_with_llm: targetChatter.is_chatting_with_llm,
        });

        // Toggle the LLM chat if not already open
        if (!targetChatter.is_chatting_with_llm) {
          console.log("[DEBUG] Calling toggleLLMChat()...");
          await targetChatter.toggleLLMChat();
          console.log("[DEBUG] toggleLLMChat() completed");
        } else {
          console.log("[DEBUG] LLM chat already open");
        }

        // Trigger auto-generation with prepended messages
        console.log("[DEBUG] Attempting to trigger auto-generation...");
        const composer = llmChat.llmChatView?.composer;
        if (composer) {
          console.log("[DEBUG] Composer found, calling startGeneration()...");
          try {
            await composer.startGeneration();
            console.log("[DEBUG] Auto-generation started successfully");
          } catch (genError) {
            console.error("[DEBUG] Error starting generation:", genError);
            // Don't fail the whole operation if generation fails
          }
        } else {
          console.warn("[DEBUG] No composer found for auto-generation");
        }

        // Success notification
        this.messaging.notify({
          message: `AI Chat opened for ${model} #${res_id}`,
          type: "info",
        });

        console.log("[DEBUG] Successfully opened LLM thread in chatter");
      } catch (error) {
        console.error("[DEBUG] Error opening LLM thread in chatter:", error);
        console.error("[DEBUG] Error stack:", error.stack);
        this.messaging.notify({
          title: "Error Opening AI Chat",
          message: error.message || "An unexpected error occurred",
          type: "danger",
        });
      }
    },
  },
});
