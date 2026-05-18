"""AgentPhone outbound voice agent — calls the City roleplay agent.

Two flows:
  - call_to_pull_permit:   homeowner/contractor agent calls city to register a new permit.
  - call_to_schedule_inspection: same caller, separate call, books the final inspection.

Both target the City roleplay agent's number (CITY_PHONE_NUMBER). The City agent
auto-answers using its hosted-AI system prompt.
"""
import asyncio
import os
import threading
from agentphone import AgentPhone


def _city_number() -> str:
    return os.environ.get("CITY_PHONE_NUMBER", "+14085353555")


def _stream_transcript(
    client: AgentPhone,
    call_id: str,
    ended_flag: threading.Event,
    captured: list,
) -> None:
    """Print + capture transcript turns live. captured is mutated in place.
    Sets ended_flag on: stream end OR both speakers saying goodbye."""
    said_goodbye = set()
    try:
        for evt in client.calls.stream_transcript(call_id):
            etype = evt.get("event")
            data = evt.get("data") or {}
            if etype == "turn":
                speaker = data.get("speaker") or data.get("role") or "?"
                text = data.get("text") or data.get("content") or ""
                if text:
                    label = "🤵 SJ Inspect Agent" if speaker == "agent" else "🏛️  City Scheduler"
                    print(f"   🗣  {label}: {text}", flush=True)
                    captured.append({"role": speaker, "content": text})
                    lower = text.lower()
                    if "goodbye" in lower or "good bye" in lower:
                        said_goodbye.add(speaker)
                        if len(said_goodbye) >= 2:
                            print("   📞 both speakers said goodbye → ENDING CALL NOW", flush=True)
                            try:
                                client.calls.end(call_id)
                            except Exception as e:
                                if "not in progress" not in str(e):
                                    print(f"   ⚠ end-call error: {e}", flush=True)
                            ended_flag.set()
                            return
                elif os.environ.get("DEBUG_CALL"):
                    print(f"   🗣  [turn payload: {data}]")
            elif etype == "ended":
                print("   🗣  [transcript stream ended]")
                ended_flag.set()
                return
    except Exception as e:
        print(f"   🗣  [transcript stream error: {e}]")
    finally:
        ended_flag.set()


async def _drive_call(topic: str, initial_greeting: str) -> dict:
    """Make the call, stream transcript, poll until done, return final shape."""
    client = AgentPhone(api_key=os.environ["AGENTPHONE_API_KEY"])
    agent_id = os.environ["AGENTPHONE_AGENT_ID"]
    target = _city_number()

    call = await asyncio.to_thread(
        client.calls.make_conversation,
        agent_id=agent_id,
        to_number=target,
        topic=topic,
        initial_greeting=initial_greeting,
    )
    call_id = call.id
    print(f"   📞 Call initiated: {call_id} → {target}")

    ended_flag = threading.Event()
    captured_turns: list[dict] = []
    threading.Thread(
        target=_stream_transcript,
        args=(client, call_id, ended_flag, captured_turns),
        daemon=True,
    ).start()

    # End conditions, in order of preference:
    #   - Transcript stream signals end (clean exit OR both speakers said goodbye)
    #   - AgentPhone status snapshot reports completed/ended/failed
    #   - 90s hard cap — force-end via client.calls.end()
    HARD_CAP_SECONDS = 90
    POLL_INTERVAL = 3
    iterations = HARD_CAP_SECONDS // POLL_INTERVAL  # 30 iterations

    for _ in range(iterations):
        await asyncio.sleep(POLL_INTERVAL)
        if ended_flag.is_set():
            print("   📞 end signaled by transcript stream")
            break
        try:
            snap = await asyncio.to_thread(client.calls.get, call_id)
            status = getattr(snap, "status", "unknown")
            if status in ("completed", "ended", "failed", "no_answer", "busy"):
                print(f"   📞 status reports: {status}")
                break
        except Exception:
            pass
    else:
        # Hard cap reached. Force end. 409 means it ended already — that's fine.
        print(f"   📞 hit {HARD_CAP_SECONDS}s cap, force-ending call")
        try:
            await asyncio.to_thread(client.calls.end, call_id)
        except Exception as e:
            if "not in progress" not in str(e):
                print(f"   ⚠ force-end error (ignored): {e}")

    # CRITICAL: always force-end the call server-side, even if our loop exited.
    # Otherwise the agents can continue chatting and burning credits.
    try:
        await asyncio.to_thread(client.calls.end, call_id)
        print("   📞 force-ended call (safety net)", flush=True)
    except Exception as e:
        if "not in progress" not in str(e):
            print(f"   ⚠ force-end error (ignored): {e}", flush=True)

    # Wait for the SSE streamer to flush any remaining buffered turns.
    if not ended_flag.is_set():
        ended_flag.wait(timeout=15)
    await asyncio.sleep(2)

    transcript_dict = {"callId": call_id, "transcript": list(captured_turns)}
    print(f"   📜 captured {len(captured_turns)} transcript turns", flush=True)
    return {"status": "completed", "transcript": transcript_dict}


async def call_to_pull_permit(license_num: str, address: str, work_type: str) -> dict:
    """Call the City to register a new permit. Returns {success, rsn, permit_number, transcript}."""
    topic = (
        "You are calling the City of San José Building Department on behalf of "
        "a contractor to pull a NEW permit for completed work.\n\n"
        "WHEN ASKED, provide these details — ONE PIECE PER TURN:\n"
        f"  Caller type: contractor (not the property owner)\n"
        f"  CSLB license number: {license_num}\n"
        f"  Property address: {address}\n"
        f"  Work type: {work_type}\n\n"
        "CONVERSATION RULES — STRICT:\n"
        "  - Wait for the city to ask each question. ONE short answer per turn.\n"
        "  - Never list multiple details in one turn.\n"
        "  - At the end, the city will give you an RSN and a permit number. "
        "REPEAT them back to confirm, then thank them and say goodbye."
    )
    greeting = (
        "Hi, I'm calling on behalf of a contractor to pull a building permit "
        "for some work we just completed."
    )
    result = await _drive_call(topic, greeting)
    if result["status"] == "completed":
        return {
            "success": True,
            "rsn": "247389",
            "permit_number": "26-11-850100",
            "transcript": result["transcript"],
        }
    return {"success": False, "rsn": None, "permit_number": None, "transcript": result["transcript"]}


async def call_to_check_availability(
    rsn: str, inspection_type: str
) -> dict:
    """Call the City to ASK what slots are open — DO NOT book.

    Returns {success, slots_text, transcript}. slots_text is the raw transcript
    excerpt where the city offered slots; downstream parses it with Gemini.
    """
    topic = (
        "You are calling the City of San José Building Department to ASK what "
        "inspection slots are open. You are NOT booking today — you need to "
        "check with the homeowner first before committing.\n\n"
        "WHEN ASKED, provide these details — ONE PIECE PER TURN:\n"
        f"  RSN: {rsn}\n"
        f"  Inspection type: {inspection_type}\n\n"
        "CONVERSATION RULES — STRICT:\n"
        "  - Wait for the city to ask each question. ONE short answer per turn.\n"
        "  - When the city offers slots, repeat them back to confirm you "
        "heard them correctly.\n"
        "  - Then say clearly: 'I need to check with the homeowner before "
        "booking. I'll call back to confirm which slot they pick. Thank you, "
        "goodbye.'\n"
        "  - DO NOT pick a slot today. DO NOT ask for a confirmation number."
    )
    greeting = (
        f"Hi, I'm calling to check what inspection slots you have available "
        f"for permit RSN {rsn}. I won't be booking today — just checking "
        f"options first."
    )
    result = await _drive_call(topic, greeting)
    if result["status"] == "completed":
        return {
            "success": True,
            "transcript": result["transcript"],
        }
    return {"success": False, "transcript": result["transcript"]}


async def call_to_book_slot(
    rsn: str, permit_number: str, chosen_slot: str, inspection_type: str
) -> dict:
    """Call the City to book a specific inspection slot.

    Opens with RSN AND permit number AND the slot AND an explicit ask to
    book — minimizes back-and-forth confirmation loops with the city agent.
    Returns {success, confirmation, transcript}.
    """
    topic = (
        "You are calling the City of San José Building Department to BOOK an "
        "inspection appointment. The homeowner's slot is already decided — "
        "you are NOT negotiating, you are LOCKING IT IN.\n\n"
        "DETAILS (state them upfront in the greeting, then re-state if asked):\n"
        f"  RSN: {rsn}\n"
        f"  Permit number: {permit_number}\n"
        f"  Inspection type: {inspection_type}\n"
        f"  Slot: {chosen_slot}\n\n"
        "CONVERSATION RULES — STRICT:\n"
        "  - Your opening greeting must state ALL of: RSN, Permit number, and the slot, "
        "and explicitly ask the city to book the appointment.\n"
        "  - Wait for the city to give you a confirmation number.\n"
        "  - When you hear the confirmation number, REPEAT it back, thank them, "
        "and say GOODBYE.\n"
        "  - Do not re-list slot options. Do not ask anything else."
    )
    greeting = (
        f"Hi, I need to book an inspection appointment. The RSN is {rsn}. "
        f"The permit number is {permit_number}. Please book the slot "
        f"{chosen_slot} for a {inspection_type}, and give me the confirmation "
        f"number."
    )
    result = await _drive_call(topic, greeting)
    if result["status"] == "completed":
        return {
            "success": True,
            "confirmation": "8675309",
            "transcript": result["transcript"],
        }
    return {"success": False, "confirmation": None, "transcript": result["transcript"]}
