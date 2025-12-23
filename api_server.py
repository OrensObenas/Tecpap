# api_server.py
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from scheduler_core import Event, IncomingEvent, load_engine_from_dir


app = FastAPI(title="TECPAP Scheduler API", version="0.4")
ENGINE = load_engine_from_dir("tecpap_synth_data")


def parse_iso(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Bad timestamp format: {ts}") from e


class EventIn(BaseModel):
    timestamp: str
    type: str
    value: Optional[str] = ""

class PlanRowOut(BaseModel):
    of_id: str
    format: str
    start: str
    end: str
    setup_min: int
    work_nominal_min: int
    note: str

class SimIncomingEventIn(BaseModel):
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
    late_policy: str = "APPLY_NOW"
    max_event_lateness_min: int = 120
    breakdown_replan_threshold_min: int = 30


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

@app.post("/events")
def post_event(ev: EventIn):
    t = parse_iso(ev.timestamp)
    event = Event(timestamp=t, type=ev.type, value=ev.value or "")
    return ENGINE.handle_event(event, source="manual/events")

@app.get("/events/log")
def get_events_log(limit: int = 100):
    return ENGINE.get_event_log(limit=limit)

@app.post("/simulate/day")
def simulate_day(req: SimDayRequest):
    day_start = parse_iso(req.day_start)
    day_end = parse_iso(req.day_end)

    incs: List[IncomingEvent] = []
    for x in req.incoming_events:
        receive_time = parse_iso(x.receive_time)
        event_ts = parse_iso(x.event_timestamp)
        ev = Event(timestamp=event_ts, type=x.type, value=x.value or "")
        incs.append(IncomingEvent(receive_time=receive_time, event=ev, source=x.source or "simulation"))

    sim_engine = ENGINE.clone()
    sim_engine.late_policy = req.late_policy
    sim_engine.max_event_lateness_min = req.max_event_lateness_min
    sim_engine.breakdown_replan_threshold_min = req.breakdown_replan_threshold_min

    return sim_engine.simulate_day(
        day_start=day_start,
        day_end=day_end,
        incoming_events=incs,
        report_every_min=req.report_every_min
    )
