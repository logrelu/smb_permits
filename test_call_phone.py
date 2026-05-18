"""Smoke-test the voice agent by calling a personal phone, not the city line.

Set TEST_PHONE in your .env to the number the agent should dial.
"""
import asyncio
import os
import threading
import time
from dotenv import load_dotenv
load_dotenv()

from agentphone import AgentPhone
from agents.voice_agent import _stream_transcript

TARGET = os.environ["TEST_PHONE"]

client = AgentPhone(api_key=os.environ["AGENTPHONE_API_KEY"])

topic = (
    "You are roleplaying calling a homeowner to pretend-schedule a building "
    "inspection. Greet them, ask if 9 AM Friday works, accept whatever they "
    "say, repeat the date back, give a fake confirmation number, and hang up."
)

call = client.calls.make_conversation(
    agent_id=os.environ["AGENTPHONE_AGENT_ID"],
    to_number=TARGET,
    topic=topic,
    initial_greeting="Hi, this is a test call from the SJ Inspect Agent. Can you hear me?",
)
call_id = call.id
print(f"📞 Call initiated: {call_id}")

threading.Thread(
    target=_stream_transcript,
    args=(client, call_id),
    daemon=True,
).start()

for _ in range(60):
    time.sleep(5)
    snap = client.calls.get(call_id)
    status = getattr(snap, "status", "unknown")
    print(f"   status: {status}")
    if status in ("completed", "ended", "failed", "no_answer", "busy"):
        break

print("\n--- final transcript ---")
print(client.calls.get_transcript(call_id))
