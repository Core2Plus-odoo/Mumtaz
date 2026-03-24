/** @odoo-module **/

import { Component, useState, onWillUnmount, useEffect, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

class VoiceAssistantAction extends Component {
    static template = "mumtaz_voice.VoiceAssistantAction";

    setup() {
        this.notification = useService("notification");
        this.historyRef = useRef("historyContainer");

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
            language: "en",
            browserSupported: !!(window.SpeechRecognition || window.webkitSpeechRecognition),
        });

        this.recognition = null;
        this.synthesis = window.speechSynthesis || null;
        this.currentAudio = null;
        this._initRecognition();

        // Auto-scroll history to bottom on new messages
        useEffect(() => {
            const el = this.historyRef.el;
            if (el) el.scrollTop = el.scrollHeight;
        }, () => [this.state.history.length]);

        onWillUnmount(() => {
            if (this.recognition) this.recognition.abort();
            this._stopAudio();
        });
    }

    _initRecognition() {
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) return;
        this.recognition = new SR();
        this.recognition.continuous = false;
        this.recognition.interimResults = true;

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
            if (e.error !== "aborted") {
                this.state.error = this.state.language === "ar"
                    ? `خطأ في الميكروفون: "${e.error}". يرجى التحقق من صلاحيات المتصفح.`
                    : `Microphone error: "${e.error}". Please check browser permissions or type your question.`;
            }
        };
    }

    setLanguage(ev) {
        const lang = ev.currentTarget.dataset.lang;
        if (lang) this.state.language = lang;
    }

    toggleMic() {
        if (!this.state.browserSupported) {
            this.notification.add(
                this.state.language === "ar"
                    ? "يتطلب الإدخال الصوتي Chrome أو Edge. يرجى كتابة سؤالك."
                    : "Voice input requires Chrome or Edge. Please type your question.",
                { type: "warning" }
            );
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
            this.recognition.lang = this.state.language === "ar" ? "ar-SA" : "en-US";
            try {
                this.recognition.start();
            } catch {
                this.state.isListening = false;
                this.state.error = "Could not start microphone. Check browser permissions.";
            }
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
            const result = await rpc("/mumtaz/voice/query", {
                transcript: question,
                session_id: this.state.sessionId,
                language: this.state.language,
            });
            if (result.error) { this.state.error = result.error; return; }
            const answer = result.response || "No response received.";
            this.state.response = answer;
            this.state.intent = result.intent || "";
            this.state.sessionId = result.session_id;
            this.state.history = [...this.state.history, {
                question,
                response: answer,
                intent: result.intent || "",
                time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
                lang: this.state.language,
            }];
            this.state.transcript = "";
            this._speak(answer);
        } catch (err) {
            this.state.error = `Request failed: ${err.message || "Unknown error."}`;
        } finally {
            this.state.isProcessing = false;
        }
    }

    async _speak(text) {
        if (!text) return;
        this._stopAudio();
        this.state.isSpeaking = true;
        const clean = text.replace(/[*_#`\u2022]/g, "").trim();
        try {
            const result = await rpc("/mumtaz/voice/tts", {
                text: clean.substring(0, 4000),
                language: this.state.language,
            });
            if (result.error) throw new Error(result.error);
            const audio = new Audio("data:audio/mpeg;base64," + result.audio);
            this.currentAudio = audio;
            audio.onended = () => { this.state.isSpeaking = false; this.currentAudio = null; };
            audio.onerror = () => {
                this.state.isSpeaking = false;
                this.currentAudio = null;
                this._speakFallback(clean);
            };
            await audio.play();
        } catch {
            this.state.isSpeaking = false;
            this._speakFallback(clean);
        }
    }

    _speakFallback(text) {
        if (!this.synthesis || !text) return;
        this.synthesis.cancel();
        const utt = new SpeechSynthesisUtterance(text.replace(/\n+/g, ". "));
        utt.lang = this.state.language === "ar" ? "ar-SA" : "en-US";
        utt.rate = 0.95; utt.pitch = 1.0; utt.volume = 1.0;
        utt.onstart = () => { this.state.isSpeaking = true; };
        utt.onend = () => { this.state.isSpeaking = false; };
        utt.onerror = () => { this.state.isSpeaking = false; };
        this.synthesis.speak(utt);
    }

    _stopAudio() {
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio = null;
        }
        if (this.synthesis) this.synthesis.cancel();
        this.state.isSpeaking = false;
    }

    replayResponse() { if (this.state.response) this._speak(this.state.response); }
    stopSpeaking() { this._stopAudio(); }

    newSession() {
        this._stopAudio();
        if (this.recognition && this.state.isListening) this.recognition.stop();
        Object.assign(this.state, {
            isListening: false, isProcessing: false, isSpeaking: false,
            transcript: "", response: "", intent: "", sessionId: null, error: "", history: [],
        });
    }

    get isRTL() { return this.state.language === "ar"; }

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
        const ar = this.isRTL;
        if (this.state.isListening) return ar ? "جارٍ الاستماع..." : "Listening\u2026";
        if (this.state.isProcessing) return ar ? "جارٍ التحليل..." : "Thinking\u2026";
        if (this.state.isSpeaking) return ar ? "جارٍ التحدث..." : "Speaking\u2026";
        return ar ? "جاهز" : "Ready";
    }
    get statusBadgeClass() {
        if (this.state.isListening) return "bg-danger";
        if (this.state.isProcessing) return "bg-warning text-dark";
        if (this.state.isSpeaking) return "bg-info";
        return "bg-success";
    }
    get placeholderText() {
        return this.isRTL
            ? "اسأل سؤالك المالي... مثال: 'ما هو وضع السيولة النقدية؟'"
            : "Ask your CFO question\u2026 e.g. 'What is our cash position?'";
    }
}

registry.category("actions").add("mumtaz_voice_assistant", VoiceAssistantAction);
