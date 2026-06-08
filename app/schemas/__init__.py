from app.schemas.appointment import AppointmentCreate, AppointmentResponse, AppointmentStatusUpdate
from app.schemas.common import ErrorDetail, PaginatedResponse
from app.schemas.slot import SlotResponse
from app.schemas.technician import TechnicianResponse, TechnicianWithAvailability

__all__ = [
    "ErrorDetail",
    "PaginatedResponse",
    "SlotResponse",
    "TechnicianResponse",
    "TechnicianWithAvailability",
    "AppointmentCreate",
    "AppointmentResponse",
    "AppointmentStatusUpdate",
]
