# SJ Inspect Agent

An agentic workflow that books your San Jose building inspection so you don't
have to pay the contractor $300 to do it for you.

Built for the [Call My Agent Hackathon](https://events.ycombinator.com/CallMyAgentHackathon).

## What it does

Your contractor replaced the gas water heater. The city needs to inspect it
before the permit closes. You can book it yourself at
[sjpermits.org](https://www.sjpermits.org) or by calling **(408) 535-3555** —
either way it's a chore. This agent does both.

## How it works

```
permit.json → Orchestrator → Browser Use (sjpermits.org)
                          ↘ AgentPhone voice (408-535-3555)   ← fallback
                                       ↓
                          AgentPhone SMS to homeowner
```

1. **Orchestrator** tries the cheap path first.
2. **Browser Use agent** opens sjpermits.org, enters your RSN, picks an
   inspection type and date, captures the confirmation #. If it hits a
   CAPTCHA or login wall, it returns `{"failed": true}`.
3. **AgentPhone voice agent** dials the city, navigates the IVR, talks
   to the scheduler, books the inspection, hangs up.
4. **AgentPhone SMS** texts you the confirmation.

## Setup

```bash
# Python 3.11+
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env   # fill in your API keys
# edit permit.json     # fill in your RSN, address, phone
```

The **RSN** (Rapid Service Number) is printed on your Permit Card — the PDF
the city emailed when the permit was issued. The City of San José docs say:
> "You will need your Customer Identification Number or Rapid Service Number
> (RSN), which is found on your Personal Information account page in
> SJPermits.org or on the Permit Record card."

## Run

```bash
python main.py
```

Watch the browser do its thing. If the online path fails, you'll hear the
phone call happen via AgentPhone. Either way, you get an SMS at the end.

## Files

| File | Purpose |
|---|---|
| `main.py` | Entry point |
| `orchestrator.py` | Routes browser → phone → SMS |
| `agents/browser_agent.py` | Browser Use, books on sjpermits.org |
| `agents/voice_agent.py` | AgentPhone outbound call to (408) 535-3555 |
| `agents/sms_agent.py` | AgentPhone SMS confirmation |
| `permit.json` | Your permit info (RSN, address, phone) |

## Caveats / next steps

- **Permit Card on-site.** The city still requires the printed Permit Card
  to be present at the inspection, and an adult at the property. The agent
  can't do that for you.
- **CAPTCHA.** sjpermits.org sometimes shows a CAPTCHA; that's exactly when
  the voice fallback earns its keep.
- **Verify the AgentPhone SDK shape.** This MVP targets the public SDK
  signature; double-check method names against your installed version.
- **Calendar invite.** Easy extension — add a `notify_agent` that creates a
  Google Calendar block for the AM or PM window.
- **Watch the contractor’s permit number.** Make sure the address matches
  before scheduling. The browser agent verifies this; the voice agent
  reads it back.
