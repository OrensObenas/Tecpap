import csv
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, time
from pathlib import Path
from typing import List, Dict, Tuple


# ----------------------------
# Config (tu as validé ces hypothèses)
# ----------------------------
CONFIG = {
    "seed": 42,

    # Horizon
    "start_date": "2026-01-05",  # lundi (modifiable)
    "days": 14,                  # 2 semaines

    # Production
    "formats": ["F1", "F2", "F3", "F4", "F5", "F6"],
    "of_per_day_mean": 12,       # environ 8-20
    "of_per_day_min": 8,
    "of_per_day_max": 20,

    # Shift (1 shift / jour)
    "shift_start": "08:00",
    "shift_end": "16:00",
    "lunch_start": "12:00",
    "lunch_end": "12:30",

    # Cadence (unités/heure) - nominale (par format on garde proche)
    "nominal_rate_min": 8000,
    "nominal_rate_max": 14000,

    # Quantités (unités) : petites / moyennes / grosses séries
    "qty_small": (2000, 8000),     # 5–15%
    "qty_medium": (8000, 30000),   # majorité
    "qty_large": (30000, 80000),   # 10–20%
    "p_small": 0.10,
    "p_large": 0.15,

    # Due dates (délais)
    "due_days_min": 0,             # parfois même jour
    "due_days_max": 5,             # horizon proche (modifiable)
    "p_tight_due": 0.18,           # % OF "tendus"

    # Setups (minutes)
    "setup_same": 0,
    "setup_close_range": (5, 15),  # formats "proches"
    "setup_far_range": (20, 55),   # formats "éloignés"

    # Pannes
    "major_breakdown_every_n_days": 5,     # ~1 panne majeure / 5 jours
    "major_breakdown_duration_min": (60, 180),
    "micro_breakdowns_per_day_range": (3, 8),
    "micro_breakdown_duration_min": (5, 15),

    # Urgences
    "urgent_orders_per_week_range": (2, 6),
    "urgent_time_window": ("09:00", "15:00"),  # arrive pendant shift
    "urgent_due_same_day_prob": 0.75,

    # Dérives de cadence
    "speed_drift_probability_per_day": 0.20,
    "speed_factor_range": (0.6, 0.9),
    "speed_drift_duration_min": (45, 120),
}


# ----------------------------
# Utils
# ----------------------------
def parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")

def parse_hhmm(s: str) -> time:
    return datetime.strptime(s, "%H:%M").time()

def dt_at(d: datetime, hhmm: str) -> datetime:
    t = parse_hhmm(hhmm)
    return datetime(d.year, d.month, d.day, t.hour, t.minute)

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def is_weekend(d: datetime) -> bool:
    return d.weekday() >= 5  # 5=Sat, 6=Sun

def rand_int(rng: Tuple[int, int]) -> int:
    a, b = rng
    return random.randint(a, b)

def rand_float(rng: Tuple[float, float]) -> float:
    a, b = rng
    return random.uniform(a, b)


# ----------------------------
# Data Models
# ----------------------------
@dataclass
class WorkOrder:
    of_id: str
    created_at: str
    due_date: str
    priority: int
    product: str
    format: str
    qty: int
    nominal_rate: int  # units/hour
    nominal_duration_min: int  # derived

@dataclass
class Event:
    timestamp: str
    type: str
    value: str


# ----------------------------
# Generators
# ----------------------------
def build_setup_matrix(formats: List[str]) -> List[Dict[str, str]]:
    """
    Simple realism rule:
    - same format => 0
    - "close" formats => small setup (neighbors)
    - far formats => larger setup
    """
    rows = []
    idx = {f: i for i, f in enumerate(formats)}

    for f_from in formats:
        for f_to in formats:
            if f_from == f_to:
                setup = CONFIG["setup_same"]
            else:
                # close if index distance <=1, else far
                dist = abs(idx[f_from] - idx[f_to])
                if dist <= 1:
                    setup = rand_int(CONFIG["setup_close_range"])
                else:
                    setup = rand_int(CONFIG["setup_far_range"])
            rows.append({
                "from_format": f_from,
                "to_format": f_to,
                "setup_min": str(setup)
            })
    return rows


def sample_qty() -> int:
    r = random.random()
    if r < CONFIG["p_small"]:
        return rand_int(CONFIG["qty_small"])
    if r > 1.0 - CONFIG["p_large"]:
        return rand_int(CONFIG["qty_large"])
    return rand_int(CONFIG["qty_medium"])


def sample_due_date(base_day: datetime) -> datetime:
    # Some are tight (same day / next day)
    if random.random() < CONFIG["p_tight_due"]:
        add = random.choice([0, 0, 1])  # bias tight
    else:
        add = rand_int((CONFIG["due_days_min"], CONFIG["due_days_max"]))
    return base_day + timedelta(days=add)


def sample_priority(due_day: datetime, base_day: datetime) -> int:
    # urgency influences priority: closer due => higher priority
    delta = (due_day.date() - base_day.date()).days
    if delta <= 0:
        return 5
    if delta == 1:
        return random.choice([4, 5])
    if delta == 2:
        return random.choice([3, 4])
    return random.choice([1, 2, 3])


def generate_work_orders(start_day: datetime, days: int, formats: List[str]) -> List[WorkOrder]:
    orders: List[WorkOrder] = []
    counter = 1

    for d in range(days):
        day = start_day + timedelta(days=d)
        if is_weekend(day):
            continue  # no production weekends in this MVP

        n = int(random.gauss(CONFIG["of_per_day_mean"], 3))
        n = clamp(n, CONFIG["of_per_day_min"], CONFIG["of_per_day_max"])

        for _ in range(n):
            fmt = random.choice(formats)
            qty = sample_qty()

            nominal_rate = rand_int((CONFIG["nominal_rate_min"], CONFIG["nominal_rate_max"]))
            # duration = qty / rate hours => minutes
            nominal_duration_min = max(5, int((qty / nominal_rate) * 60))

            due = sample_due_date(day)
            prio = sample_priority(due, day)

            wo = WorkOrder(
                of_id=f"OF{counter:05d}",
                created_at=dt_at(day, "07:30").isoformat(timespec="minutes"),
                due_date=dt_at(due, "16:00").isoformat(timespec="minutes"),
                priority=prio,
                product=f"PRODUCT_{fmt}",
                format=fmt,
                qty=qty,
                nominal_rate=nominal_rate,
                nominal_duration_min=nominal_duration_min
            )
            orders.append(wo)
            counter += 1

    return orders


def add_shift_events(start_day: datetime, days: int) -> List[Event]:
    events: List[Event] = []
    for d in range(days):
        day = start_day + timedelta(days=d)
        if is_weekend(day):
            continue
        events.append(Event(dt_at(day, CONFIG["shift_start"]).isoformat(timespec="minutes"), "SHIFT_START", ""))
        events.append(Event(dt_at(day, CONFIG["lunch_start"]).isoformat(timespec="minutes"), "SHIFT_STOP", "LUNCH"))
        events.append(Event(dt_at(day, CONFIG["lunch_end"]).isoformat(timespec="minutes"), "SHIFT_START", "AFTER_LUNCH"))
        events.append(Event(dt_at(day, CONFIG["shift_end"]).isoformat(timespec="minutes"), "SHIFT_STOP", "END_OF_SHIFT"))
    return events


def add_breakdown_events(start_day: datetime, days: int) -> List[Event]:
    events: List[Event] = []
    shift_start = CONFIG["shift_start"]
    shift_end = CONFIG["shift_end"]

    for d in range(days):
        day = start_day + timedelta(days=d)
        if is_weekend(day):
            continue

        # Micro-breakdowns
        k = rand_int(CONFIG["micro_breakdowns_per_day_range"])
        for _ in range(k):
            start = dt_at(day, shift_start) + timedelta(minutes=rand_int((20, 420)))
            dur = rand_int(CONFIG["micro_breakdown_duration_min"])
            end = start + timedelta(minutes=dur)
            events.append(Event(start.isoformat(timespec="minutes"), "BREAKDOWN_START", "MICRO"))
            events.append(Event(end.isoformat(timespec="minutes"), "BREAKDOWN_END", "MICRO"))

        # Major breakdown every N days (approx)
        if (d % CONFIG["major_breakdown_every_n_days"]) == 0:
            start = dt_at(day, shift_start) + timedelta(minutes=rand_int((60, 330)))
            dur = rand_int(CONFIG["major_breakdown_duration_min"])
            end = start + timedelta(minutes=dur)
            # clamp within day window a bit
            end_limit = dt_at(day, shift_end) - timedelta(minutes=5)
            if end > end_limit:
                end = end_limit
            events.append(Event(start.isoformat(timespec="minutes"), "BREAKDOWN_START", "MAJOR"))
            events.append(Event(end.isoformat(timespec="minutes"), "BREAKDOWN_END", "MAJOR"))

            # Optional: cascade after major (stress test)
            if random.random() < 0.25:
                c_start = end + timedelta(minutes=rand_int((10, 40)))
                for _ in range(2):
                    c_dur = rand_int(CONFIG["micro_breakdown_duration_min"])
                    c_end = c_start + timedelta(minutes=c_dur)
                    if c_end <= dt_at(day, shift_end):
                        events.append(Event(c_start.isoformat(timespec="minutes"), "BREAKDOWN_START", "CASCADE"))
                        events.append(Event(c_end.isoformat(timespec="minutes"), "BREAKDOWN_END", "CASCADE"))
                    c_start = c_end + timedelta(minutes=rand_int((10, 30)))

    return events


def add_speed_drift_events(start_day: datetime, days: int) -> List[Event]:
    events: List[Event] = []
    for d in range(days):
        day = start_day + timedelta(days=d)
        if is_weekend(day):
            continue

        if random.random() < CONFIG["speed_drift_probability_per_day"]:
            start = dt_at(day, CONFIG["shift_start"]) + timedelta(minutes=rand_int((30, 360)))
            dur = rand_int(CONFIG["speed_drift_duration_min"])
            factor = round(rand_float(CONFIG["speed_factor_range"]), 2)
            end = start + timedelta(minutes=dur)

            events.append(Event(start.isoformat(timespec="minutes"), "SPEED_CHANGE", f"{factor}"))
            events.append(Event(end.isoformat(timespec="minutes"), "SPEED_CHANGE", "1.0"))

    return events


def add_urgent_order_events(start_day: datetime, days: int, orders: List[WorkOrder]) -> List[Event]:
    events: List[Event] = []

    # pick urgent count for 2 weeks ~ (2..6 per week) => 4..12 in 2 weeks
    per_week = rand_int(CONFIG["urgent_orders_per_week_range"])
    urgent_total = clamp(per_week * 2, 4, 12)

    # choose random working days
    working_days = [start_day + timedelta(days=d) for d in range(days) if not is_weekend(start_day + timedelta(days=d))]
    chosen_days = random.sample(working_days, k=min(urgent_total, len(working_days)))

    for i, day in enumerate(chosen_days, start=1):
        # urgent time window inside shift
        w_start = dt_at(day, CONFIG["urgent_time_window"][0])
        w_end = dt_at(day, CONFIG["urgent_time_window"][1])
        t = w_start + timedelta(minutes=rand_int((0, int((w_end - w_start).total_seconds() / 60))))

        fmt = random.choice(CONFIG["formats"])
        qty = rand_int((3000, 25000))  # urgences plutôt petites/moyennes
        nominal_rate = rand_int((CONFIG["nominal_rate_min"], CONFIG["nominal_rate_max"]))
        duration_min = max(5, int((qty / nominal_rate) * 60))

        # due date often same day
        if random.random() < CONFIG["urgent_due_same_day_prob"]:
            due = dt_at(day, CONFIG["shift_end"])
        else:
            due = dt_at(day + timedelta(days=1), CONFIG["shift_end"])

        urgent_of_id = f"URG{ i:04d}"

        # We'll add an URGENT_ORDER event. Your system should translate this into a new WorkOrder.
        payload = f"of_id={urgent_of_id};format={fmt};qty={qty};nominal_rate={nominal_rate};duration_min={duration_min};due={due.isoformat(timespec='minutes')};priority=5"
        events.append(Event(t.isoformat(timespec="minutes"), "URGENT_ORDER", payload))

    return events


# ----------------------------
# Writers
# ----------------------------
def write_csv(path: Path, fieldnames: List[str], rows: List[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main(out_dir: str = "tecpap_synth_data"):
    random.seed(CONFIG["seed"])

    start_day = parse_date(CONFIG["start_date"])
    formats = CONFIG["formats"]

    # 1) Setup matrix
    setup_rows = build_setup_matrix(formats)

    # 2) Work orders
    orders = generate_work_orders(start_day, CONFIG["days"], formats)
    orders_rows = [{
        "of_id": o.of_id,
        "created_at": o.created_at,
        "due_date": o.due_date,
        "priority": o.priority,
        "product": o.product,
        "format": o.format,
        "qty": o.qty,
        "nominal_rate_u_per_h": o.nominal_rate,
        "nominal_duration_min": o.nominal_duration_min,
    } for o in orders]

    # 3) Events
    events: List[Event] = []
    events += add_shift_events(start_day, CONFIG["days"])
    events += add_breakdown_events(start_day, CONFIG["days"])
    events += add_speed_drift_events(start_day, CONFIG["days"])
    events += add_urgent_order_events(start_day, CONFIG["days"], orders)

    # sort events by time
    events.sort(key=lambda e: e.timestamp)
    events_rows = [{
        "timestamp": e.timestamp,
        "type": e.type,
        "value": e.value
    } for e in events]

    # Write
    out = Path(out_dir)
    write_csv(out / "setup_matrix.csv", ["from_format", "to_format", "setup_min"], setup_rows)
    write_csv(out / "work_orders.csv",
              ["of_id", "created_at", "due_date", "priority", "product", "format", "qty", "nominal_rate_u_per_h", "nominal_duration_min"],
              orders_rows)
    write_csv(out / "events.csv", ["timestamp", "type", "value"], events_rows)

    # Quick summary
    print(f"✅ Generated in ./{out_dir}")
    print(f"- work_orders.csv : {len(orders_rows)} OF")
    print(f"- setup_matrix.csv: {len(setup_rows)} lines")
    print(f"- events.csv      : {len(events_rows)} events")
    print(f"Seed = {CONFIG['seed']}")


if __name__ == "__main__":
    main()
