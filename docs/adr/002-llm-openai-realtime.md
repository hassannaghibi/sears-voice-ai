# ADR-002: LLM — OpenAI Realtime API

**Status:** Accepted

## Context
Voice agents traditionally chain STT → LLM → TTS, adding latency and state complexity.

## Decision
Use **OpenAI Realtime API** (`gpt-4o-realtime-preview`) over a single WebSocket.

## Rationale
- Unified audio + tool calling in one session
- `server_vad` turn detection
- Function tools map directly to scheduling services

## Tradeoff
Vendor lock-in and per-minute cost; acceptable for this assignment scope.
