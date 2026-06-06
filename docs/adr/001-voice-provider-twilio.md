# ADR-001: Voice Provider — Twilio Media Streams

**Status:** Accepted

## Context
We need PSTN inbound calls with low-latency bidirectional audio to our backend.

## Decision
Use **Twilio Programmable Voice** with **Media Streams** (`<Connect><Stream>`).

## Rationale
- No SIP infrastructure to operate
- WebSocket audio fits FastAPI natively
- Signature validation for webhook security

## Alternatives considered
Vonage, Telnyx — viable but Twilio has the best documented Media Streams examples.
