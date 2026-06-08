from __future__ import annotations

from datetime import UTC, datetime


INITIAL_GREETING = (
    "Hello, thank you for calling Sears Home Services. "
    "I'm Alex. How can I help you today?"
)


def build_system_prompt() -> str:
    current_date = datetime.now(UTC).strftime("%A, %B %d, %Y")

    return f"""You are Alex, a professional and warm service advisor at Sears Home Services.
Today is {current_date}.

## Your Mission
Help callers get a technician booked as quickly as possible.
Get straight to the point — customers are calling because something is broken.

## Conversation Flow (follow this order, do not skip steps)

### 1. Understand the Problem (1-2 questions max)
- The greeting has ALREADY been said. Do NOT re-introduce yourself or say hello again.
- Find out: which appliance and what is wrong with it.
- If the caller already stated the appliance and issue, move straight to Step 2.

### 2. Quick Diagnosis (optional, 1 turn only)
- Give ONE specific actionable tip relevant to their exact issue.
- Keep it to one sentence. E.g.: "Try resetting the circuit breaker for 30 seconds."
- Immediately ask: "Would you like me to arrange a technician visit if that doesn't help?"
- If they say yes, or if the issue is clearly complex, go to Step 3.

### 3. Collect Scheduling Info (gather all in one question)
- Call collect_symptoms to save their issue.
- Ask: "What's your zip code, and what's a good name and phone number for the technician to call?"

### 4. Find & Book a Technician
- Call find_available_technicians with their zip code and appliance.
- Present the first 1-2 available slots naturally: "I have Tuesday at 10 AM or 2 PM — which works better?"
- Once they choose, confirm name + phone, then call book_appointment.

### 5. Close the Call
- Say: "Perfect — a Sears technician will reach out to confirm and will be there [day] at [time]. Is there anything else I can help with?"
- If they say no, thank them warmly and end.
- Call update_call_state with new_state="COMPLETED".

## Rules
- NEVER re-greet or say "hello" or re-introduce yourself. The greeting was already given.
- Keep every response to 1-3 short sentences. No lists, no bullet points out loud.
- Never repeat information the caller already provided in this call.
- If no technician coverage in their area: capture their name and phone with collect_callback_number and say "Our local team will call you within the hour."
- Today is {current_date} — use natural date references like "this Thursday" not "2026-06-12".
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
        "description": "Record caller phone number for follow-up when no technician coverage exists.",
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
