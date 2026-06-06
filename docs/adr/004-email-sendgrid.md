# ADR-004: Email — SendGrid (Tier 3)

**Status:** Accepted

## Context
Visual diagnosis requires sending a unique upload link during a live call.

## Decision
**SendGrid** transactional email via REST API.

## Rationale
- Simple HTML email with upload link
- Free tier sufficient for demo
- Failures logged; voice agent informs caller if send fails

## Alternatives considered
AWS SES — more setup; SendGrid faster for take-home scope.
