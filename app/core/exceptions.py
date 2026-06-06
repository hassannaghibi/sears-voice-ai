from __future__ import annotations


class SearsBaseError(Exception):
    """Base exception for all Sears Voice API errors."""


class SlotNotAvailableError(SearsBaseError):
    """Raised when a slot is already booked. Maps to HTTP 409."""

    def __init__(self, slot_id: int | None = None) -> None:
        msg = f"Slot {slot_id} is no longer available." if slot_id else "Slot is no longer available."
        super().__init__(msg)
        self.slot_id = slot_id


class NotFoundError(SearsBaseError):
    """Raised when a requested resource does not exist. Maps to HTTP 404."""

    def __init__(self, resource: str = "Resource", resource_id: int | str | None = None) -> None:
        msg = f"{resource} '{resource_id}' not found." if resource_id else f"{resource} not found."
        super().__init__(msg)
        self.resource = resource
        self.resource_id = resource_id


class ValidationError(SearsBaseError):
    """Raised for domain-level validation failures. Maps to HTTP 422."""
