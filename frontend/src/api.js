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


export function getItems() {
  return request("/api/items");
}


export function createItem(title) {
  return request("/api/items", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}
