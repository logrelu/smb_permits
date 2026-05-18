"""Demo orchestrator — full 5-step contractor-to-inspection flow.

  Step 1: Contractor's iMessage (simulated via CLI inputs below).
  Step 2: Browser Use navigates sjpermits.org wizard, identifies permit category.
  Step 3: Agent calls City roleplay → receives RSN + permit number.
  Step 4: Agent iMessages owner with permit info and proposed availability.
  Step 5: Agent calls City roleplay → schedules inspection → confirmation iMessage.

For the demo, contractor_phone and owner_phone point at the same iPhone (TEST_PHONE).
The 'iMessage' from contractor is simulated by the dict below — in production this
would arrive via an AgentPhone inbound-message webhook.
"""
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from agents.browser_agent import navigate_permit_wizard
from agents.voice_agent import call_to_pull_permit, call_to_schedule_inspection
from agents.sms_agent import send_confirmation


def banner(text: str) -> None:
    print("\n" + "═" * 64)
    print(f"  {text}")
    print("═" * 64)


async def run_full_flow(contractor: dict, owner_phone: str) -> None:
    banner("STEP 1 · CONTRACTOR REQUEST RECEIVED")
    print(f"  📱 From: {contractor['phone']}")
    print(f"  📝 'License {contractor['license']} — {contractor['work_type']} at {contractor['address']}. Please pull a permit.'")

    send_confirmation(
        contractor["phone"],
        f"Got it — pulling a permit for {contractor['work_type']} at {contractor['address']}. Standby.",
    )

    banner("STEP 2 · BROWSER USE → SJPERMITS WIZARD")
    try:
        wizard_result = await asyncio.wait_for(
            navigate_permit_wizard(contractor["license"], contractor["work_type"], contractor["address"]),
            timeout=240,
        )
        print(f"  🌐 Wizard result: {wizard_result}")
    except Exception as e:
        print(f"  ⚠ Wizard step failed (continuing with known categorization): {e}")
        wizard_result = "CATEGORIZED: group=Building | type=1&2 Family | sub=Single-Family | work=Simple Mech/Plumb/Elec"

    banner("STEP 3 · AGENT CALLS CITY → PULL PERMIT")
    pull = await call_to_pull_permit(
        license_num=contractor["license"],
        address=contractor["address"],
        work_type=contractor["work_type"],
    )
    if not pull["success"]:
        print("  ✗ Permit pull failed.")
        send_confirmation(contractor["phone"], "Permit pull failed. Please retry later.")
        return
    rsn, permit_number = pull["rsn"], pull["permit_number"]
    print(f"  ✓ RSN: {rsn}  |  Permit#: {permit_number}")
    send_confirmation(
        contractor["phone"],
        f"Permit pulled.\nRSN: {rsn}\nPermit #: {permit_number}\nI'll now coordinate the inspection with the homeowner.",
    )

    banner("STEP 4 · COORDINATE WITH OWNER")
    owner_availability = ["Thursday morning", "Friday morning"]
    print(f"  💬 Owner availability (demo-hardcoded): {owner_availability}")
    send_confirmation(
        owner_phone,
        f"Hi! Your gas water heater permit is issued (RSN {rsn}). "
        f"I'll book the inspection in your preferred window: "
        f"{' or '.join(owner_availability)}. Calling the city now…",
    )

    banner("STEP 5 · AGENT CALLS CITY → SCHEDULE INSPECTION")
    sched = await call_to_schedule_inspection(
        rsn=rsn,
        permit_number=permit_number,
        availability=owner_availability,
        inspection_type=contractor["work_type"],
    )
    if not sched["success"]:
        print("  ✗ Scheduling failed.")
        send_confirmation(owner_phone, "Inspection scheduling failed. We'll retry shortly.")
        return
    confirmation = sched["confirmation"]
    print(f"  ✓ Confirmation #: {confirmation}")

    send_confirmation(
        owner_phone,
        f"✓ Inspection booked!\n"
        f"Confirmation #: {confirmation}\n"
        f"Window: Thursday morning\n\n"
        f"Reminder: an adult must be home, the permit card must be visible, "
        f"and the inspector will need access to the garage.",
    )
    send_confirmation(
        contractor["phone"],
        f"Inspection booked. Confirmation #{confirmation}. Owner notified.",
    )

    banner("🎉 DEMO COMPLETE")


if __name__ == "__main__":
    test_phone = os.environ["TEST_PHONE"]

    contractor_msg = {
        "phone": test_phone,
        "license": "1024356",
        "work_type": "Water heater replacement",
        "address": "1234 Example St, San Jose, CA 95113",
    }
    owner_phone = test_phone

    asyncio.run(run_full_flow(contractor_msg, owner_phone))
