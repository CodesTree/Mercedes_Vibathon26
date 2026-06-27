// Gated behind settings.voice_reply_enabled (default false) - the component
// itself doesn't check that flag; the parent/dashboard should only render
// this when the flag is on (or the backend will reject with 409
// VOICE_REPLY_DISABLED anyway, which we surface as an error below).

import { useState, useRef, useCallback } from "react";

const isMediaRecorderSupported =
  typeof window !== "undefined" &&
  "MediaRecorder" in window &&
  navigator.mediaDevices &&
  navigator.mediaDevices.getUserMedia;

function pickMimeType() {
  if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
    return "audio/webm;codecs=opus";
  }
  if (MediaRecorder.isTypeSupported("audio/ogg;codecs=opus")) {
    return "audio/ogg;codecs=opus";
  }
  return ""; // let the browser pick a default
}

export default function VoiceNoteRecorder({ messageId, transcript, onSent }) {
  const [isRecording, setIsRecording] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [audioUrl, setAudioUrl] = useState(null);
  const [error, setError] = useState(null);

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const audioBlobRef = useRef(null);

  const startRecording = useCallback(async () => {
    if (!isMediaRecorderSupported) return;
    setError(null);
    setAudioUrl(null);
    chunksRef.current = [];

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = pickMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        audioBlobRef.current = blob;
        setAudioUrl(URL.createObjectURL(blob));
        // release the mic
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setIsRecording(true);
    } catch (err) {
      setError(err.message || "Could not access microphone.");
    }
  }, []);

  const stopRecording = useCallback(() => {
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
  }, []);

  const handleUpload = useCallback(async () => {
    const blob = audioBlobRef.current;
    if (!blob) {
      setError("Record a voice note before sending.");
      return;
    }
    if (!transcript || !transcript.trim()) {
      setError("A confirmed transcript is required alongside the recording.");
      return;
    }

    setIsUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("reply_mode", "voice");
      formData.append("transcript", transcript.trim());
      const ext = blob.type.includes("ogg") ? "ogg" : "webm";
      formData.append("audio", blob, `reply.${ext}`);

      const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
      const res = await fetch(`${apiBase}/api/messages/${messageId}/reply`, {
        method: "POST",
        body: formData, // NOTE: no Content-Type header - browser sets the multipart boundary itself
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const detail =
            typeof body.detail === "string"
                ? body.detail
                : JSON.stringify(body.detail || body) || `Upload failed (${res.status})`;
        throw new Error(`${detail} (status ${res.status})`);
    }

      const result = await res.json();
      onSent?.(result);
    } catch (err) {
      setError(err.message || "Failed to send voice note.");
    } finally {
      setIsUploading(false);
    }
  }, [messageId, transcript, onSent]);

  if (!isMediaRecorderSupported) {
    return (
      <p className="text-xs text-zinc-500">
        Voice note recording isn't supported in this browser.
      </p>
    );
  }

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-zinc-400">Voice note (stretch)</span>
        {isRecording && (
          <span className="flex items-center gap-1.5 text-xs text-rose-400">
            <span className="h-2 w-2 rounded-full bg-rose-400 animate-pulse" />
            Recording…
          </span>
        )}
      </div>

      {audioUrl && (
        <audio controls src={audioUrl} className="w-full">
          Your browser does not support audio playback.
        </audio>
      )}

      {error && <p className="text-sm text-rose-400">{error}</p>}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={isRecording ? stopRecording : startRecording}
          disabled={isUploading}
          className="flex-1 rounded-md border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm font-medium text-zinc-100
                     transition hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed
                     focus:outline-none focus:ring-2 focus:ring-cyan-200 focus:ring-offset-2 focus:ring-offset-zinc-950"
        >
          {isRecording ? "Stop Recording" : "Record"}
        </button>
        <button
          type="button"
          onClick={handleUpload}
          disabled={isUploading || !audioUrl}
          className="flex-1 rounded-md bg-cyan-400 px-4 py-2 text-sm font-semibold text-zinc-950
                     transition hover:bg-cyan-300 disabled:opacity-40 disabled:cursor-not-allowed
                     focus:outline-none focus:ring-2 focus:ring-cyan-200 focus:ring-offset-2 focus:ring-offset-zinc-950"
        >
          {isUploading ? "Sending…" : "Send Voice Note"}
        </button>
      </div>
    </div>
  );
}
