# Skill: Frontend

Read this file before building any part of the React frontend. It sets direction and constraints — use judgment on specifics (exact colors, font choice, component structure, CSS approach) within these principles.

---

## 1. Project Overview

PawMatch is a dog breed recommendation engine. The frontend is a React single-page application that guides users through a multi-step lifestyle questionnaire and displays a ranked list of dog breed recommendations.

The app should feel warm, friendly, and approachable — like a trusted advisor helping someone make an important life decision, not a cold data tool.

---

## 2. Tech Stack

- React with Vite — scaffold with `npm create vite@latest frontend -- --template react`
- No UI component library — build components from scratch using CSS modules or plain CSS
- No TypeScript — plain JavaScript only
- The backend runs locally at `http://localhost:8001` during development
- Read `skills/api-contract.md` before building anything that touches the API — the request and response shapes are authoritative. Do not invent or guess field names.

---

## 3. Application Structure

Two main views:

- **Questionnaire** — a multi-step form that collects the user's lifestyle inputs
- **Results** — a ranked list of breed recommendation cards, shown after the API responds

Suggested step grouping (adjust within reason — the goal is one focused topic per step, not this exact split):

| Step | Topic | Fields |
|---|---|---|
| 1 | Housing | property type, has yard |
| 2 | Household | has kids, has elderly, has other dogs, has cats, allergies |
| 3 | Budget & experience | monthly budget, owner experience level |
| 4 | Lifestyle | daily time available, climate, outdoor time expected, grooming commitment, primary purpose, prioritize longevity, prioritize low vet costs |
| 5 | Preferences | noise tolerance, max size category, size-strict toggle (with a clear explanation of what "strict" means) |
| 6 | Trait ranking | drag-and-rank UI for the 6 traits: `energy_level`, `trainability`, `barking_level`, `affection_level`, `protective_instinct`, `shedding_level` |

Each trait in Step 6 needs a short plain-English label and a one-line description so users understand what they're ranking before they rank it.

---

## 4. Design Direction

- **Color palette** — warm and friendly: earthy tones, soft greens, warm neutrals. Avoid cold blues or stark black-and-white.
- **Typography** — a single Google Font that feels friendly and modern. Use size and weight hierarchy to create structure rather than decorative elements.
- **Whitespace** — generous. The questionnaire should feel calm and uncluttered; one focused question or section per step.
- **Progress indicator** — always show users which step they're on and how many remain.
- **Drag-and-rank (Step 6)** — must be intuitive: visual drag handles, clear labels, and a brief instruction at the top explaining what to do.
- **Results cards** — each shows: breed image (with a graceful fallback when no image is available), breed name prominently, rank badge, the `match_explanation` from Groq, and three key stats (size category, energy level, monthly cost). Keep cards clean and scannable.
- **Mobile-friendly** — the app should work reasonably well on mobile widths even though it's primarily designed for desktop.
- **Loading state** — show a friendly loading indicator while waiting for the API response; the Groq call adds noticeable latency.

---

## 5. API Integration

- `POST` to `http://localhost:8001/recommend` with the full request body defined in `skills/api-contract.md`.
- Zero-results case: show a friendly message explaining no breeds matched and suggest loosening the filters. Don't treat it as an error.
- API errors: show a friendly error state with an option to retry.
- Never show raw error messages, status codes, or stack traces to the user.

---

## 6. State Management

- `useState` and `useContext` only — no Redux or other external state libraries.
- All questionnaire state lives in a single top-level state object, assembled into the request body on submission.
- After results are returned, the user can go back, adjust their answers, and resubmit.

---

## 7. Non-Obvious Rules

- `trait_priority_ranking` sent to the API must be exactly 6 items and a valid permutation of the allowed trait names — validate this client-side before submitting, not just on the backend.
- `size_strict` defaults to `false`. Include a tooltip or inline explanation so users understand what enabling it does.
- Present enum-like options (e.g. `primary_purpose`) with friendly labels, never raw API values — "Family pet," not `family_pet`.
- Do not expose raw API field names anywhere in the UI.
- The app should work correctly against a backend running with `DB_MODE=local` — no backend changes are needed for frontend development.

---

## 8. Development Workflow

- Scaffold under `frontend/` using Vite.
- Run the dev server with `npm run dev` from within `frontend/`.
- The backend must be running on port 8001 for API calls to work during development.
- Configure the Vite dev server proxy to forward `/recommend` requests to `http://localhost:8001`, so the frontend can call a relative path and CORS isn't a concern during development.
