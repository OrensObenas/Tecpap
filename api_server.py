# api_server.py
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from scheduler_core import Event, IncomingEvent, load_engine_from_dir

# Realtime runner
from realtime_runner import RealTimeRunner, RunnerConfig


app = FastAPI(title="TECPAP Scheduler API", version="0.6")

# ✅ CORS (indispensable pour un frontend React/Vite)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ENGINE = load_engine_from_dir("tecpap_synth_data")
RUNNER = RealTimeRunner(ENGINE)


def parse_iso(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Bad timestamp format: {ts}") from e


# -----------------------
# Schemas
# -----------------------

class EventIn(BaseModel):
    timestamp: str
    type: str
    value: Optional[str] = ""


class EventNowIn(BaseModel):
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


class RealTimeStartRequest(BaseModel):
    day_start: str
    day_end: str
    compress_to_seconds: int = 600  # default 10 min
    tick_seconds: float = 0.5


# -----------------------
# Basic engine endpoints
# -----------------------

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
    """
    Export planning preview to CSV for quick download.
    """
    rows = ENGINE.get_plan_preview(limit=limit)
    lines = ["of_id,format,start,end,setup_min,work_nominal_min,note"]

    def esc(s: str) -> str:
        if "," in s or '"' in s or "\n" in s:
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


# -----------------------
# Events endpoints
# -----------------------

@app.post("/events")
def post_event(ev: EventIn):
    t = parse_iso(ev.timestamp)
    event = Event(timestamp=t, type=ev.type, value=ev.value or "")
    return ENGINE.handle_event(event, source="manual/events")


@app.post("/events/now")
def post_event_now(ev: EventNowIn):
    """
    Create an event with timestamp = current simulated time (engine.now).
    Perfect for realtime demo while runner is running.
    """
    now_sim = datetime.fromisoformat(ENGINE.get_state()["now"])
    event = Event(timestamp=now_sim, type=ev.type, value=ev.value or "")
    return ENGINE.handle_event(event, source="manual/events_now")


@app.get("/events/log")
def get_events_log(limit: int = 100):
    return ENGINE.get_event_log(limit=limit)


# -----------------------
# Offline full-day simulation
# -----------------------

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


# -----------------------
# Realtime compressed simulation
# -----------------------

@app.post("/realtime/start")
def realtime_start(req: RealTimeStartRequest):
    day_start = parse_iso(req.day_start)
    day_end = parse_iso(req.day_end)

    if day_end <= day_start:
        raise HTTPException(status_code=400, detail="day_end must be > day_start")

    if req.compress_to_seconds <= 0:
        raise HTTPException(status_code=400, detail="compress_to_seconds must be > 0")

    if req.tick_seconds <= 0:
        raise HTTPException(status_code=400, detail="tick_seconds must be > 0")

    cfg = RunnerConfig(
        day_start=day_start,
        day_end=day_end,
        compress_to_seconds=req.compress_to_seconds,
        tick_seconds=req.tick_seconds
    )
    return RUNNER.start(cfg)


@app.post("/realtime/stop")
def realtime_stop():
    return RUNNER.stop()


@app.get("/realtime/state")
def realtime_state():
    return RUNNER.state()


@app.get("/realtime/hourly")
def realtime_hourly():
    return RUNNER.hourly_reports()
