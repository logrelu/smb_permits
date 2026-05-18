"""Inbound iMessage listener — multi-turn conversational agent + multi-stage pipeline.

Stages, per phone number (CONVERSATIONS dict):
  "gathering_contractor"  — chatting with contractor to collect license/work/address
  "running_pipeline"      — Steps 2-4 firing in the background (browser, permit-pull, availability check)
  "awaiting_owner_choice" — waiting for owner's iMessage reply choosing one of the offered slots
  "done"                  — pipeline finished

For the demo, contractor and owner share TEST_PHONE — but logically they are
separate roles. The conversation `stage` determines how a new iMessage is
interpreted.
"""
import asyncio
import json
import logging
import os
from dotenv import load_dotenv
load_dotenv()

# Quiet down browser-use's noisy INFO logs in the demo output.
logging.getLogger("browser_use").setLevel(logging.WARNING)
logging.getLogger("Agent").setLevel(logging.WARNING)
logging.getLogger("BrowserSession").setLevel(logging.WARNING)
logging.getLogger("tools").setLevel(logging.WARNING)
logging.getLogger("service").setLevel(logging.WARNING)
logging.getLogger("bubus").setLevel(logging.WARNING)
logging.getLogger("cdp_use.client").setLevel(logging.WARNING)

from google import genai
from pydantic import BaseModel
from agentphone import AgentPhone

from agents.browser_agent import navigate_permit_wizard
from agents.sms_agent import send_message
from agents.voice_agent import (
    call_to_pull_permit,
    call_to_check_availability,  # unused in simplified flow; kept for future
    call_to_book_slot,
)

# Simplified flow: we assume the owner's availability rather than asking each time.
ASSUMED_SLOT = "Thursday, May 21, 8 AM to 12 PM"

IMSG_NUMBER_ID = os.environ["AGENTPHONE_NUMBER_ID"]
OWNER_PHONE = os.environ.get("TEST_PHONE")

# Friendly aliases so phone numbers don't leak into the demo output.
_PHONE_LABELS = {
    "+17578314612": "iMessage line",
    "+17622254598": "City",
    "+16183531563": "Inspect Agent",
}
if OWNER_PHONE:
    _PHONE_LABELS[OWNER_PHONE] = "Contractor"  # same phone plays both roles in demo


def alias(phone: str, stage: str = "") -> str:
    if phone == OWNER_PHONE and stage == "awaiting_owner_choice":
        return "Owner"
    return _PHONE_LABELS.get(phone, "Contractor" if phone == OWNER_PHONE else phone)

_gemini = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
_GEMINI_MODEL = "gemini-flash-latest"


class ContractorState(BaseModel):
    intent: str | None = None
    license_number: str | None = None
    work_type: str | None = None
    address: str | None = None


class ContractorTurn(BaseModel):
    state: ContractorState
    reply: str
    is_complete: bool


class SlotOptions(BaseModel):
    slot_a: str | None = None    # e.g. "Thursday May 21 morning, 8 AM to 12 PM"
    slot_b: str | None = None
    raw: str | None = None       # any extra slot text


class SlotChoice(BaseModel):
    chosen_slot: str | None = None  # whichever slot the owner picked, in plain English
    is_clear: bool                  # true if the choice was unambiguous


CONVERSATIONS: dict[str, dict] = {}


_CONTRACTOR_SYSTEM = """You are an SMS assistant for the SJ Building Permit office. You're texting with a contractor over iMessage.

Your job is to gather three things from them to pull a permit:
  1. CSLB license number (digits)
  2. Work type (e.g. "gas water heater replacement", "furnace install")
  3. Property address (street + city, San Jose by default)

Conversation rules:
  - Reply ONE friendly, short sentence (under 25 words). Like a text from a human assistant, not a form.
  - If they say hi / hello, greet back briefly and ask what they need.
  - If they want a permit but are missing fields, ask for ONE missing field, not all three at once.
  - Don't ask for info they already gave. Update state from each message.
  - Once you have intent=pull_permit AND all three fields, set is_complete=true and reply with a quick "Got it, pulling the permit now — I'll text you the RSN in a minute." style message.
  - If the message is unrelated, gently steer back ("I can help with permits — what are you working on?").

Return a ContractorTurn: updated state, the reply text, and is_complete.
"""


async def contractor_turn(phone: str, body: str) -> ContractorTurn:
    conv = CONVERSATIONS[phone]
    conv["history"].append({"role": "contractor", "content": body})

    history_text = "\n".join(f"{m['role']}: {m['content']}" for m in conv["history"])
    user_block = (
        f"Current known state (may be partial):\n{conv['state'].model_dump_json()}\n\n"
        f"Conversation so far:\n{history_text}\n\n"
        f"Generate the next ContractorTurn."
    )

    resp = await asyncio.to_thread(
        _gemini.models.generate_content,
        model=_GEMINI_MODEL,
        contents=[{"role": "user", "parts": [{"text": _CONTRACTOR_SYSTEM + "\n\n" + user_block}]}],
        config={"response_mime_type": "application/json", "response_schema": ContractorTurn},
    )
    result = ContractorTurn.model_validate_json(resp.text)
    conv["state"] = result.state
    conv["history"].append({"role": "agent", "content": result.reply})
    return result


_SLOTS_SYSTEM = """Extract the two inspection slots the city offered from a voice-call transcript. The slots may be uttered by the city directly, OR repeated back by the caller to confirm — either form counts. A typical phrasing is "Thursday May 21 morning, 8 AM to 12 PM, or Friday May 22 afternoon, 1 PM to 5 PM."

Return SlotOptions with slot_a and slot_b as natural-language descriptions (e.g. "Thursday May 21, 8 AM – 12 PM"). If only one slot is mentioned, leave slot_b null. raw can contain any extra detail.
"""


async def extract_slots_from_transcript(transcript: dict | None) -> SlotOptions:
    if not transcript or not transcript.get("transcript"):
        return SlotOptions()
    turns = transcript["transcript"]
    # Use the FULL transcript — slots may be uttered by city OR repeated by agent.
    full_text = "\n".join(f"{t.get('role','?')}: {t.get('content','')}" for t in turns)
    if not full_text.strip():
        return SlotOptions()
    resp = await asyncio.to_thread(
        _gemini.models.generate_content,
        model=_GEMINI_MODEL,
        contents=[{"role": "user", "parts": [{"text": _SLOTS_SYSTEM + "\n\nFull transcript:\n" + full_text}]}],
        config={"response_mime_type": "application/json", "response_schema": SlotOptions},
    )
    return SlotOptions.model_validate_json(resp.text)


_CHOICE_SYSTEM = """The homeowner was offered two inspection slots and replied with their choice via iMessage. Determine which slot they picked.

Return SlotChoice with chosen_slot set to one of the two offered slots (in the same wording the city used), and is_clear=true if the homeowner unambiguously picked one. If they declined both or were ambiguous, is_clear=false.
"""


async def parse_owner_slot_choice(offered: SlotOptions, owner_message: str) -> SlotChoice:
    prompt = (
        _CHOICE_SYSTEM
        + f"\n\nSlot A: {offered.slot_a}\nSlot B: {offered.slot_b}\n\nHomeowner replied: {owner_message}"
    )
    resp = await asyncio.to_thread(
        _gemini.models.generate_content,
        model=_GEMINI_MODEL,
        contents=[{"role": "user", "parts": [{"text": prompt}]}],
        config={"response_mime_type": "application/json", "response_schema": SlotChoice},
    )
    return SlotChoice.model_validate_json(resp.text)


def banner(text: str) -> None:
    line = "─" * 60
    print(f"\n{line}\n  {text}\n{line}")


async def run_pipeline(contractor_phone: str, state: ContractorState) -> None:
    """Simplified end-to-end: wizard → permit-pull → book hardcoded slot → confirm."""
    conv = CONVERSATIONS[contractor_phone]

    # STEP 2: browser wizard
    banner("STEP 2 · BROWSER USE → SJPERMITS WIZARD")
    try:
        wizard = await asyncio.wait_for(
            navigate_permit_wizard(
                license_num=state.license_number,
                work_type=state.work_type,
                address=state.address,
            ),
            timeout=240,
        )
        print(f"  ✓ {wizard}", flush=True)
        send_message(contractor_phone, f"Found the permit category: {wizard}\n\nCalling the city to file now…")
    except Exception as e:
        print(f"  ⚠ wizard error (continuing): {e}", flush=True)
        send_message(contractor_phone, "Wizard had trouble — calling the city directly now.")

    # STEP 3: pull permit
    banner("STEP 3 · AGENT → CITY · PULL PERMIT")
    pull = await call_to_pull_permit(
        license_num=state.license_number,
        address=state.address,
        work_type=state.work_type,
    )
    if not pull["success"]:
        send_message(contractor_phone, "Couldn't reach the city to pull the permit. Try again later.")
        conv["stage"] = "done"
        return
    rsn, permit_number = pull["rsn"], pull["permit_number"]
    print(f"  ✓ RSN={rsn}  Permit#={permit_number}", flush=True)
    send_message(
        contractor_phone,
        f"Permit pulled.\nRSN: {rsn}\nPermit #: {permit_number}\n\nNow booking your inspection…",
    )

    # STEP 4: notify owner of upcoming booking (assumed slot)
    banner(f"STEP 4 · NOTIFYING OWNER · slot={ASSUMED_SLOT}")
    send_message(
        OWNER_PHONE,
        f"Hi! Your {state.work_type} permit is issued (RSN {rsn}). "
        f"Booking your inspection for: {ASSUMED_SLOT}. Calling the city now…",
    )

    # STEP 5: call city to book the assumed slot
    banner("STEP 5 · AGENT → CITY · BOOK SLOT")
    book = await call_to_book_slot(
        rsn=rsn,
        permit_number=permit_number,
        chosen_slot=ASSUMED_SLOT,
        inspection_type=state.work_type,
    )
    if not book["success"]:
        send_message(OWNER_PHONE, "Booking call didn't complete. Will retry shortly.")
        conv["stage"] = "done"
        return

    confirmation = book["confirmation"]
    print(f"  ✓ Confirmation #: {confirmation}", flush=True)
    send_message(
        OWNER_PHONE,
        f"✓ Inspection booked!\n"
        f"Slot: {ASSUMED_SLOT}\n"
        f"Confirmation #: {confirmation}\n\n"
        f"Reminder: an adult must be home, the permit card must be visible, "
        f"and the inspector will need access to the garage.",
    )
    send_message(
        contractor_phone,
        f"All done. Inspection booked — confirmation #{confirmation}. Owner notified.",
    )
    conv["stage"] = "done"
    banner("🎉 PIPELINE COMPLETE")


async def watch() -> None:
    c = AgentPhone(api_key=os.environ["AGENTPHONE_API_KEY"])

    seed = c.numbers.get_messages(IMSG_NUMBER_ID, limit=1)
    last_seen_id = seed.data[0].id if seed.data else None
    print(f"📥 Listening on iMessage line (number_id={IMSG_NUMBER_ID})")
    print(f"   Multi-turn + multi-stage pipeline. Seeded last_seen_id={last_seen_id}\n")

    while True:
        await asyncio.sleep(3)
        try:
            msgs = c.numbers.get_messages(IMSG_NUMBER_ID, limit=10)
        except Exception as e:
            print(f"   ⚠ poll error: {e}")
            continue

        new_inbound = []
        for m in msgs.data:
            if m.id == last_seen_id:
                break
            if m.direction == "inbound":
                new_inbound.append(m)
        if not new_inbound:
            continue

        for m in reversed(new_inbound):
            conv = CONVERSATIONS.setdefault(
                m.from_number,
                {"state": ContractorState(), "history": [], "stage": "gathering_contractor"},
            )
            # If the previous pipeline already finished for this phone, treat any
            # new inbound iMessage as the start of a fresh conversation.
            if conv["stage"] == "done":
                print(f"   🔄 previous pipeline complete — resetting for new conversation", flush=True)
                conv["state"] = ContractorState()
                conv["history"] = []
                conv["stage"] = "gathering_contractor"
            stage = conv["stage"]
            print(f"📩 {alias(m.from_number, stage)}: {m.body!r}", flush=True)
            print(f"   📋 stage={stage}", flush=True)

            try:
                if stage == "gathering_contractor":
                    result = await contractor_turn(m.from_number, m.body)
                    send_message(m.from_number, result.reply)
                    print(f"   🤖 reply: {result.reply!r}", flush=True)
                    print(f"   📋 state: {result.state.model_dump()}  complete={result.is_complete}", flush=True)
                    if result.is_complete:
                        conv["stage"] = "running_pipeline"
                        await run_pipeline(m.from_number, result.state)
                elif stage == "running_pipeline":
                    send_message(m.from_number, "Still working on the previous request — stand by.")
                else:
                    send_message(m.from_number, "Pipeline complete. Send a fresh request to start over.")
            except Exception as e:
                print(f"   ⚠ handler error: {e}", flush=True)
                send_message(m.from_number, f"Hit a snag: {e}")

        last_seen_id = msgs.data[0].id


if __name__ == "__main__":
    asyncio.run(watch())
