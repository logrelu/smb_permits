"""Workflow brain.

Strategy (cheap → expensive):
  1) Browser Use opens sjpermits.org and books the inspection.
  2) On failure / CAPTCHA / login wall, fall back to an AgentPhone voice
     agent calling the SJ Building Division line (408) 535-3555.
  3) Either way, AgentPhone SMS pings the homeowner the confirmation.
"""
import asyncio
import json
import re

from agents.browser_agent import book_online
from agents.voice_agent import call_to_book
from agents.sms_agent import send_confirmation


async def book_inspection(permit: dict, desired_date: str) -> str:
    summary = None

    # ── Path A: Browser Use ─────────────────────────────────────────────
    print("🌐 Trying online booking via Browser Use…")
    try:
        raw = await asyncio.wait_for(
            book_online(permit, desired_date),
            timeout=300,
        )
        parsed = _extract_json(raw)
        if parsed and not parsed.get("failed"):
            summary = (
                f"{parsed['scheduled_date']} ({parsed['time_window']}) "
                f"— conf# {parsed['confirmation_number']}"
            )
            print(f"   ✓ Online booking succeeded: {summary}")
    except Exception as e:
        print(f"   ✗ Browser path failed: {e}")

    # ── Path B: AgentPhone voice fallback ───────────────────────────────
    if summary is None:
        print("📞 Falling back to AgentPhone voice agent…")
        result = await call_to_book(permit, desired_date)
        if not result.get("scheduled"):
            raise RuntimeError(
                f"Both online and phone booking failed.\n"
                f"Last transcript snippet:\n{result.get('transcript', '')[:500]}"
            )
        summary = result["confirmation"]
        print(f"   ✓ Phone booking succeeded: {summary}")

    # ── SMS the homeowner ───────────────────────────────────────────────
    print("💬 Sending SMS confirmation…")
    send_confirmation(permit["phone"], summary)

    return summary


def _extract_json(raw) -> dict | None:
    """Browser Use returns a string; find the JSON blob inside it."""
    s = str(raw)
    m = re.search(r"\{[^{}]*\}", s, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
