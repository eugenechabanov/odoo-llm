/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { Composer } from "@mail/core/common/composer";
import {
  DictationRecorder,
  isDictationSupported,
} from "@llm_thread/components/llm_dictation/llm_dictation";
import { onWillDestroy, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

/**
 * Patch Composer to handle LLM threads
 * IMPORTANT: Only affects behavior when dealing with llm.thread model
 * All other mail functionality remains unchanged
 */
patch(Composer.prototype, {
  setup() {
    super.setup();

    // Initialize LLM store in setup - wrap with useState for reactivity (like Odoo does)
    try {
      this.llmStore = useState(useService("llm.store"));
    } catch (error) {
      // LLM service might not be available, that's ok
      console.warn("LLM store service not available:", error.message);
      this.llmStore = null;
    }

    this.notification = useService("notification");
    this.dictation = useState({ recording: false, transcribing: false });
    this.dictationRecorder = new DictationRecorder();
    onWillDestroy(() => this.dictationRecorder.cancel());
  },

  /**
   * Show the mic only on LLM threads, and only where the browser can record.
   */
  get showDictation() {
    return this.isLLMThread && isDictationSupported();
  },

  get dictationTitle() {
    if (this.dictation.transcribing) {
      return _t("Transcribing...");
    }
    return this.dictation.recording
      ? _t("Stop recording")
      : _t("Dictate a message");
  },

  /**
   * Toggle dictation: record, then drop the transcript into the composer for
   * the user to check before sending. Nothing is ever sent automatically.
   */
  async onClickDictate() {
    if (this.dictation.transcribing) {
      return;
    }

    if (!this.dictation.recording) {
      try {
        await this.dictationRecorder.start();
        this.dictation.recording = true;
      } catch (error) {
        this.notification.add(error.message, { type: "danger" });
      }
      return;
    }

    this.dictation.recording = false;
    this.dictation.transcribing = true;
    try {
      const wav = await this.dictationRecorder.stop();
      if (!wav) {
        this.notification.add(_t("Nothing was recorded."), { type: "warning" });
        return;
      }
      const text = await this.transcribeDictation(wav);
      if (text) {
        this.insertDictatedText(text);
      } else {
        this.notification.add(_t("No speech was recognised."), {
          type: "warning",
        });
      }
    } catch (error) {
      this.notification.add(
        error.message || _t("Could not transcribe the recording."),
        { type: "danger" }
      );
    } finally {
      this.dictation.transcribing = false;
    }
  },

  /**
   * Send the recording to the server and return the transcript.
   */
  async transcribeDictation(wav) {
    const threadId = this.props.composer.thread.id;
    const formData = new FormData();
    formData.append("csrf_token", odoo.csrf_token);
    formData.append("audio", wav, "dictation.wav");

    const response = await fetch(`/llm/thread/${threadId}/transcribe`, {
      method: "POST",
      body: formData,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.error) {
      throw new Error(payload.error || _t("Could not transcribe the recording."));
    }
    return (payload.text || "").trim();
  },

  /**
   * Append the transcript to whatever is already typed, so dictation adds to
   * a message instead of wiping it.
   */
  insertDictatedText(text) {
    const composer = this.props.composer;
    const existing = composer.text || "";
    composer.text = existing
      ? `${existing.replace(/\s*$/, "")} ${text}`
      : text;
    composer.autofocus++;
  },

  /**
   * Check if current thread is an LLM thread
   * This is our safety check to ensure we only modify LLM-related behavior
   */
  get isLLMThread() {
    return this.props.composer?.thread?.model === "llm.thread";
  },

  /**
   * Check if this LLM thread is currently streaming
   */
  get isStreaming() {
    // Normal mail threads are never "streaming"
    if (!this.isLLMThread || !this.llmStore) {
      return false;
    }
    return this.llmStore.getStreamingStatus() || false;
  },

  get showStop() {
    if (this.isLLMThread) {
      return this.isStreaming;
    }

    return false;
  },

  async sendMessage() {
    if (this.isLLMThread && this.llmStore) {
      const content = this.props.composer.text?.trim();
      const attachments = this.props.composer.attachments || [];
      const attachmentIds = attachments.map((att) => att.id);

      if (!content && attachmentIds.length === 0) {
        return;
      }

      const threadId = this.props.composer.thread.id;

      this.props.composer.clear();

      await this.llmStore.sendLLMMessage(threadId, content, attachmentIds);
      return;
    }

    return super.sendMessage();
  },

  /**
   * Override onKeydown to handle LLM-specific shortcuts
   * @param {KeyboardEvent} ev - Keyboard event
   */
  onKeydown(ev) {
    // LLM-specific handling
    if (this.isLLMThread) {
      switch (ev.key) {
        case "Enter":
          // For LLM threads, always send on Enter (no Shift+Enter for newline)
          if (!ev.shiftKey && !this.isStreaming) {
            ev.preventDefault();
            this.sendMessage();
            return;
          }
          break;
        case "Escape":
          // Stop streaming if ESC is pressed
          if (this.isStreaming) {
            ev.preventDefault();
            this.stopStreaming();
            return;
          }
          break;
      }
    }

    // For all other cases (including non-LLM threads), use original behavior
    super.onKeydown(ev);
  },

  /**
   * Stop LLM streaming (only relevant for LLM threads)
   */
  stopStreaming() {
    if (this.isLLMThread && this.llmStore) {
      const threadId = this.props.composer.thread.id;
      this.llmStore.stopStreaming(threadId);
    }
  },

  /**
   * Override placeholder for LLM threads
   */
  get placeholder() {
    if (this.isLLMThread) {
      return this.isStreaming
        ? _t("AI is responding...")
        : _t("Ask anything...");
    }

    // Use original placeholder for regular mail
    return super.placeholder || _t("Write a message...");
  },

  /**
   * Hide composer avatar/sidebar for LLM threads
   * This removes the empty 42px column on the left
   */
  get showComposerAvatar() {
    if (this.isLLMThread) {
      return false;
    }

    // Use original logic for regular mail
    return super.showComposerAvatar;
  },

  /**
   * Disable composer while streaming (LLM only)
   */
  get isDisabled() {
    if (this.isLLMThread) {
      return this.isStreaming || !this.props.composer.text?.trim();
    }

    // Use original disabled logic for regular mail
    return super.isDisabled;
  },
});
