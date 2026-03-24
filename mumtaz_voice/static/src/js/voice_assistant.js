/** @odoo-module **/

import { Component, useState, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

class VoiceAssistantAction extends Component {
    static template = "mumtaz_voice.VoiceAssistantAction";

    setup() {
        this.notification = useService("notification");

        this.state = useState({
            isListening: false,
            isProcessing: false,
            isSpeaking: false,
            transcript: "",
            response: "",
            intent: "",
            sessionId: null,
            error: "",
            history: [],
            browserSupported: !!(window.SpeechRecognition || window.webkitSpeechRecognition),
        });

        this.recognition = null;
        this.synthesis = window.speechSynthesis || null;
        this._initRecognition();

        onWillUnmount(() => {
            if (this.recognition) this.recognition.abort();
            if (this.synthesis) this.synthesis.cancel();
        });
    }

    _initRecognition() {
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) return;
        this.recognition = new SR();
        this.recognition.continuous = false;
        this.recognition.interimResults = true;
        this.recognition.lang = "en-US";

        this.recognition.onresult = (event) => {
            let text = "";
            for (const result of event.results) text += result[0].transcript;
            this.state.transcript = text;
        };
        this.recognition.onend = () => {
            this.state.isListening = false;
            if (this.state.transcript.trim()) this._processQuery();
        };
        this.recognition.onerror = (e) => {
            this.state.isListening = false;
            if (e.error !== "aborted")
                this.state.error = `Microphone error: "${e.error}". Please check browser permissions or type your question.`;
        };
    }

    toggleMic() {
        if (!this.state.browserSupported) {
            this.notification.add("Voice input requires Chrome or Edge. Please type your question.", { type: "warning" });
            return;
        }
        if (this.state.isListening) {
            this.recognition.stop();
            this.state.isListening = false;
        } else {
            this.state.transcript = "";
            this.state.response = "";
            this.state.error = "";
            this.state.isListening = true;
            try { this.recognition.start(); }
            catch { this.state.isListening = false; this.state.error = "Could not start microphone. Check browser permissions."; }
        }
    }

    async submitTyped() {
        if (!this.state.transcript.trim() || this.state.isProcessing) return;
        await this._processQuery();
    }

    async _processQuery() {
        const question = this.state.transcript.trim();
        if (!question) return;
        this.state.isProcessing = true;
        this.state.error = "";
        this.state.response = "";
        try {
            const result = await rpc("/mumtaz/voice/query", { transcript: question, session_id: this.state.sessionId });
            if (result.error) { this.state.error = result.error; return; }
            const answer = result.response || "No response received.";
            this.state.response = answer;
            this.state.intent = result.intent || "";
            this.state.sessionId = result.session_id;
            this.state.history = [...this.state.history, {
                question, response: answer, intent: result.intent || "",
                time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            }];
            this.state.transcript = "";
            this._speak(answer);
        } catch (err) {
            this.state.error = `Request failed: ${err.message || "Unknown error."}`;
        } finally {
            this.state.isProcessing = false;
        }
    }

    _speak(text) {
        if (!this.synthesis || !text) return;
        this.synthesis.cancel();
        const clean = text.replace(/[*_#`\u2022]/g, "").replace(/\n+/g, ". ").trim();
        const utt = new SpeechSynthesisUtterance(clean);
        utt.lang = "en-US"; utt.rate = 0.95; utt.pitch = 1.0; utt.volume = 1.0;
        utt.onstart = () => { this.state.isSpeaking = true; };
        utt.onend = () => { this.state.isSpeaking = false; };
        utt.onerror = () => { this.state.isSpeaking = false; };
        this.synthesis.speak(utt);
    }

    replayResponse() { if (this.state.response) this._speak(this.state.response); }
    stopSpeaking() { if (this.synthesis) this.synthesis.cancel(); this.state.isSpeaking = false; }

    newSession() {
        if (this.synthesis) this.synthesis.cancel();
        if (this.recognition && this.state.isListening) this.recognition.stop();
        Object.assign(this.state, { isListening: false, isProcessing: false, isSpeaking: false,
            transcript: "", response: "", intent: "", sessionId: null, error: "", history: [] });
    }

    get micBtnClass() {
        if (this.state.isListening) return "btn-danger pulse-animation";
        if (this.state.isProcessing) return "btn-warning";
        return "btn-primary";
    }
    get micIcon() {
        if (this.state.isListening) return "fa-stop";
        if (this.state.isProcessing) return "fa-spinner fa-spin";
        return "fa-microphone";
    }
    get statusLabel() {
        if (this.state.isListening) return "Listening\u2026";
        if (this.state.isProcessing) return "Thinking\u2026";
        if (this.state.isSpeaking) return "Speaking\u2026";
        return "Ready";
    }
    get statusBadgeClass() {
        if (this.state.isListening) return "bg-danger";
        if (this.state.isProcessing) return "bg-warning text-dark";
        if (this.state.isSpeaking) return "bg-info";
        return "bg-success";
    }
}

registry.category("actions").add("mumtaz_voice_assistant", VoiceAssistantAction);
