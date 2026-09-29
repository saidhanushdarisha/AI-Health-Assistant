from __future__ import annotations

import os
import uuid
from datetime import date as dt_date, datetime
from pathlib import Path
import pandas as pd
from langchain_core.tools import tool

from agents.appointment.data.data import (
    df_doctors,
    df_slots,
    CSV_SLOTS,
    CSV_BOOKINGS,
    BOOKING_COLUMNS,
    ensure_future_schedule,
)


def _reload_slots() -> pd.DataFrame:
    global df_slots
    ensure_future_schedule()
    df_slots = pd.read_csv(CSV_SLOTS).fillna("")
    df_slots["patient_name"] = df_slots["patient_name"].astype(str)
    return df_slots


def _save_slots(frame: pd.DataFrame) -> None:
    global df_slots
    frame.to_csv(CSV_SLOTS, index=False)
    df_slots = frame


def _parse_date(value: str) -> str | None:
    value = str(value or "").strip()
    if not value:
        return None
    formats = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d %m %Y"]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _slot_is_in_future(slot_date: str, time_slot: str) -> bool:
    """Return False for time slots that have already passed today."""
    try:
        slot_day = datetime.strptime(str(slot_date), "%Y-%m-%d").date()
        if slot_day > dt_date.today():
            return True
        if slot_day < dt_date.today():
            return False
        slot_time = datetime.strptime(str(time_slot).strip(), "%I:%M %p").time()
        now = datetime.now().time()
        return slot_time > now
    except ValueError:
        return False


def _load_bookings() -> pd.DataFrame:
    if not Path(CSV_BOOKINGS).exists():
        frame = pd.DataFrame(columns=BOOKING_COLUMNS)
        frame.to_csv(CSV_BOOKINGS, index=False)
        return frame
    frame = pd.read_csv(CSV_BOOKINGS).fillna("")
    for col in BOOKING_COLUMNS:
        if col not in frame.columns:
            frame[col] = ""
    return frame[BOOKING_COLUMNS]


@tool
def check_doctor_availability(department: str, date: str) -> str:
    """Show every open doctor/time slot for a department on a date.

    Date accepts YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY, or YYYY/MM/DD.
    """
    normalized_date = _parse_date(date)
    if not normalized_date:
        return "Availability check failed: please provide the date as YYYY-MM-DD (for example, 2026-10-01)."

    slots = _reload_slots()
    department_clean = department.strip()
    available = slots[
        (slots["department"].astype(str).str.lower() == department_clean.lower())
        & (slots["date"].astype(str) == normalized_date)
        & (slots["status"].astype(str).str.lower() == "available")
    ].copy()
    if not available.empty:
        available = available[available.apply(lambda r: _slot_is_in_future(r["date"], r["time_slot"]), axis=1)]

    if available.empty:
        today = dt_date.today().isoformat()
        if normalized_date < today:
            return (
                f"There are no appointments on {normalized_date}; that date has already passed. "
                f"Please choose today or a future date."
            )
        return f"No open {department_clean} slots were found on {normalized_date}. You can ask for the next available date."

    lines = [
        f"{row['doctor_name']} — {row['time_slot']} (slot {row['slot_id']})"
        for _, row in available.iterrows()
    ]
    return f"Available {department_clean} appointments for {normalized_date}:\n" + "\n".join(lines)


@tool
def find_next_available_slots(department: str, start_date: str = "", limit: int = 10) -> str:
    """Find the next available appointments for a department from a start date."""
    start = _parse_date(start_date) if start_date else dt_date.today().isoformat()
    if not start:
        start = dt_date.today().isoformat()

    slots = _reload_slots()
    available = slots[
        (slots["department"].astype(str).str.lower() == department.strip().lower())
        & (slots["status"].astype(str).str.lower() == "available")
        & (slots["date"].astype(str) >= start)
    ].copy()
    if not available.empty:
        available = available[available.apply(lambda r: _slot_is_in_future(r["date"], r["time_slot"]), axis=1)]
    available = available.sort_values(["date", "time_slot", "doctor_name"]).head(max(1, min(int(limit), 25)))

    if available.empty:
        return f"No future {department} appointments are currently available in the schedule."

    lines = [
        f"{row['date']} | {row['doctor_name']} | {row['time_slot']} | Slot {row['slot_id']}"
        for _, row in available.iterrows()
    ]
    return f"Next available {department} appointments:\n" + "\n".join(lines)


@tool
def book_hospital_appointment(
    patient_name: str, department: str, time_slot: str, date: str, patient_phone: str = ""
) -> str:
    """Book an available hospital appointment. Always verify availability first."""
    normalized_date = _parse_date(date)
    if not normalized_date:
        return "Booking failed: invalid date. Use YYYY-MM-DD."
    if normalized_date < dt_date.today().isoformat():
        return "Booking failed: the requested appointment date has already passed."
    if normalized_date == dt_date.today().isoformat() and not _slot_is_in_future(normalized_date, time_slot):
        return "Booking failed: the requested time has already passed today. Please choose a later slot."
    if not patient_name.strip():
        return "Booking failed: patient name is required."

    slots = _reload_slots()
    match = slots[
        (slots["department"].astype(str).str.lower() == department.strip().lower())
        & (slots["date"].astype(str) == normalized_date)
        & (slots["time_slot"].astype(str).str.strip().str.upper() == time_slot.strip().upper())
        & (slots["status"].astype(str).str.lower() == "available")
    ]

    if match.empty:
        return (
            f"Booking failed: {time_slot} on {normalized_date} is not available for {department}. "
            "Please check availability again."
        )

    idx = match.index[0]
    doctor_assigned = str(slots.at[idx, "doctor_name"])
    slot_id = str(slots.at[idx, "slot_id"])
    appointment_id = f"APT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    slots.at[idx, "status"] = "Booked"
    slots.at[idx, "patient_name"] = patient_name.strip()
    _save_slots(slots)

    bookings = _load_bookings()
    bookings = pd.concat([
        bookings,
        pd.DataFrame([{
            "appointment_id": appointment_id,
            "patient_name": patient_name.strip(),
            "department": department.strip(),
            "doctor_name": doctor_assigned,
            "date": normalized_date,
            "time_slot": time_slot.strip(),
            "status": "Confirmed",
            "patient_phone": patient_phone.strip(),
        }])
    ], ignore_index=True)
    bookings.to_csv(CSV_BOOKINGS, index=False)

    return (
        f"SUCCESS: Appointment {appointment_id} confirmed.\n"
        f"Patient: {patient_name.strip()}\n"
        f"Department: {department.strip()}\n"
        f"Doctor: {doctor_assigned}\n"
        f"Date: {normalized_date}\n"
        f"Time: {time_slot.strip()}\n"
        f"Slot ID: {slot_id}"
    )


@tool
def cancel_hospital_appointment(appointment_id: str, patient_name: str) -> str:
    """Cancel a confirmed appointment using appointment ID and patient name."""
    bookings = _load_bookings()
    bookings["appointment_id"] = bookings["appointment_id"].astype(str)
    bookings["patient_name"] = bookings["patient_name"].astype(str)
    match = bookings[
        (bookings["appointment_id"].str.strip().str.upper() == appointment_id.strip().upper())
        & (bookings["patient_name"].str.strip().str.lower() == patient_name.strip().lower())
        & (bookings["status"].astype(str).str.lower() == "confirmed")
    ]
    if match.empty:
        return f"Cancellation failed: no confirmed appointment {appointment_id} was found for {patient_name}."

    row_idx = match.index[0]
    row = match.iloc[0]
    slots = _reload_slots()
    slot_match = slots[
        (slots["department"].astype(str).str.lower() == str(row["department"]).lower())
        & (slots["date"].astype(str) == str(row["date"]))
        & (slots["time_slot"].astype(str).str.upper() == str(row["time_slot"]).upper())
        & (slots["doctor_name"].astype(str).str.lower() == str(row["doctor_name"]).lower())
    ]
    if not slot_match.empty:
        idx = slot_match.index[0]
        slots.at[idx, "status"] = "Available"
        slots.at[idx, "patient_name"] = ""
        _save_slots(slots)

    bookings.at[row_idx, "status"] = "Cancelled"
    bookings.to_csv(CSV_BOOKINGS, index=False)
    return f"SUCCESS: Appointment {appointment_id} has been cancelled and the slot is available again."


@tool
def reschedule_hospital_appointment(
    appointment_id: str, patient_name: str, new_date: str, new_time_slot: str
) -> str:
    """Move a confirmed appointment to a new available slot."""
    normalized_date = _parse_date(new_date)
    if not normalized_date:
        return "Rescheduling failed: invalid new date. Use YYYY-MM-DD."
    if normalized_date < dt_date.today().isoformat():
        return "Rescheduling failed: the new appointment date has already passed."

    bookings = _load_bookings()
    bookings["appointment_id"] = bookings["appointment_id"].astype(str)
    bookings["patient_name"] = bookings["patient_name"].astype(str)
    match = bookings[
        (bookings["appointment_id"].str.strip().str.upper() == appointment_id.strip().upper())
        & (bookings["patient_name"].str.strip().str.lower() == patient_name.strip().lower())
        & (bookings["status"].astype(str).str.lower() == "confirmed")
    ]
    if match.empty:
        return f"Rescheduling failed: no confirmed appointment {appointment_id} was found for {patient_name}."

    booking_idx = match.index[0]
    old = match.iloc[0]
    department = str(old["department"])

    slots = _reload_slots()
    new_match = slots[
        (slots["department"].astype(str).str.lower() == department.lower())
        & (slots["date"].astype(str) == normalized_date)
        & (slots["time_slot"].astype(str).str.upper() == new_time_slot.strip().upper())
        & (slots["status"].astype(str).str.lower() == "available")
    ]
    if new_match.empty:
        return f"Rescheduling failed: {new_time_slot} on {normalized_date} is not available for {department}."

    new_idx = new_match.index[0]
    new_doctor = str(slots.at[new_idx, "doctor_name"])

    old_match = slots[
        (slots["department"].astype(str).str.lower() == department.lower())
        & (slots["date"].astype(str) == str(old["date"]))
        & (slots["time_slot"].astype(str).str.upper() == str(old["time_slot"]).upper())
        & (slots["doctor_name"].astype(str).str.lower() == str(old["doctor_name"]).lower())
    ]
    if not old_match.empty:
        old_idx = old_match.index[0]
        slots.at[old_idx, "status"] = "Available"
        slots.at[old_idx, "patient_name"] = ""

    slots.at[new_idx, "status"] = "Booked"
    slots.at[new_idx, "patient_name"] = patient_name.strip()
    _save_slots(slots)

    bookings.at[booking_idx, "date"] = normalized_date
    bookings.at[booking_idx, "time_slot"] = new_time_slot.strip()
    bookings.at[booking_idx, "doctor_name"] = new_doctor
    bookings.to_csv(CSV_BOOKINGS, index=False)

    return f"SUCCESS: Appointment {appointment_id} rescheduled to {normalized_date} at {new_time_slot} with {new_doctor}."


@tool
def search_doctors_directory(department: str = "", doctor_name: str = "") -> str:
    """Search doctors and show their next available appointment when possible."""
    slots = _reload_slots()
    filtered = df_doctors.copy()
    if department.strip():
        filtered = filtered[filtered["department"].astype(str).str.lower() == department.strip().lower()]
    if doctor_name.strip():
        filtered = filtered[filtered["doctor_name"].astype(str).str.lower().str.contains(doctor_name.strip().lower(), regex=False)]

    if filtered.empty:
        return "No matching doctors found."

    today = dt_date.today().isoformat()
    lines = []
    for _, doctor in filtered.iterrows():
        open_slots = slots[
            (slots["doctor_id"].astype(str) == str(doctor["doctor_id"]))
            & (slots["date"].astype(str) >= today)
            & (slots["status"].astype(str).str.lower() == "available")
        ].sort_values(["date", "time_slot"])
        next_slot = "No open slot"
        if not open_slots.empty:
            s = open_slots.iloc[0]
            next_slot = f"{s['date']} {s['time_slot']}"
        lines.append(
            f"{doctor['doctor_name']} | {doctor['department']} | "
            f"Fee: ₹{doctor['consultation_fee']} | Working days: {doctor['working_days']} | "
            f"Next available: {next_slot}"
        )
    return "Doctors and current availability:\n" + "\n".join(lines)


APPOINTMENT_TOOLS = [
    check_doctor_availability,
    find_next_available_slots,
    book_hospital_appointment,
    cancel_hospital_appointment,
    reschedule_hospital_appointment,
    search_doctors_directory,
]
