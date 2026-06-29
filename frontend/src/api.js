const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";


async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`API request failed with status ${response.status}`);
  }

  return response.json();
}


export function getApiBaseUrl() {
  return API_BASE_URL;
}


export function getHealth() {
  return request("/health");
}


const API_CHECKS = [
  { method: "GET", path: "/health" },
  { method: "GET", path: "/api/car/state" },
  { method: "GET", path: "/api/settings/" },
  { method: "GET", path: "/api/contacts/" },
  { method: "GET", path: "/api/messages/" },
  { method: "GET", path: "/api/calendar/events" },
  { method: "GET", path: "/api/automations/next-departure" },
  { method: "GET", path: "/api/automations/log" },
];


// Never throws — returns a result row even on failure so one dead
// endpoint can't break the panel.
async function checkEndpoint({ method, path }) {
  const start = performance.now();
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, { method });
    return {
      method,
      path,
      ok: response.ok,
      status: response.status,
      ms: Math.round(performance.now() - start),
    };
  } catch (requestError) {
    return {
      method,
      path,
      ok: false,
      status: 0,
      ms: Math.round(performance.now() - start),
      error: requestError.message,
    };
  }
}


export function runApiChecks() {
  return Promise.all(API_CHECKS.map(checkEndpoint));
}

// --- Agent / voice features 

// Send a text reply (STT transcript) for a given message.
// Spec: POST /api/messages/{id}/reply  { reply_mode: "text", transcript }
export function sendTextReply(messageId, transcript) {
  return request(`/api/messages/${messageId}/reply`, {
    method: "POST",
    body: JSON.stringify({ reply_mode: "text", transcript }),
  });
}

// Send a voice command transcript to the assistant.
// Spec: POST /api/assistant/command  { transcript }
export function sendAssistantCommand(transcript) {
  return request("/api/assistant/command", {
    method: "POST",
    body: JSON.stringify({ transcript }),
  });
}