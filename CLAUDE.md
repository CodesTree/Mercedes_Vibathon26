## Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

Tradeoff: These guidelines bias toward caution over speed. For trivial tasks, use judgment.

1. Think Before Coding
   Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:

State your assumptions explicitly. If uncertain, ask.
If multiple interpretations exist, present them - don't pick silently.
If a simpler approach exists, say so. Push back when warranted.
If something is unclear, stop. Name what's confusing. Ask. 2. Simplicity First
Minimum code that solves the problem. Nothing speculative.

No features beyond what was asked.
No abstractions for single-use code.
No "flexibility" or "configurability" that wasn't requested.
No error handling for impossible scenarios.
If you write 200 lines and it could be 50, rewrite it.
Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

3. Surgical Changes
   Touch only what you must. Clean up only your own mess.

When editing existing code:

Don't "improve" adjacent code, comments, or formatting.
Don't refactor things that aren't broken.
Match existing style, even if you'd do it differently.
If you notice unrelated dead code, mention it - don't delete it.
When your changes create orphans:

Remove imports/variables/functions that YOUR changes made unused.
Don't remove pre-existing dead code unless asked.
The test: Every changed line should trace directly to the user's request.

4. Goal-Driven Execution
   Define success criteria. Loop until verified.

Transform tasks into verifiable goals:

"Add validation" → "Write tests for invalid inputs, then make them pass"
"Fix the bug" → "Write a test that reproduces it, then make it pass"
"Refactor X" → "Ensure tests pass before and after"
For multi-step tasks, state a brief plan:

1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
   Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

These guidelines are working if: fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## CarPa — Feature Summary

### F1 · Telegram Message Triage + STT Reply

Inbound Telegram DMs are polled, deduplicated by `update_id`, and upserted into `messages`. Gemini classifies priority (`low`/`normal`/`high`) and generates a reply suggestion. `low` + `marketing` contacts are auto-silenced. `normal`/`high` messages surface on the dashboard with the Gemini draft.

**Primary reply (must-demo):** Web Speech API STT → transcript sent as plain Telegram text via `POST /api/messages/{id}/reply` (`reply_mode="text"`). No blobs, no MediaRecorder.

**Stretch reply:** `voice_reply_enabled=true` → MediaRecorder WebM/Opus → `sendVoice`. Failure → blob deleted, `status="send_failed"`.

Invariants: Gemini outage → `priority="normal"`, `summary=null`, HTTP 200. Empty transcript → 422. Voice when disabled → 409 `VOICE_REPLY_DISABLED`. Replying to already-replied message → 409 `INVALID_TRANSITION`.

### F2 · Arriving-Late Responder

Triggered by `POST /api/automations/run-late-check`. Computes `mins_late = (now + resolved_eta) − event.start`. If `≥ settings.late_threshold_min` (default 15): Gemini drafts an apology → sent as Telegram text to all matched calendar attendees with a `tg_chat_id`. Unmatched attendees skipped. Gemini failure → static fallback. One `automation_log` row per invocation (`type="late_responder"`).

### F3 · Calendar → Cabin Cooling + Departure Planning

Fetches Google Calendar events (SQLite cache fallback, `source="cache"` on outage). Computes `leave_by = event.start − resolved_eta − 5 min` and `precool_due = leave_by − precool_lead_min`. Dashboard shows countdown + late warning. `POST /api/car/cabin/cool` → `climate_on=true`, logs `type="cabin_precool"` (idempotent). `precool_fired=true` once a precool log exists for the current event.

### Navigation (ETA utility only)

`POST /api/nav/route` → TomTom Routing API → writes `route_polyline`, `route_eta_minutes`, `eta_source="tomtom"` atomically. Failure → 502, `car_state` unchanged. `TOMTOM_API_KEY` never exposed to browser. No animation, turn-by-turn, or traffic overlay.
