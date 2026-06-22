# CarPA — Vibathon 2026 PoC Spec Sheet

## Section 1 — Idea Overview

```
Idea Name: CarPA (Car Personal Assistant)
Track: Intelligent Experience (primary), with Operational Efficiency depth
Team: TBD (4 members)
Pitch Date: 6 July 2026
```

CarPA is a proactive multi-agent orchestration layer for the Mercedes-Benz connected ecosystem that treats the vehicle as both a mobility partner and a living financial asset. Three specialist AI agents — a Personal Assistant Agent, a Maintenance Agent, and an AssetIQ Agent — share a common data backbone and collaborate through a single LLM orchestrator to manage the driver's time, safety, and money before they ever ask. Where today's tools (Calendar, Maps, Siri, CarPlay) operate in silos that the driver must bridge manually while driving, CarPA closes the loop: it learns the driver's patterns, adapts to live conditions, and initiates decisions — the definition of an AI-Defined Vehicle.

---

## Section 2 — Problem / Issue

Busy professionals in Malaysia juggle tight schedules against heavy traffic, sudden tropical weather, and constant work communications — and the tools meant to help them don't talk to each other. The driver becomes the integration layer: checking traffic, deciding when to leave, replying "running late" texts, and adjusting cabin comfort, all while operating a vehicle. This cognitive overload produces real safety risk (distracted phone use behind the wheel) and erodes the premium experience a Mercedes should deliver.

A second, quieter cost hits after the drive. A Mercedes is typically its owner's second-largest financial asset, yet in a market where used cars make up ~65% of Malaysian automotive sales, owners manage that asset blind — servicing only when a warning light appears, selling without data, and timing trade-ins with no view of SST exemption cycles, OPR moves, or AP policy changes. The result is thousands of Ringgit in avoidable leakage from mistimed servicing and uninformed resale decisions. Nobody has solved this well because it requires fusing in-car telemetry, personal context, and external market data — exactly the integration only the vehicle's own connected ecosystem can do.

---

## Section 3 — How the Solution Solves It

CarPA replaces the driver-as-integrator with an orchestrated team of agents. The **Personal Assistant Agent** predicts departure time from calendar + live traffic + weather, pre-conditions the cabin before the driver arrives, drafts approval-gated "running late" messages delivered via TTS, and suppresses non-urgent notifications when a driving-load classifier detects high cognitive demand (rain, dense traffic, high speed). The **Maintenance Agent** monitors OBD-II component-health streams and forecasts which components need attention in the next 3 months. The **AssetIQ Agent** runs a resale-price regression model trained on Malaysian used-car listings (Mudah.my / Carlist.my / MB Certified snapshot) plus a market-timing monitor over economic signals, and converts mechanical events into financial advice ("servicing now adds ~RM2,400–3,100 to resale value").

The before/after is concrete: before, the driver checks five apps at red lights and discovers maintenance needs from a warning light; after, the car has already pre-cooled, told them when to leave, silenced the noise, and booked the brake service into a free calendar slot — with the financial justification attached.

**Agent Decision Loop**
> **Perceive** → calendar events, live traffic & weather, cabin/vehicle telematics, OBD-II health streams, message context, used-car market listings, MY economic news signals
> **Reason** → LLM orchestrator routes events to specialist agents; agents combine LLM reasoning with dedicated ML models (resale regression, wear forecasting, driving-load classification) and negotiate with each other (e.g., AssetIQ asks PA Agent for a calendar slot)
> **Act** → pre-condition cabin, push urgency-ranked departure alerts, draft & TTS messages for one-tap approval, suppress notifications, propose & book workshop appointments, render Smart Sell dashboard
> **Learn** → every accept/dismiss/edit is a feedback signal: departure predictions calibrate against actual departure times, the notification suppressor updates per-driver urgency weights, and the resale model retrains on fresh listing data

---

## Section 4 — What Makes It Special / Unique

Existing MB features and consumer apps each solve one slice; CarPA's differentiator is the **orchestration layer** — agents that visibly collaborate on a single decision spanning the driver's time, the vehicle's health, and its market value. The "only we can do this" angle is data fusion depth: only the vehicle's own ecosystem holds telemetry + cabin control + driver context simultaneously, and CarPA adds a Malaysia-specific market intelligence layer (SST/OPR/AP signals, local listing data) that no global competitor models. The timing is right: MB is publicly moving from SDV to AIDV, agentic LLM tool-calling matured in 2025, and Malaysia's used-car market volatility makes ownership-economics guidance immediately valuable.

- **Unique Data Angle**: fusion of OBD-II health streams + personal calendar/comms context + a Malaysian used-car listings dataset + local economic signals — a combination no single existing product touches
- **AI Technique**: LLM orchestrator with function-calling (agent-to-agent delegation), gradient-boosted regression for resale pricing, time-series wear forecasting for component health, and an online-learning preference model for notification suppression — LLMs for reasoning and language, classical ML for the numbers
- **MB Brand Fit**: extends the "executive lounge" promise beyond the cabin — a Mercedes that manages your time, protects your attention, and stewards your asset is the premium experience, not just leather and ride quality

---

## Section 5 — PoC Scope (What You Will Actually Build — 72 hours)

**In scope for the PoC demo:**

1. **Scenario simulation engine** — a scripted "day in the life" timeline (scrubber-controlled) that streams mocked calendar, traffic, weather, and OBD-II events into the system — *mocked data (JSON streams + MBTMY-provided telemetry where available)*
2. **LLM orchestrator + 3 agents** — Gemini API function-calling loop; each agent is a system prompt + toolset over the shared context store; inter-agent messages are real LLM tool calls, not hardcoded — *real AI on mocked inputs*
3. **Live Agent Activity Feed** — UI panel showing every perceive→reason→act→delegate message between agents in real time; this is the proof of orchestration — *real*
4. **Hero cross-agent flow** — Maintenance Agent detects brake wear trend → AssetIQ quantifies resale impact → PA Agent finds a calendar slot and proposes a workshop booking → one-tap driver approval — *real agent chain, mocked workshop API*
5. **Smart Sell mini-dashboard + resale model** — gradient-boosted regression trained on a scraped/synthesized snapshot (~500–1,000 listings) showing predicted price range with confidence band and "service now vs. later" delta — *real model, snapshot data*

**Out of scope (future roadmap):**
- Live daily scraping of Mudah.my/Carlist.my and live news-API economic monitoring (PoC uses a frozen snapshot + scripted SST event)
- Real vehicle integration (cabin pre-conditioning is simulated state), real messaging/calendar OAuth (mocked accounts)
- AAOS native app — PoC is a web cockpit styled after MBUX

**Tech Stack:**
- Frontend: React + Vite single-page web app — MBUX-style cockpit, agent activity feed, Smart Sell tab, phone-notification mock; Web Speech API for TTS
- AI/ML: Gemini API (Google AI Studio free tier) for orchestrator + agents with function calling; scikit-learn (gradient boosting) for resale regression; lightweight rolling-statistics forecaster for component wear; logistic preference model updated from driver feedback
- Data: mocked telemetry JSON streams, MBTMY mocked datasets, one-time scraped/synthesized MY used-car listings CSV
- Backend: FastAPI + WebSocket — runs the simulation clock, the agent loop, and pushes events to the UI

**Demo scenario (what the judge sees):**
It's a simulated Tuesday 7:40 AM: CarPA sees a 9:00 client meeting, rain, and building traffic — the cockpit shows the cabin pre-cooling and an alert lands: "Leave by 8:05, not 8:20." Mid-drive the simulation injects a jam; the PA Agent drafts a running-late message, reads it aloud via TTS, and the driver approves with one tap while two non-urgent notifications are visibly suppressed because the driving-load classifier reads high. The Maintenance Agent then flags front brake pads trending to threshold in ~6 weeks from the OBD stream. In the Agent Activity Feed, judges watch AssetIQ respond that servicing before resale adds RM2,400–3,100, and the PA Agent reply with a free Thursday 2 PM slot at the nearest workshop — booked on the driver's approval. The demo closes on the Smart Sell dashboard: predicted resale range, confidence band, and a recommended upgrade window flagged by a scripted SST-exemption news event.

---

## Section 6 — Judging Criteria Alignment

| Criterion | Weight | How CarPA scores | Evidence / What to show |
|---|---|---|---|
| Innovation & Creativity | 20% | High — multi-agent orchestration over a car is fresh, and "vehicle as financial asset" with MY market signals is an angle no judge will have seen twice | The hero cross-agent flow: three agents negotiating one decision live |
| AI Utilization | 20% | High — LLM function-calling orchestration + three named ML models + a visible learning loop; explicitly not rule-based | Agent Activity Feed showing real tool calls; feedback updating suppression weights on screen |
| Impact & Value | 20% | High — safety (distraction reduction) + quantified money (RM2,400–3,100 resale delta; mistimed trade-in leakage) | One impact slide with assumptions stated; the RM figure appearing inside the demo |
| User Experience | 15% | Medium-High — one-tap approvals, TTS, calm MBUX-style cockpit; risk is clutter, so demo only the hero path | Smooth scripted scenario; suppressed notifications visibly queued, not lost |
| Technical Implementation | 15% | Medium-High — honest architecture: simulation layer, shared context store, orchestrator, real models; clearly scoped mocks | Architecture slide; admit what's mocked before judges ask |
| Presentation & Demo | 10% | Depends on rehearsal — scripted scenario player de-risks the live demo | Backup screen-recording; 90-second demo segment rehearsed to time |

---

## Section 7 — Pitch Outline (4 minutes)

| Segment | Time | Content |
|---|---|---|
| Hook | 0:00–0:30 | "It's 7:40 AM, raining, your client meeting is at 9, your phone has 11 notifications, and your brake pads are 6 weeks from a warning light you don't know about yet." No tech jargon. |
| Solution | 0:30–1:30 | CarPA: three specialist agents, one orchestrator, one data backbone. Show the Perceive→Reason→Act→Learn loop on one visual. Name the techniques: LLM function-calling orchestration, resale regression, wear forecasting, learned notification suppression. |
| Demo | 1:30–3:00 | The scripted Tuesday-morning scenario. Narrate the Agent Activity Feed: "watch the Maintenance Agent ask AssetIQ what this brake job is worth — RM2,800 — and the PA Agent book Thursday 2 PM." |
| Impact & Uniqueness | 3:00–3:40 | One number (Ringgit protected per ownership cycle + distraction events suppressed per drive). Why AI is essential: this is negotiation between agents, not if-then rules. Why MB: only the vehicle's ecosystem holds all three data domains. |
| Close | 3:40–4:00 | "CarPA turns a Mercedes from a machine you drive into a partner that manages your time, your safety, and your money." Team names. |

**Anticipated QnA — prepared answers:**

1. **"Is it truly adaptive or rule-based?"** — Three explicit learning loops: departure predictions calibrate against actual departures, the suppression model updates per-driver urgency weights from accept/dismiss feedback, and the resale model retrains on fresh listings. Show the weights changing in the demo if asked.
2. **"What if the AI is wrong?"** — Every outward action is approval-gated (messages, bookings); suppression queues notifications rather than deleting them; resale predictions are shown as ranges with confidence, never point claims; safety-critical functions are never delegated to the LLM.
3. **"PoC to production?"** — The orchestrator pattern maps onto MB's existing connected-car backend; agents are modular plug-ins on a shared event bus, so production means swapping mocked adapters (telemetry, calendar, workshop booking) for real APIs — the architecture doesn't change.
4. **"Better than what MB already offers?"** — MBUX reacts to commands; the ME app shows data. CarPA initiates: cross-domain decisions (mechanical event → financial impact → calendar action) that no current MB feature chain performs, plus a Malaysia-market asset layer MB doesn't have anywhere.
5. **"Privacy?"** — Calendar/message access is opt-in per scope, message content is processed transiently and never stored, financial profiles stay on the owner's account, and the demo shows the consent screen first.

---

## Appendix — 72-Hour Build Plan (team of 4)

| Window | Deliverable | Owner split |
|---|---|---|
| H0–8 | Repo + scaffolding; mock-data generator (calendar/traffic/weather/OBD JSON streams); scenario script v1; UI shell with cockpit layout | All four pair up: data×1, frontend×1, backend×1, agents×1 |
| H8–24 | FastAPI sim clock + WebSocket bus; orchestrator loop with Gemini function-calling; PA Agent end-to-end (departure alert + TTS message draft) | Backend+agents pair; frontend builds activity feed |
| H24–48 | Maintenance Agent (wear forecaster) + AssetIQ (train resale regression on listings CSV); wire the hero cross-agent flow; Smart Sell dashboard | ML owner on models; agents owner on chain; frontend on dashboard |
| H48–60 | Learning-loop visibility (suppression weights, calibration); polish, error handling, demo-mode hardening (deterministic seed) | All |
| H60–72 | Pitch deck, 90-second demo rehearsal ×5, backup screen recording, QnA drill | All |

**Biggest risks:** LLM latency during live demo (mitigate: cache/seed the scripted run, keep live calls to the hero flow only); overscoping the UI (mitigate: one hero path, everything else is a static tab); resale data quality (mitigate: synthesize around a small scraped seed, state it honestly).
