# api_server.py
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from scheduler_core import Event, IncomingEvent, load_engine_from_dir


app = FastAPI(title="TECPAP Scheduler API", version="0.3")
ENGINE = load_engine_from_dir("tecpap_synth_data")


def parse_iso(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Bad timestamp format: {ts}") from e


# -------------------------
# Schemas
# -------------------------

class EventIn(BaseModel):
    timestamp: str
    type: str
    value: Optional[str] = ""

class EvoconWebhookIn(BaseModel):
    eventTime: str
    eventType: str
    reason: Optional[str] = ""
    speedFactor: Optional[float] = None
    payload: Optional[str] = ""

class PlanRowOut(BaseModel):
    of_id: str
    format: str
    start: str
    end: str
    setup_min: int
    work_nominal_min: int
    note: str

class SimIncomingEventIn(BaseModel):
    """
    This is how you simulate 'late events':
    - receive_time: when the engine receives it (e.g., 12:00)
    - event_timestamp: when it actually happened (e.g., 10:00)
    """
    receive_time: str
    event_timestamp: str
    type: str
    value: Optional[str] = ""
    source: Optional[str] = "simulation"

class SimDayRequest(BaseModel):
    day_start: str
    day_end: str
    report_every_min: int = 60
    incoming_events: List[SimIncomingEventIn] = Field(default_factory=list)
    late_policy: str = "APPLY_NOW"  # APPLY_NOW or IGNORE
    max_event_lateness_min: int = 120


# -------------------------
# Endpoints
# -------------------------

@app.get("/state")
def get_state():
    return ENGINE.get_state()

@app.get("/plan", response_model=List[PlanRowOut])
def get_plan(limit: int = 30):
    rows = ENGINE.get_plan_preview(limit=limit)
    return [
        PlanRowOut(
            of_id=r.of_id,
            format=r.format,
            start=r.start.isoformat(timespec="minutes"),
            end=r.end.isoformat(timespec="minutes"),
            setup_min=r.setup_min,
            work_nominal_min=r.work_nominal_min,
            note=r.note
        )
        for r in rows
    ]

@app.get("/plan/export.csv")
def export_plan_csv(limit: int = 200):
    rows = ENGINE.get_plan_preview(limit=limit)
    lines = ["of_id,format,start,end,setup_min,work_nominal_min,note"]

    def esc(s: str) -> str:
        if "," in s or '"' in s:
            return '"' + s.replace('"', '""') + '"'
        return s

    for r in rows:
        lines.append(",".join([
            esc(r.of_id),
            esc(r.format),
            esc(r.start.isoformat(timespec="minutes")),
            esc(r.end.isoformat(timespec="minutes")),
            str(r.setup_min),
            str(r.work_nominal_min),
            esc(r.note),
        ]))
    return Response(content="\n".join(lines), media_type="text/csv")

@app.post("/events")
def post_event(ev: EventIn):
    t = parse_iso(ev.timestamp)
    event = Event(timestamp=t, type=ev.type, value=ev.value or "")
    return ENGINE.handle_event(event, source="manual/events")

@app.get("/events/log")
def get_events_log(limit: int = 100):
    return ENGINE.get_event_log(limit=limit)

@app.post("/time")
def set_time(timestamp: str):
    t = parse_iso(timestamp)
    return ENGINE.set_time(t)

# -------------------------
# Evocon-like webhook -> internal
# -------------------------

def map_evocon_to_internal(payload: EvoconWebhookIn) -> Event:
    ts = parse_iso(payload.eventTime)
    et = payload.eventType.strip().lower()

    if et == "downtime_start":
        return Event(timestamp=ts, type="BREAKDOWN_START", value=(payload.reason or ""))
    if et == "downtime_end":
        return Event(timestamp=ts, type="BREAKDOWN_END", value=(payload.reason or ""))
    if et == "shift_start":
        return Event(timestamp=ts, type="SHIFT_START", value="")
    if et == "shift_stop":
        return Event(timestamp=ts, type="SHIFT_STOP", value="")
    if et == "speed":
        if payload.speedFactor is None:
            raise HTTPException(status_code=400, detail="Missing speedFactor for speed event")
        return Event(timestamp=ts, type="SPEED_CHANGE", value=str(payload.speedFactor))
    if et == "urgent_order":
        if not payload.payload:
            raise HTTPException(status_code=400, detail="Missing payload for urgent_order")
        return Event(timestamp=ts, type="URGENT_ORDER", value=payload.payload)

    raise HTTPException(status_code=400, detail=f"Unsupported evocon eventType: {payload.eventType}")

@app.post("/evocon/webhook")
def evocon_webhook(ev: EvoconWebhookIn):
    internal = map_evocon_to_internal(ev)
    return ENGINE.handle_event(internal, source="evocon/webhook")

# -------------------------
# Simulation endpoint (whole day + hourly reports + late events)
# -------------------------

@app.post("/simulate/day")
def simulate_day(req: SimDayRequest):
    day_start = parse_iso(req.day_start)
    day_end = parse_iso(req.day_end)

    # Build incoming events
    incs: List[IncomingEvent] = []
    for x in req.incoming_events:
        receive_time = parse_iso(x.receive_time)
        event_ts = parse_iso(x.event_timestamp)
        ev = Event(timestamp=event_ts, type=x.type, value=x.value or "")
        incs.append(IncomingEvent(receive_time=receive_time, event=ev, source=x.source or "simulation"))

    # Run simulation on clone (does not modify live ENGINE)
    sim_engine = ENGINE.clone()
    sim_engine.late_policy = req.late_policy
    sim_engine.max_event_lateness_min = req.max_event_lateness_min

    result = sim_engine.simulate_day(
        day_start=day_start,
        day_end=day_end,
        incoming_events=incs,
        report_every_min=req.report_every_min
    )
    return result
