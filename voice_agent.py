"""
Apollo Clinic Voice Agent — brain module
Handles full appointment booking conversation for:
  - General Physicians
  - Dermatologists
  - Orthopedic Specialists
Clinic hours: 9 AM – 8 PM, Monday to Saturday
"""

from datetime import datetime, timedelta
import re
def parse_time(t):
    m = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?', t)
    if m:
        h = int(m.group(1))
        mn = int(m.group(2)) if m.group(2) else 0
        p = re.sub(r'\.', '', m.group(3) or '').strip()
        if p == "pm" and h != 12: h += 12
        elif p == "am" and h == 12: h = 0
        return f"{h:02d}:{mn:02d}"

# ─────────────────────────────────────────
# CLINIC DATA
# ─────────────────────────────────────────

CLINIC_DATA = {
    "general physician": {
        "doctors": [
            {"name": "Dr. Rohan Kulkarni", "slots": ["09:00","10:00","11:00","12:00","14:00","15:00","16:00","17:00","18:00","19:00"]},
            {"name": "Dr. Sneha Patil",    "slots": ["09:00","10:00","11:00","14:00","15:00","16:00","17:00","18:00"]},
        ]
    },
    "dermatology": {
        "doctors": [
            {"name": "Dr. Ananya Desai",  "slots": ["10:00","11:00","12:00","14:00","15:00","16:00","17:00"]},
            {"name": "Dr. Kabir Mehta",   "slots": ["09:00","10:00","11:00","14:00","15:00","16:00","18:00","19:00"]},
        ]
    },
    "orthopedics": {
        "doctors": [
            {"name": "Dr. Vivek Singh",   "slots": ["09:00","10:00","11:00","14:00","15:00","16:00"]},
            {"name": "Dr. Priya Nair",    "slots": ["10:00","11:00","12:00","14:00","15:00","17:00","18:00"]},
        ]
    },
}

EMERGENCY_LINE = "1800-APOLLO-911"
CLINIC_HOURS  = "9 AM to 8 PM, Monday to Saturday"

# Booked slots in-memory (replace with DB in production)
# Format: { "Dr. Name|YYYY-MM-DD": {"10:00", "11:00"} }
_booked: dict[str, set] = {}


def _booked_key(doctor: str, date: str) -> str:
    return f"{doctor}|{date}"


def is_slot_booked(doctor: str, date: str, slot: str) -> bool:
    return slot in _booked.get(_booked_key(doctor, date), set())


def book_slot(doctor: str, date: str, slot: str):
    key = _booked_key(doctor, date)
    _booked.setdefault(key, set()).add(slot)


def available_slots(doctor_obj: dict, date: str) -> list[str]:
    all_slots = doctor_obj["slots"]
    booked    = _booked.get(_booked_key(doctor_obj["name"], date), set())
    return [s for s in all_slots if s not in booked]


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def fmt_slot(s: str) -> str:
    """Convert 24h 'HH:MM' to '10:00 AM' style."""
    h, m = map(int, s.split(":"))
    period = "AM" if h < 12 else "PM"
    h12 = h if h <= 12 else h - 12
    h12 = 12 if h12 == 0 else h12
    return f"{h12}:{m:02d} {period}"


def fmt_date(d: str) -> str:
    """'2025-05-25' → 'Sunday, 25 May 2025'"""
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%A, %d %B %Y")
    except Exception:
        return d


def parse_date(text: str):
    text = text.lower().strip()

    if "today" in text:
        d = datetime.now()
        if d.weekday() == 6:          # Sunday
            return None, "today_sunday"
        return d.strftime("%Y-%m-%d"), True

    if "tomorrow" in text:
        d = datetime.now() + timedelta(days=1)
        if d.weekday() == 6:
            return None, "tomorrow_sunday"
        return d.strftime("%Y-%m-%d"), True

    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d %m %Y"):
        try:
            parsed = datetime.strptime(text, fmt)
            if parsed.weekday() == 6:
                return None, "sunday"
            return parsed.strftime("%Y-%m-%d"), True
        except ValueError:
            continue

    return None, False


def normalize_slot(text: str) -> str:
    """'2 PM' / '14:00' / 'two pm' → '14:00'"""
    t = text.lower().strip()
    words = {"nine":9,"ten":10,"eleven":11,"twelve":12,
             "one":1,"two":2,"three":3,"four":4,"five":5,
             "six":6,"seven":7,"eight":8}
    for w, h in words.items():
        if w in t:
            if "pm" in t and h != 12: h += 12
            if "am" in t and h == 12: h = 0
            return f"{h:02d}:00"
    m = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', t)
    if m:
        h = int(m.group(1))
        mn = int(m.group(2)) if m.group(2) else 0
        p = m.group(3)
        if p == "pm" and h != 12: h += 12
        elif p == "am" and h == 12: h = 0
        return f"{h:02d}:{mn:02d}"
    return t


def detect_specialty(text: str):
    t = text.lower()
    if any(x in t for x in ["general","gp","physician","fever","cold","cough","medicine"]):
        return "general physician"
    if any(x in t for x in ["derm","skin","acne","rash","hair","nail"]):
        return "dermatology"
    if any(x in t for x in ["ortho","bone","joint","fracture","spine","knee","shoulder"]):
        return "orthopedics"
    return None


def detect_doctor(text: str):
    t = text.lower()
    for dept in CLINIC_DATA.values():
        for doc in dept["doctors"]:
            if doc["name"].lower().split("dr. ")[-1].split()[0] in t or doc["name"].lower() in t:
                return doc, dept
    return None, None


def is_emergency(text: str) -> bool:
    t = text.lower()
    return any(x in t for x in ["emergency","chest pain","heart attack","unconscious",
                                  "bleeding","stroke","accident","critical","urgent"])


# ─────────────────────────────────────────
# CONVERSATION ENGINE
# ─────────────────────────────────────────

GREETING = (
    f"Hello! Welcome to Apollo Clinic. Our clinic is open {CLINIC_HOURS}. "
    "I can help you schedule an appointment with a general physician, dermatologist, "
    "or orthopedic specialist. How may I assist you today?"
)

REMINDERS = (
    "Please remember to bring your previous prescriptions and any reports, "
    "and kindly arrive 15 minutes before your appointment time."
)


def get_session() -> dict:
    return {
        "step": "greet",
        "name": None,
        "specialty": None,
        "doctor": None,
        "doctor_obj": None,
        "date": None,
        "slot": None,
        "available": [],
    }


def think(user_text: str, memory: dict) -> str:
    if "session" not in memory:
        memory["session"] = get_session()

    sess = memory["session"]
    text = user_text.strip()
    tl   = text.lower()

    # ── EMERGENCY CHECK (always, any step) ──────────────────────────────────
    if is_emergency(tl):
        return (
            f"This sounds like a medical emergency. Please call our 24/7 emergency helpline "
            f"immediately: {EMERGENCY_LINE}, or go to the nearest emergency room right away. "
            "Do not wait for a scheduled appointment. Please stay safe."
        )

    # ── GREET ────────────────────────────────────────────────────────────────
    if sess["step"] == "greet":
        sess["step"] = "get_name"
        return GREETING

    # ── GET NAME ─────────────────────────────────────────────────────────────
    if sess["step"] == "get_name":
        if len(text.strip()) < 2:
            return "Could you please share your full name so I can address you properly?"
        sess["name"] = text.strip().title()
        sess["step"] = "get_specialty"
        return (
            f"Thank you, {sess['name']}. Which specialist would you like to see today? "
            "We have general physicians, dermatologists, and orthopedic specialists."
        )

    # ── GET SPECIALTY / DOCTOR ───────────────────────────────────────────────
    if sess["step"] == "get_specialty":

        # Check if they named a specific doctor
        doc_obj, dept = detect_doctor(tl)
        if doc_obj:
            sess["doctor_obj"] = doc_obj
            sess["doctor"]     = doc_obj["name"]
            for k, v in CLINIC_DATA.items():
                if doc_obj in v["doctors"]:
                    sess["specialty"] = k
                    break
            sess["step"] = "get_date"
            return (
                f"Great choice! {sess['doctor']} is available. "
                "What date would you like your appointment? "
                "You can say today, tomorrow, or give a date like 25-05-2025. "
                f"(Clinic is open Monday to Saturday, {CLINIC_HOURS}.)"
            )

        spec = detect_specialty(tl)
        if spec:
            sess["specialty"] = spec
            docs = CLINIC_DATA[spec]["doctors"]
            doc_list = " or ".join([d["name"] for d in docs])
            sess["step"] = "get_doctor"
            return (
                f"We have the following {spec} specialists available: {doc_list}. "
                "Do you have a preference, or shall I assign the first available doctor?"
            )

        return (
            "I'm sorry, I didn't catch that. We offer general physicians, "
            "dermatologists, and orthopedic specialists. Which would you prefer?"
        )

    # ── GET DOCTOR PREFERENCE ────────────────────────────────────────────────
    if sess["step"] == "get_doctor":
        docs = CLINIC_DATA[sess["specialty"]]["doctors"]

        doc_obj, _ = detect_doctor(tl)
        if doc_obj and doc_obj in docs:
            sess["doctor_obj"] = doc_obj
            sess["doctor"]     = doc_obj["name"]
        elif any(x in tl for x in ["any","first","available","no preference","doesn't matter","either"]):
            sess["doctor_obj"] = docs[0]
            sess["doctor"]     = docs[0]["name"]
        else:
            doc_list = " or ".join([d["name"] for d in docs])
            return f"Could you please choose from {doc_list}, or say 'any' for first available?"

        sess["step"] = "get_date"
        return (
            f"Perfect, I'll book you with {sess['doctor']}. "
            "What date would you prefer? Say today, tomorrow, or a date like 25-05-2025. "
            f"We're open Monday to Saturday."
        )

    # ── GET DATE ─────────────────────────────────────────────────────────────
    if sess["step"] == "get_date":
        parsed, valid = parse_date(text)

        if valid == "sunday" or valid == "today_sunday" or valid == "tomorrow_sunday":
            return (
                "I'm sorry, our clinic is closed on Sundays. "
                "Could you please choose a date from Monday to Saturday?"
            )

        if not valid:
            return (
                "I couldn't quite catch that date. Could you say today, tomorrow, "
                "or give a date like 25-05-2025?"
            )

        sess["date"] = parsed
        avail = available_slots(sess["doctor_obj"], parsed)

        if not avail:
            sess["step"] = "get_date"
            return (
                f"Unfortunately, {sess['doctor']} has no available slots on {fmt_date(parsed)}. "
                "Could you please choose a different date?"
            )

        sess["available"] = avail
        sess["step"]      = "get_slot"
        slot_str = ", ".join([fmt_slot(s) for s in avail[:6]])
        return (
            f"On {fmt_date(parsed)}, {sess['doctor']} has the following slots open: "
            f"{slot_str}. Which time works best for you?"
        )
# ── GET SLOT ─────────────────────────────────────────────────────────────
if sess["step"] == "get_slot":

    avail = sess["available"]

    # 🔥 normalize user time
    user_time = parse_time(text)

    matched_slot = None

    for slot in avail:
        slot_time = parse_time(fmt_slot(slot))
        if slot_time == user_time:
            matched_slot = slot
            break

    # ✅ MATCHED
    if matched_slot:
        sess["slot"] = matched_slot
        sess["step"] = "confirm"

        return (
            f"Let me confirm your appointment details:\n\n"
            f"  Patient   : {sess['name']}\n"
            f"  Doctor    : {sess['doctor']}\n"
            f"  Specialty : {sess['specialty'].title()}\n"
            f"  Date      : {fmt_date(sess['date'])}\n"
            f"  Time      : {fmt_slot(sess['slot'])}\n\n"
            "Shall I go ahead and confirm this? Please say yes or no."
        )

    # ❌ NOT MATCHED
    alternatives = avail[:2]

    if alternatives:
        alt_str = " or ".join([fmt_slot(s) for s in alternatives])
        return (
            f"I'm sorry, that time is not available. "
            f"The next available slots are {alt_str}. Would either of those work for you?"
        )

    slot_str = ", ".join([fmt_slot(s) for s in avail[:4]])
    return (
        f"That slot isn't available. Available times are: {slot_str}. "
        "Which would you prefer?"
    )


# ── CONFIRM ──────────────────────────────────────────────────────────────
if sess["step"] == "confirm":

    if any(x in tl for x in ["yes","confirm","correct","sure","ok","go ahead","please"]):
        book_slot(sess["doctor"], sess["date"], sess["slot"])
        memory["session"] = get_session()

        return (
            f"Wonderful! Your appointment has been confirmed, {sess['name']}. "
            f"You are scheduled with {sess['doctor']} on {fmt_date(sess['date'])} "
            f"at {fmt_slot(sess['slot'])}.\n\n"
            f"{REMINDERS}\n\n"
            "If you need to reschedule or cancel, please call us at least 2 hours in advance. "
            "Thank you for choosing Apollo Clinic. We wish you good health. Take care!"
        )

    if any(x in tl for x in ["no","cancel","wrong","change","different"]):
        sess["step"] = "get_date"
        sess["slot"] = None
        sess["date"] = None
        return (
            "No problem! Let's pick a different date or time. "
            "What date would you prefer?"
        )

    return "Please say yes to confirm the appointment or no to change the details."


# ── FALLBACK ─────────────────────────────────────────────────────────────
memory["session"] = get_session()
return (
    "I apologize, something went wrong on my end. Let's start fresh. " + GREETING
)