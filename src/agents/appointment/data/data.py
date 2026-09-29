"""Appointment data layer for the demo hospital application.

The original project shipped with a very small, already-expired slot dataset.
This module keeps the CSV-backed design but automatically creates a useful
rolling schedule so local demos and deployments have real future availability.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
import re
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent
CSV_DOCTORS = DATA_DIR / "doctors.csv"
CSV_SLOTS = DATA_DIR / "slots_availability.csv"
CSV_BOOKINGS = DATA_DIR / "appointments_booked.csv"

SLOT_COLUMNS = [
    "slot_id", "doctor_id", "doctor_name", "department", "date",
    "time_slot", "status", "patient_name"
]
BOOKING_COLUMNS = [
    "appointment_id", "patient_name", "department", "doctor_name",
    "date", "time_slot", "status", "patient_phone"
]

# Two demo consultation times per doctor. Different departments get slightly
# different schedules so the UI looks realistic without needing a live HIS.
DEPARTMENT_TIMES = {
    "Cardiology": ["09:00 AM", "11:00 AM", "02:00 PM", "04:00 PM"],
    "Dermatology": ["09:30 AM", "11:30 AM", "03:00 PM", "05:00 PM"],
    "General Practice": ["08:30 AM", "10:30 AM", "02:00 PM", "04:00 PM"],
    "Orthopedics": ["09:00 AM", "11:00 AM", "02:30 PM", "04:30 PM"],
    "Pediatrics": ["10:00 AM", "12:00 PM", "03:00 PM", "05:00 PM"],
    "Neurology": ["09:00 AM", "11:30 AM", "02:00 PM", "04:00 PM"],
    "Gynecology": ["09:00 AM", "11:30 AM", "02:30 PM", "04:30 PM"],
    "Ophthalmology": ["09:30 AM", "10:30 AM", "02:00 PM", "03:30 PM"],
    "Psychiatry": ["10:00 AM", "12:00 PM", "03:00 PM", "05:00 PM"],
    "ENT": ["09:00 AM", "11:00 AM", "02:30 PM", "04:30 PM"],
}

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _working_days_set(value: str) -> set[str]:
    """Turn values such as 'Mon-Sat' or 'Tue-Sun' into weekday names."""
    value = str(value).strip()
    if "-" in value:
        start, end = [x.strip() for x in value.split("-", 1)]
        try:
            a, b = DAY_NAMES.index(start), DAY_NAMES.index(end)
            if a <= b:
                return set(DAY_NAMES[a:b + 1])
            return set(DAY_NAMES[a:] + DAY_NAMES[:b + 1])
        except ValueError:
            pass
    return {x.strip() for x in value.split(",") if x.strip() in DAY_NAMES}


def _next_slot_rows(doctors: pd.DataFrame, start: date, days: int = 60) -> list[dict]:
    rows: list[dict] = []
    sequence = 1
    for offset in range(days):
        current = start + timedelta(days=offset)
        weekday = current.strftime("%a")
        for doctor_idx, doctor in doctors.reset_index(drop=True).iterrows():
            working = _working_days_set(doctor["working_days"])
            if weekday not in working:
                continue
            times = DEPARTMENT_TIMES.get(
                str(doctor["department"]), ["09:00 AM", "01:00 PM"]
            )
            # Two slots per working day, rotated across doctors.
            start_index = doctor_idx % max(1, len(times) - 1)
            chosen = [times[start_index], times[(start_index + 1) % len(times)]]
            for time_slot in chosen:
                rows.append({
                    "slot_id": f"SLT-{current.strftime('%Y%m%d')}-{sequence:05d}",
                    "doctor_id": doctor["doctor_id"],
                    "doctor_name": doctor["doctor_name"],
                    "department": doctor["department"],
                    "date": current.isoformat(),
                    "time_slot": time_slot,
                    "status": "Available",
                    "patient_name": "",
                })
                sequence += 1
    return rows


def ensure_future_schedule(days: int = 60) -> None:
    """Ensure the CSV contains a rolling future schedule.

    Existing future bookings are preserved. Expired demo rows are harmless and
    remain in the file for historical demonstration, while new dates are added.
    """
    if not CSV_DOCTORS.exists():
        raise FileNotFoundError(f"Missing doctors dataset: {CSV_DOCTORS}")

    doctors = pd.read_csv(CSV_DOCTORS).fillna("")
    today = date.today()
    target_end = today + timedelta(days=days - 1)

    if CSV_SLOTS.exists():
        slots = pd.read_csv(CSV_SLOTS).fillna("")
    else:
        slots = pd.DataFrame(columns=SLOT_COLUMNS)

    for col in SLOT_COLUMNS:
        if col not in slots.columns:
            slots[col] = ""
    slots = slots[SLOT_COLUMNS]
    slots["date"] = slots["date"].astype(str)
    existing_keys = set(
        zip(slots["doctor_id"].astype(str), slots["date"].astype(str), slots["time_slot"].astype(str))
    )

    new_rows = []
    for row in _next_slot_rows(doctors, today, days):
        key = (str(row["doctor_id"]), str(row["date"]), str(row["time_slot"]))
        if key not in existing_keys:
            new_rows.append(row)
            existing_keys.add(key)

    if new_rows:
        slots = pd.concat([slots, pd.DataFrame(new_rows)], ignore_index=True)

    # Normalize old/new statuses and keep future schedule deterministic.
    slots["status"] = slots["status"].astype(str).str.title()
    slots["patient_name"] = slots["patient_name"].fillna("").astype(str)
    slots.to_csv(CSV_SLOTS, index=False)

    if not CSV_BOOKINGS.exists():
        pd.DataFrame(columns=BOOKING_COLUMNS).to_csv(CSV_BOOKINGS, index=False)


ensure_future_schedule()

df_doctors = pd.read_csv(CSV_DOCTORS).fillna("")
df_slots = pd.read_csv(CSV_SLOTS).fillna("")
for col in SLOT_COLUMNS:
    if col not in df_slots.columns:
        df_slots[col] = ""
df_slots = df_slots[SLOT_COLUMNS]
df_slots["patient_name"] = df_slots["patient_name"].astype(str)
