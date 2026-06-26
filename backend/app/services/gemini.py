import os
import json

import httpx

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

_CLASSIFY_DEFAULT = {"priority": "normal", "summary": None, "suggested_reply": None}
_ASSISTANT_DEFAULT = {"spoken_text": "Sorry, I couldn't process that.", "action": None, "action_data": None}


def _api_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "")


async def _generate(model: str, prompt: str) -> str:
    url = f"{GEMINI_API_BASE}/{model}:generateContent"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, params={"key": _api_key()}, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


async def classify_and_summarize(message_body: str, contact_name: str, relationship: str | None) -> dict:
    prompt = (
        "You are a message classifier for a busy executive's in-car assistant.\n\n"
        f"Contact: {contact_name} (relationship: {relationship or 'unknown'})\n"
        f"Message: \"{message_body}\"\n\n"
        "Respond with JSON only (no markdown):\n"
        "{\"priority\": \"low\"|\"normal\"|\"high\", \"summary\": \"one sentence summary\", \"suggested_reply\": \"draft reply text\"}\n\n"
        "Rules:\n"
        "- \"high\" for boss, urgent, time-sensitive, meeting changes\n"
        "- \"low\" for marketing, promotions, spam\n"
        "- \"normal\" for everything else"
    )
    try:
        text = await _generate("gemini-2.5-flash", prompt)
        # Strip markdown code fences if present
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        result = json.loads(cleaned.strip())
        return {
            "priority": result.get("priority", "normal"),
            "summary": result.get("summary"),
            "suggested_reply": result.get("suggested_reply"),
        }
    except Exception:
        return dict(_CLASSIFY_DEFAULT)


async def draft_late_apology(contact_name: str, event_title: str, minutes_late: int) -> str:
    prompt = (
        f"Draft a short, friendly apology message (1-2 sentences) to {contact_name} "
        f"saying I am running about {minutes_late} minutes late to {event_title}. "
        f"Be professional and brief."
    )
    fallback = f"Hi {contact_name}, I'm running about {minutes_late} minutes late to {event_title}. See you soon."
    try:
        text = await _generate("gemini-2.5-flash", prompt)
        return text.strip() or fallback
    except Exception:
        return fallback


async def process_assistant_command(transcript: str, context: dict) -> dict:
    prompt = (
        "You are an in-car AI assistant. Given the driver's voice command, determine the action.\n\n"
        f"Command: \"{transcript}\"\n\n"
        "Respond with JSON only:\n"
        "{\"action\": \"summarize_messages\"|\"late_check\"|\"cabin_cool\"|\"navigate_to\"|null, "
        "\"spoken_text\": \"response to speak to driver\", \"action_data\": {}}\n\n"
        "Actions:\n"
        "- summarize_messages: driver wants to hear their messages\n"
        "- late_check: driver asks if they're late\n"
        "- cabin_cool: driver wants to cool the cabin\n"
        "- navigate_to: driver wants to navigate somewhere (extract destination in action_data.destination)\n"
        "- null: unknown command"
    )
    try:
        text = await _generate("gemini-2.5-pro", prompt)
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        result = json.loads(cleaned.strip())
        return {
            "spoken_text": result.get("spoken_text", _ASSISTANT_DEFAULT["spoken_text"]),
            "action": result.get("action"),
            "action_data": result.get("action_data"),
        }
    except Exception:
        return dict(_ASSISTANT_DEFAULT)
