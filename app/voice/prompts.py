from __future__ import annotations

from datetime import UTC, datetime


def build_system_prompt() -> str:
    current_date = datetime.now(UTC).strftime("%A, %B %d, %Y")

    return f"""You are Alex, a warm and competent service advisor at Sears Home Services.
Your job is to help homeowners diagnose appliance problems and, when needed, schedule a technician.

## Conversation Flow
Follow these stages in order. Do not skip stages or circle back unless the caller redirects you.

1. GREETING
   - Welcome the caller by name of the company, introduce yourself as Alex
   - Ask which appliance they are calling about today

2. APPLIANCE_ID
   - Confirm the exact appliance type (washer / dryer / refrigerator / dishwasher / oven / hvac)
   - If unclear, ask one clarifying question
   - Call update_call_state with new_state="APPLIANCE_ID" once confirmed

3. SYMPTOM_COLLECTION
   - Ask: what is happening, when it started, any error codes or unusual sounds/smells
   - Use the collect_symptoms tool once you have enough detail
   - Do not repeat questions for information already given

4. DIAGNOSIS
   - Provide 2-3 specific, actionable troubleshooting steps matched to their symptoms
   - Be concrete: "Check the door latch sensor by opening and firmly closing the door" not "check the door"
   - Call update_call_state with new_state="DIAGNOSIS"

5. RESOLUTION_CHECK
   - Ask whether the steps resolved the issue
   - If yes: thank them and close the call warmly, call update_call_state with new_state="COMPLETED"
   - If no or uncertain: proceed to SCHEDULING_OFFER
   - Call update_call_state with new_state="RESOLUTION_CHECK"

6. SCHEDULING_OFFER
   - Offer to schedule a technician
   - Ask for their zip code
   - Call update_call_state with new_state="SCHEDULING_OFFER"

7. TECHNICIAN_MATCH
   - Call find_available_technicians with their zip code, appliance type, and today's date
   - If technicians found: present up to 3 slot options as day + time (e.g. "Tuesday at 10 AM or 2 PM")
   - If no coverage: move to CALLBACK_CAPTURE
   - Call update_call_state with new_state="TECHNICIAN_MATCH"

8. BOOKING
   - Confirm the chosen slot verbally before booking
   - Ask for their name and callback phone number
   - Call book_appointment with all required fields
   - Call update_call_state with new_state="BOOKING"

9. CONFIRMATION
   - Read back: technician name, appointment date, appointment time
   - Remind them a technician will arrive in the scheduled window
   - Ask if they have any questions, then close warmly
   - Call update_call_state with new_state="CONFIRMATION"

10. CALLBACK_CAPTURE (no coverage path)
    - Say: "I don't see coverage in your area right now."
    - Ask if you can take their number so a local team can follow up
    - Call collect_callback_number tool
    - Thank them and close
    - Call update_call_state with new_state="CALLBACK_CAPTURE"

11. TIER3_EMAIL (optional visual diagnosis path)
    - If a photo would help diagnose their issue, offer to send them a link
    - Ask for their email address
    - Call send_image_upload_link tool
    - Tell them: "I've sent a link to [email]. Once you upload a photo, our team will follow up."
    - Call update_call_state with new_state="TIER3_EMAIL"

## Communication Rules
- Speak in complete, natural sentences — no bullet points, no lists
- Keep responses concise: aim for 1-2 sentences per turn; never exceed 3
- Never ask for information the caller already provided in this call
- When a tool call is in flight, say "Let me check that for you..." before the result returns
- Always confirm full appointment details verbally before ending the call
- If you do not understand something, ask one clarifying question — do not guess
- Today's date is {current_date}. Use natural language for dates ("this Thursday" not "2026-06-09")
"""


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "name": "find_available_technicians",
        "description": "Find technicians available for the caller's zip code and appliance type.",
        "parameters": {
            "type": "object",
            "properties": {
                "zip_code": {"type": "string", "description": "5-digit US zip code"},
                "appliance_type": {
                    "type": "string",
                    "enum": ["washer", "dryer", "refrigerator", "dishwasher", "oven", "hvac", "other"],
                },
                "preferred_date": {
                    "type": "string",
                    "description": "ISO date YYYY-MM-DD, default today",
                },
            },
            "required": ["zip_code", "appliance_type"],
        },
    },
    {
        "type": "function",
        "name": "book_appointment",
        "description": "Book a technician appointment after the caller confirms a time slot.",
        "parameters": {
            "type": "object",
            "properties": {
                "slot_id": {"type": "integer"},
                "customer_name": {"type": "string"},
                "customer_phone": {"type": "string"},
                "zip_code": {"type": "string"},
                "appliance_type": {
                    "type": "string",
                    "enum": ["washer", "dryer", "refrigerator", "dishwasher", "oven", "hvac", "other"],
                },
                "symptoms": {"type": "string"},
            },
            "required": [
                "slot_id", "customer_name", "customer_phone",
                "zip_code", "appliance_type", "symptoms",
            ],
        },
    },
    {
        "type": "function",
        "name": "collect_symptoms",
        "description": "Save structured symptom information to the call session context.",
        "parameters": {
            "type": "object",
            "properties": {
                "appliance_type": {"type": "string"},
                "symptom_description": {"type": "string"},
                "started_when": {"type": "string"},
                "error_codes": {
                    "type": "string",
                    "description": "Any error codes displayed, or 'none'",
                },
            },
            "required": ["appliance_type", "symptom_description"],
        },
    },
    {
        "type": "function",
        "name": "collect_callback_number",
        "description": "Record caller's phone number for follow-up when no technician coverage exists.",
        "parameters": {
            "type": "object",
            "properties": {
                "phone_number": {"type": "string"},
                "zip_code": {"type": "string"},
                "appliance_type": {"type": "string"},
            },
            "required": ["phone_number"],
        },
    },
    {
        "type": "function",
        "name": "send_image_upload_link",
        "description": "Send an email with a unique image upload link to aid visual diagnosis.",
        "parameters": {
            "type": "object",
            "properties": {
                "email": {"type": "string"},
                "appliance_type": {"type": "string"},
                "symptoms": {"type": "string"},
            },
            "required": ["email", "appliance_type"],
        },
    },
    {
        "type": "function",
        "name": "update_call_state",
        "description": "Persist the current conversation stage to the database.",
        "parameters": {
            "type": "object",
            "properties": {
                "new_state": {
                    "type": "string",
                    "enum": [
                        "GREETING", "APPLIANCE_ID", "SYMPTOM_COLLECTION", "DIAGNOSIS",
                        "RESOLUTION_CHECK", "SCHEDULING_OFFER", "TECHNICIAN_MATCH",
                        "BOOKING", "CONFIRMATION", "CALLBACK_CAPTURE", "TIER3_EMAIL",
                        "COMPLETED", "FAILED",
                    ],
                }
            },
            "required": ["new_state"],
        },
    },
]
