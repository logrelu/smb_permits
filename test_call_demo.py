"""Demo: agent calls your iPhone, plays the homeowner; you roleplay the city scheduler.

Ask the agent for: RSN, address, owner name, inspection type. Offer a slot.
Give it a fake confirmation number. The agent should repeat back to confirm.

Set TEST_PHONE in your .env to the number the agent should dial.
"""
import asyncio
import os
from datetime import date, timedelta
from dotenv import load_dotenv
load_dotenv()

from agents.voice_agent import call_to_book

TARGET = os.environ["TEST_PHONE"]

permit = {
    "rsn": "247389",
    "address": "1234 Example St, San Jose, CA 95113",
    "owner_name": "Jane Doe",
    "phone": "+14085551234",
    "inspection_type": "Plumbing - Gas Water Heater Final",
}

desired_date = (date.today() + timedelta(days=3)).isoformat()
print(f"Calling {TARGET} — target inspection date: {desired_date}")
print("Pick up the phone and roleplay the city scheduler.\n")

result = asyncio.run(call_to_book(permit, desired_date, target_number=TARGET))
print("\n--- result ---")
for k, v in result.items():
    print(f"{k}: {v}")
