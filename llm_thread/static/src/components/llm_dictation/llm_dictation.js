/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { browser } from "@web/core/browser/browser";

/**
 * Voice dictation recorder for the AI chat composer.
 *
 * Deliberately built on getUserMedia + MediaRecorder, which every current
 * browser supports (Firefox, Chrome, Edge, Safari). The Web Speech API would
 * have been less code but is Chrome/Edge only, so it is not an option here.
 *
 * Each browser hands back a different container (Firefox ogg/opus, Chrome
 * webm/opus, Safari mp4/aac). Rather than negotiate that with the server, we
 * decode whatever we got and re-encode it as 16 kHz mono 16-bit WAV, so the
 * backend always receives one known format.
 */

const TARGET_SAMPLE_RATE = 16000;

/** Preferred containers, best-supported first; undefined lets the browser pick. */
const PREFERRED_MIME_TYPES = [
    "audio/webm;codecs=opus",
    "audio/ogg;codecs=opus",
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
];

export function isDictationSupported() {
    return Boolean(
        browser.navigator?.mediaDevices?.getUserMedia &&
            typeof window.MediaRecorder !== "undefined"
    );
}

function pickMimeType() {
    if (typeof window.MediaRecorder?.isTypeSupported !== "function") {
        return undefined;
    }
    return PREFERRED_MIME_TYPES.find((type) =>
        window.MediaRecorder.isTypeSupported(type)
    );
}

/**
 * Encode raw mono PCM samples as a 16-bit WAV blob.
 *
 * @param {Float32Array} samples
 * @param {number} sampleRate
 * @returns {Blob}
 */
function encodeWav(samples, sampleRate) {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);
    const writeString = (offset, str) => {
        for (let i = 0; i < str.length; i++) {
            view.setUint8(offset + i, str.charCodeAt(i));
        }
    };

    writeString(0, "RIFF");
    view.setUint32(4, 36 + samples.length * 2, true);
    writeString(8, "WAVE");
    writeString(12, "fmt ");
    view.setUint32(16, 16, true); // PCM chunk size
    view.setUint16(20, 1, true); // PCM format
    view.setUint16(22, 1, true); // mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true); // byte rate
    view.setUint16(32, 2, true); // block align
    view.setUint16(34, 16, true); // bits per sample
    writeString(36, "data");
    view.setUint32(40, samples.length * 2, true);

    let offset = 44;
    for (const sample of samples) {
        const clamped = Math.max(-1, Math.min(1, sample));
        view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
        offset += 2;
    }
    return new Blob([view], { type: "audio/wav" });
}

/**
 * Decode a recorded blob and re-encode it as 16 kHz mono WAV.
 *
 * @param {Blob} blob
 * @returns {Promise<Blob>}
 */
async function toWav(blob) {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) {
        throw new Error("AudioContext unavailable");
    }
    const arrayBuffer = await blob.arrayBuffer();
    const decodeCtx = new AudioCtx();
    let decoded;
    try {
        decoded = await decodeCtx.decodeAudioData(arrayBuffer);
    } finally {
        decodeCtx.close();
    }

    // Resample to the rate speech-to-text actually wants, and collapse to mono.
    const frames = Math.ceil(decoded.duration * TARGET_SAMPLE_RATE);
    const OfflineCtx = window.OfflineAudioContext || window.webkitOfflineAudioContext;
    const offline = new OfflineCtx(1, frames, TARGET_SAMPLE_RATE);
    const source = offline.createBufferSource();
    source.buffer = decoded;
    source.connect(offline.destination);
    source.start();
    const rendered = await offline.startRendering();
    return encodeWav(rendered.getChannelData(0), TARGET_SAMPLE_RATE);
}

export class DictationRecorder {
    constructor() {
        this._recorder = null;
        this._stream = null;
        this._chunks = [];
    }

    get isRecording() {
        return Boolean(this._recorder) && this._recorder.state === "recording";
    }

    /**
     * Ask for the microphone and start recording.
     * Throws a translated message if permission is refused or unavailable.
     */
    async start() {
        let stream;
        try {
            stream = await browser.navigator.mediaDevices.getUserMedia({ audio: true });
        } catch (error) {
            if (error?.name === "NotAllowedError" || error?.name === "SecurityError") {
                throw new Error(
                    _t(
                        "Microphone access was blocked. Allow it for this site in your browser, then try again."
                    )
                );
            }
            if (error?.name === "NotFoundError") {
                throw new Error(_t("No microphone was found on this device."));
            }
            throw new Error(_t("Could not start recording: %s", error?.message || error));
        }

        this._stream = stream;
        this._chunks = [];
        const mimeType = pickMimeType();
        this._recorder = new window.MediaRecorder(stream, mimeType ? { mimeType } : {});
        this._recorder.addEventListener("dataavailable", (ev) => {
            if (ev.data?.size) {
                this._chunks.push(ev.data);
            }
        });
        this._recorder.start();
    }

    /**
     * Stop recording and return the audio as 16 kHz mono WAV.
     *
     * @returns {Promise<Blob|null>} null when nothing was captured
     */
    async stop() {
        if (!this._recorder) {
            return null;
        }
        const recorder = this._recorder;
        const stopped = new Promise((resolve) => {
            recorder.addEventListener("stop", resolve, { once: true });
        });
        if (recorder.state !== "inactive") {
            recorder.stop();
        }
        await stopped;
        this._releaseStream();
        this._recorder = null;

        if (!this._chunks.length) {
            return null;
        }
        const raw = new Blob(this._chunks, { type: recorder.mimeType || "audio/webm" });
        this._chunks = [];
        return toWav(raw);
    }

    /** Abandon a recording without transcribing it. */
    cancel() {
        if (this._recorder && this._recorder.state !== "inactive") {
            this._recorder.stop();
        }
        this._recorder = null;
        this._chunks = [];
        this._releaseStream();
    }

    _releaseStream() {
        // Release the mic so the browser's recording indicator goes away.
        this._stream?.getTracks().forEach((track) => track.stop());
        this._stream = null;
    }
}
