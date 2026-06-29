// Reply modal piece (spec §5, "Speak Reply" flow).
// Driver taps "Speak Reply" -> Web Speech API transcribes speech live ->
// transcript is editable -> driver taps "Send" -> POST /messages/{id}/reply
//
// NOTE: Web Speech API (SpeechRecognition) is currently Chrome/Edge only.
// Firefox and Safari do not support it reliably - this component detects
// that and disables the mic button with a message instead of crashing.

import { useState, useRef, useCallback } from "react";
import { sendTextReply } from "../api";

const SpeechRecognitionImpl =
  typeof window !== "undefined"
    ? window.SpeechRecognition || window.webkitSpeechRecognition
    : null;

export default function SpeechToTextReply({
  messageId,
  suggestedReply = "",
  onSent,
}) {
  const [transcript, setTranscript] = useState(suggestedReply);
  const [isListening, setIsListening] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState(null);
  const recognitionRef = useRef(null);

  const isSupported = Boolean(SpeechRecognitionImpl);

  const startListening = useCallback(() => {
    if (!isSupported) return;
    setError(null);

    const recognition = new SpeechRecognitionImpl();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onresult = (event) => {
      const text = Array.from(event.results)
        .map((r) => r[0].transcript)
        .join("");
      setTranscript(text);
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
  }, [isSupported]);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    setIsListening(false);
  }, []);

  const handleSend = useCallback(async () => {
    const trimmed = transcript.trim();
    if (!trimmed) {
      setError("Say or type a reply before sending.");
      return;
    }
    setIsSending(true);
    setError(null);
    try {
      const result = await sendTextReply(messageId, trimmed);
      onSent?.(result);
    } catch (err) {
      setError(err.message || "Failed to send reply.");
    } finally {
      setIsSending(false);
    }
  }, [transcript, messageId, onSent]);

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-zinc-400">Reply</span>
        {isListening && (
          <span className="flex items-center gap-1.5 text-xs text-rose-400">
            <span className="h-2 w-2 rounded-full bg-rose-400 animate-pulse" />
            Listening…
          </span>
        )}
      </div>

      <textarea
        className="w-full resize-none rounded-md border border-zinc-700 bg-zinc-900 p-3 text-sm text-zinc-100
                   placeholder:text-zinc-500
                   focus:outline-none focus:ring-2 focus:ring-cyan-400"
        rows={3}
        value={transcript}
        onChange={(e) => setTranscript(e.target.value)}
        placeholder="Tap the mic and speak your reply, or type here…"
        disabled={isSending}
      />

      {error && <p className="text-sm text-rose-400">{error}</p>}

      {!isSupported && (
        <p className="text-xs text-zinc-500">
          Voice dictation isn't supported in this browser. You can still type your reply above.
        </p>
      )}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={isListening ? stopListening : startListening}
          disabled={!isSupported || isSending}
          className="flex-1 rounded-md border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm font-medium text-zinc-100
                     transition hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed
                     focus:outline-none focus:ring-2 focus:ring-cyan-200 focus:ring-offset-2 focus:ring-offset-zinc-950"
        >
          {isListening ? "Stop" : "Speak Reply"}
        </button>
        <button
          type="button"
          onClick={handleSend}
          disabled={isSending || !transcript.trim()}
          className="flex-1 rounded-md bg-cyan-400 px-4 py-2 text-sm font-semibold text-zinc-950
                     transition hover:bg-cyan-300 disabled:opacity-40 disabled:cursor-not-allowed
                     focus:outline-none focus:ring-2 focus:ring-cyan-200 focus:ring-offset-2 focus:ring-offset-zinc-950"
        >
          {isSending ? "Sending…" : "Send"}
        </button>
      </div>
    </div>
  );
}
