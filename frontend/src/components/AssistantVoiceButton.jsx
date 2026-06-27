// Assistant voice command piece (spec §5 + §6.7).
// Driver taps the mic -> speaks a command ("am I late?", "cool the cabin") ->
// transcript sent to POST /assistant/command -> response spoken back via TTS.

import { useState, useRef, useCallback } from "react";
import { sendAssistantCommand } from "../api";

const SpeechRecognitionImpl =
  typeof window !== "undefined"
    ? window.SpeechRecognition || window.webkitSpeechRecognition
    : null;

const speechSynthesisSupported =
  typeof window !== "undefined" && "speechSynthesis" in window;

export default function AssistantVoiceButton() {
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [lastTranscript, setLastTranscript] = useState("");
  const [lastResponse, setLastResponse] = useState("");
  const [error, setError] = useState(null);
  const recognitionRef = useRef(null);

  const isSupported = Boolean(SpeechRecognitionImpl);

  const speak = useCallback((text) => {
    if (!speechSynthesisSupported || !text) return;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    window.speechSynthesis.cancel(); // stop any prior utterance
    window.speechSynthesis.speak(utterance);
  }, []);

  const handleCommand = useCallback(
    async (transcript) => {
      setIsProcessing(true);
      setError(null);
      try {
        const result = await sendAssistantCommand(transcript);
        setLastResponse(result.spoken_text);
        speak(result.spoken_text);
      } catch (err) {
        const message = "Sorry, I couldn't process that.";
        setError(err.message || message);
        speak(message);
      } finally {
        setIsProcessing(false);
      }
    },
    [speak]
  );

  const startListening = useCallback(() => {
    if (!isSupported) return;
    setError(null);
    setLastTranscript("");
    setLastResponse("");

    const recognition = new SpeechRecognitionImpl();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    recognition.onresult = (event) => {
      const text = event.results[0][0].transcript;
      setLastTranscript(text);
      handleCommand(text);
    };

    recognition.onerror = (event) => {
      setError(`Mic error: ${event.error}`);
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  }, [isSupported, handleCommand]);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    setIsListening(false);
  }, []);

  if (!isSupported) {
    return (
      <p className="text-xs text-zinc-500">
        Voice commands aren't supported in this browser.
      </p>
    );
  }

  return (
    <div className="flex flex-col items-center gap-3">
      <button
        type="button"
        onClick={isListening ? stopListening : startListening}
        disabled={isProcessing}
        className={`flex h-16 w-16 items-center justify-center rounded-full text-zinc-950 shadow-md
                    transition-colors disabled:opacity-50
                    focus:outline-none focus:ring-2 focus:ring-cyan-200 focus:ring-offset-2 focus:ring-offset-zinc-900
                    ${isListening ? "bg-rose-400 animate-pulse" : "bg-cyan-400 hover:bg-cyan-300"}`}
        aria-label={isListening ? "Stop listening" : "Start voice command"}
      >
        {/* simple mic glyph, no icon library dependency */}
        <svg viewBox="0 0 24 24" fill="currentColor" className="h-7 w-7">
          <path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3z" />
          <path d="M19 11a1 1 0 1 0-2 0 5 5 0 0 1-10 0 1 1 0 1 0-2 0 7 7 0 0 0 6 6.92V20H9a1 1 0 1 0 0 2h6a1 1 0 1 0 0-2h-2v-2.08A7 7 0 0 0 19 11z" />
        </svg>
      </button>

      <div className="min-h-[3rem] max-w-xs text-center text-sm">
        {isProcessing && <p className="text-zinc-500">Thinking…</p>}
        {!isProcessing && lastTranscript && (
          <p className="text-zinc-400">"{lastTranscript}"</p>
        )}
        {!isProcessing && lastResponse && (
          <p className="mt-1 font-medium text-zinc-100">{lastResponse}</p>
        )}
        {error && <p className="text-rose-400">{error}</p>}
      </div>
    </div>
  );
}
