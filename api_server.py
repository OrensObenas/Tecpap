# api_server.py
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional
from types import SimpleNamespace
import os
import traceback
import inspect

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from scheduler_core import Event, IncomingEvent, load_engine_from_dir

# Realtime runner
from realtime_runner import RealTimeRunner, RunnerConfig
# -----------------------
# NEW: Work Orders + Planning preview from CSV/queue
# -----------------------
from dataclasses import asdict, is_dataclass
import csv
from pathlib import Path

# IMPORTANT: WorkOrder doit exister (ta debug montre que ENGINE.queue contient des WorkOrder)
from scheduler_core import WorkOrder  # si ImportError: dis-moi le nom exact de la classe



# -----------------------
# App init
# -----------------------

app = FastAPI(title="TECPAP Scheduler API", version="0.7")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "tecpap_synth_data")

ENGINE = load_engine_from_dir(DATA_DIR)
RUNNER = RealTimeRunner(ENGINE)

WORK_ORDERS_CSV = Path(DATA_DIR) / "work_orders.csv"
SETUP_MATRIX_CSV = Path(DATA_DIR) / "setup_matrix.csv"
MACHINE_HISTORY_CSV = Path(DATA_DIR) / "machine_history.csv"


def parse_iso(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Bad timestamp format: {ts}") from e


# -----------------------
# Debug endpoints
# -----------------------

@app.get("/debug/engine")
def debug_engine():
    """
    Inspect ENGINE to find any planning-related methods/attributes.
    """
    names = dir(ENGINE)
    keys = []
    for n in names:
        ln = n.lower()
        if any(k in ln for k in ["plan", "sched", "order", "queue", "job", "preview"]):
            keys.append(n)

    methods = []
    attrs = []
    for n in keys:
        try:
            v = getattr(ENGINE, n)
            if callable(v):
                try:
                    sig = str(inspect.signature(v))
                except Exception:
                    sig = "(?)"
                methods.append({"name": n, "signature": sig})
            else:
                sample = None
                if isinstance(v, list):
                    sample = {"len": len(v), "first_type": type(v[0]).__name__ if v else None}
                attrs.append({"name": n, "type": type(v).__name__, "sample": sample})
        except Exception as e:
            attrs.append({"name": n, "type": "ERROR", "sample": str(e)})

    return {
        "engine_type": type(ENGINE).__name__,
        "candidates_count": len(keys),
        "methods": methods[:80],
        "attrs": attrs[:80],
    }


@app.get("/debug/plan-error")
def debug_plan_error(limit: int = 5):
    """
    Force the planning extraction and return the real traceback in JSON.
    """
    try:
        rows = safe_get_plan_rows(limit=limit)
        sample = []
        for r in rows[: min(len(rows), 3)]:
            sample.append({
                "of_id": getattr(r, "of_id", None),
                "format": getattr(r, "format", None),
                "start": getattr(getattr(r, "start", None), "isoformat", lambda **k: None)(timespec="minutes")
                if getattr(r, "start", None) else None,
                "end": getattr(getattr(r, "end", None), "isoformat", lambda **k: None)(timespec="minutes")
                if getattr(r, "end", None) else None,
                "setup_min": getattr(r, "setup_min", None),
                "work_nominal_min": getattr(r, "work_nominal_min", None),
                "note": getattr(r, "note", None),
            })
        return {"ok": True, "count": len(rows), "sample": sample}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()}


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
    machine_id: Optional[str] = ""
    due_date: Optional[str] = ""


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
# Helpers
# -----------------------

def _maybe_build_plan(engine) -> None:
    """
    Certains moteurs ne construisent le planning qu'après un 'build' initial.
    On tente plusieurs noms de méthode (compat).
    """
    for method_name in ("build_initial_plan", "build_plan", "make_initial_plan", "init_plan", "ensure_plan"):
        fn = getattr(engine, method_name, None)
        if callable(fn):
            fn()
            return


def build_plan_preview_from_queue(limit: int = 30):
    """
    MVP: build a planning preview from ENGINE.queue (WorkOrders).
    This is a projected schedule (sequential) starting from ENGINE.now.
    """
    st = ENGINE.get_state()
    now = datetime.fromisoformat(st["now"])

    queue = getattr(ENGINE, "queue", None)
    if not isinstance(queue, list):
        raise AttributeError("ENGINE.queue is missing or not a list; cannot build plan preview.")

    t = now
    prev_format = st.get("current_format", None)

    # MVP defaults (can be refined later with real parameters)
    DEFAULT_SETUP_ON_CHANGE = 10   # minutes
    DEFAULT_WORK_MIN = 30          # minutes

    rows = []
    for wo in queue[:limit]:
        # Try common attributes for id/format/setup/work
        of_id = getattr(wo, "of_id", None) or getattr(wo, "id", None) or getattr(wo, "name", None) or "UNKNOWN"
        fmt = getattr(wo, "format", None) or getattr(wo, "fmt", None) or getattr(wo, "product_format", None) or ""

        setup_min = getattr(wo, "setup_min", None)
        if setup_min is None:
            setup_min = DEFAULT_SETUP_ON_CHANGE if (prev_format and fmt and fmt != prev_format) else 0
        setup_min = int(setup_min or 0)

        work_nominal_min = getattr(wo, "work_nominal_min", None)
        if work_nominal_min is None:
            # Attempt to derive from qty / rate if present
            qty = getattr(wo, "qty", None) or getattr(wo, "quantity", None)
            rate = getattr(wo, "rate_per_min", None) or getattr(wo, "speed_per_min", None)
            if qty is not None and rate not in (None, 0):
                try:
                    work_nominal_min = int(round(float(qty) / float(rate)))
                except Exception:
                    work_nominal_min = DEFAULT_WORK_MIN
            else:
                work_nominal_min = DEFAULT_WORK_MIN
        work_nominal_min = int(work_nominal_min or 0)

        start = t
        end = t + timedelta(minutes=setup_min + work_nominal_min)

        note = getattr(wo, "note", None)
        if not note:
            due = getattr(wo, "due_date", None)
            if due:
                try:
                    note = f"due={due.isoformat(timespec='minutes')}"
                except Exception:
                    note = "due=?"
            else:
                note = ""

        rows.append(SimpleNamespace(
            of_id=str(of_id),
            format=str(fmt),
            start=start,
            end=end,
            setup_min=setup_min,
            work_nominal_min=work_nominal_min,
            note=str(note),
        ))

        t = end
        prev_format = fmt

    return rows


def safe_get_plan_rows(limit: int = 30):
    """
    Return planning rows regardless of engine version.
    Priority:
    1) known planning methods
    2) known planning attributes
    3) build from queue (MVP)
    """
    candidate_methods = [
        "get_plan_preview",
        "plan_preview",
        "get_plan",
        "get_plan_rows",
        "get_planning_preview",
        "get_planning",
    ]

    for name in candidate_methods:
        fn = getattr(ENGINE, name, None)
        if callable(fn):
            try:
                return fn(limit=limit)
            except TypeError:
                return fn(limit)

    candidate_attrs = [
        "plan",
        "planning",
        "schedule",
        "current_plan",
        "current_schedule",
    ]
    for attr in candidate_attrs:
        val = getattr(ENGINE, attr, None)
        if isinstance(val, list):
            return val[:limit]

    # Attempt lazy build then re-try methods/attrs
    try:
        _maybe_build_plan(ENGINE)
        for name in candidate_methods:
            fn = getattr(ENGINE, name, None)
            if callable(fn):
                try:
                    return fn(limit=limit)
                except TypeError:
                    return fn(limit)
        for attr in candidate_attrs:
            val = getattr(ENGINE, attr, None)
            if isinstance(val, list):
                return val[:limit]
    except Exception:
        pass

    # MVP fallback: build from queue
    if isinstance(getattr(ENGINE, "queue", None), list):
        return build_plan_preview_from_queue(limit=limit)

    raise AttributeError(
        "No planning method/attribute found on SchedulerEngine and no queue fallback available. "
        "Expected one of: " + ", ".join(candidate_methods + candidate_attrs) + " or ENGINE.queue"
    )


# -----------------------
# Basic engine endpoints
# -----------------------

@app.get("/state")
def get_state():
    return ENGINE.get_state()


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




def _safe_dt_iso(x):
    if x is None:
        return ""
    try:
        return x.isoformat(timespec="minutes")
    except Exception:
        return str(x)

def _wo_to_dict(wo: WorkOrder) -> dict:
    # robuste: marche même si WorkOrder change
    if is_dataclass(wo):
        d = asdict(wo)
    else:
        d = wo.__dict__.copy()

    # normalise quelques champs usuels
    d["of_id"] = str(d.get("of_id", ""))
    d["format"] = str(d.get("format", ""))
    if "due_date" in d:
        d["due_date"] = _safe_dt_iso(d.get("due_date"))
    d["priority"] = int(d.get("priority", 0) or 0)
    return d

def _read_setup_matrix() -> dict[tuple[str, str], int]:
    """
    Lit setup_matrice.csv et retourne {(from_format, to_format): setup_min}
    Format attendu (tolérant):
      from_format,to_format,setup_min
    """
    m: dict[tuple[str, str], int] = {}
    if not SETUP_MATRIX_CSV.exists():
        return m

    with SETUP_MATRIX_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            a = (row.get("from_format") or row.get("from") or "").strip()
            b = (row.get("to_format") or row.get("to") or "").strip()
            v = row.get("setup_min") or row.get("setup") or row.get("minutes") or "0"
            if a and b:
                try:
                    m[(a, b)] = int(float(v))
                except Exception:
                    m[(a, b)] = 0
    return m

def _get_setup_minutes(setup_map, prev_fmt: str | None, next_fmt: str | None) -> int:
    if not prev_fmt or not next_fmt:
        return 0
    if prev_fmt == next_fmt:
        return 0
    return int(setup_map.get((prev_fmt, next_fmt), setup_map.get((prev_fmt, prev_fmt), 0) or 0))


def _read_machine_history_rows() -> list[dict]:
    """
    Lit machine_history.csv pour exposer l'historique TRS.
    """
    rows: list[dict] = []
    if not MACHINE_HISTORY_CSV.exists():
        return rows
    with MACHINE_HISTORY_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            mid = (r.get("machine_id") or "").strip()
            fmt = (r.get("format") or "").strip()
            if not mid or not fmt:
                continue
            try:
                trs = float(r.get("trs_percent") or r.get("trs") or 70.0)
            except Exception:
                trs = 70.0
            rows.append({
                "machine_id": mid,
                "format": fmt,
                "trs_percent": trs,
                "sample_count": r.get("sample_count"),
                "avg_setup_min": r.get("avg_setup_min"),
            })
    return rows

def _get_now_dt() -> datetime:
    st = ENGINE.get_state()
    return datetime.fromisoformat(st["now"])

def _work_nominal_min(wo: WorkOrder) -> int:
    # selon ton modèle : parfois c'est qty / speed, parfois champ direct.
    # On tente plusieurs noms usuels.
    for k in ["work_nominal_min", "work_min", "duration_min", "processing_min"]:
        v = getattr(wo, k, None)
        if v is not None:
            try:
                return int(v)
            except Exception:
                pass
    # fallback: 60 min par défaut
    return 60

def build_plan_preview_from_queue(limit: int = 30) -> list[dict]:
    """
    Construit un planning "preview" à partir de ENGINE.queue.
    Ne dépend pas d'une méthode de planning dans l'engine.
    """
    setup_map = _read_setup_matrix()
    now = _get_now_dt()

    # état machine: format courant (si tu le stockes)
    st = ENGINE.get_state()
    prev_fmt = st.get("current_format") or None

    rows = []
    t = now
    q = getattr(ENGINE, "queue", []) or []
    for wo in q[:limit]:
        fmt = getattr(wo, "format", None) or ""
        setup = _get_setup_minutes(setup_map, prev_fmt, fmt)
        start = t
        t = t + timedelta(minutes=setup)
        work = _work_nominal_min(wo)
        end = t + timedelta(minutes=work)

        rows.append({
            "of_id": str(getattr(wo, "of_id", "")),
            "format": str(fmt),
            "start": start.isoformat(timespec="minutes"),
            "end": end.isoformat(timespec="minutes"),
            "setup_min": int(setup),
            "work_nominal_min": int(work),
            "note": "preview_from_queue"
        })

        t = end
        prev_fmt = fmt

    return rows


# -----------------------
# API Schemas
# -----------------------
class WorkOrderOut(BaseModel):
    of_id: str
    format: str
    due_date: Optional[str] = ""
    priority: int = 0
    work_nominal_min: Optional[int] = None

class WorkOrderCreateIn(BaseModel):
    of_id: str
    format: str
    due_date: Optional[str] = None  # ISO: "2026-01-05T16:00"
    priority: int = 0
    work_nominal_min: int = 60      # durée nominale

class SetupMatrixUpsertIn(BaseModel):
    from_format: str
    to_format: str
    setup_min: int


# -----------------------
# Work Orders endpoints
# -----------------------
@app.get("/work-orders", response_model=List[WorkOrderOut])
def get_work_orders(limit: int = 200):
    q = getattr(ENGINE, "queue", []) or []
    out = []
    for wo in q[:limit]:
        d = _wo_to_dict(wo)
        out.append(WorkOrderOut(
            of_id=d.get("of_id", ""),
            format=d.get("format", ""),
            due_date=d.get("due_date", ""),
            priority=int(d.get("priority", 0) or 0),
            work_nominal_min=_work_nominal_min(wo),
        ))
    return out


import csv
from pathlib import Path
from datetime import datetime

def _read_csv_header(path: Path) -> list[str] | None:
    if not path.exists():
        return None
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return None
    header = [h.strip() for h in header if h.strip()]
    return header or None


def _append_work_order_csv(req: WorkOrderCreateIn):
    """
    Append a row using the *existing CSV header* so we never break scheduler_core.read_work_orders().
    If file doesn't exist yet, we create it with the minimum expected columns.
    """
    header = _read_csv_header(WORK_ORDERS_CSV)

    # If file doesn't exist, create a header that matches scheduler_core expectations.
    # We KNOW it expects created_at (from your traceback).
    if header is None:
        header = ["of_id", "format", "due_date", "priority", "created_at", "work_nominal_min"]

        with WORK_ORDERS_CSV.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)

    row = {h: "" for h in header}

    # Fill common fields if they exist in header
    if "of_id" in row:
        row["of_id"] = req.of_id
    if "format" in row:
        row["format"] = req.format
    if "due_date" in row and req.due_date:
        row["due_date"] = req.due_date
    if "priority" in row:
        row["priority"] = str(req.priority)
    if "work_nominal_min" in row:
        row["work_nominal_min"] = str(req.work_nominal_min)

    # IMPORTANT: created_at must be a valid ISO string
    if "created_at" in row:
        row["created_at"] = datetime.now().isoformat(timespec="minutes")

    # Write in correct order
    with WORK_ORDERS_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writerow(row)


@app.post("/work-orders", response_model=WorkOrderOut)
def create_work_order(req: WorkOrderCreateIn):
    # 1) persist CSV
    _append_work_order_csv(req)

    # 2) add into ENGINE.queue (et/ou pool si tu en as une)
    due = parse_iso(req.due_date) if req.due_date else parse_iso(ENGINE.get_state()["now"])
    wo = WorkOrder(
        of_id=req.of_id,
        format=req.format,
        due_date=due,
        priority=req.priority,
        work_nominal_min=req.work_nominal_min,  # si ton WorkOrder n'a pas ce champ, dis-moi son vrai nom
    )

    if hasattr(ENGINE, "queue") and isinstance(ENGINE.queue, list):
        ENGINE.queue.append(wo)

    # si ton moteur a une pool (optionnel)
    if hasattr(ENGINE, "pool") and isinstance(getattr(ENGINE, "pool"), list):
        ENGINE.pool.append(wo)

    # refresh si le moteur le prévoit
    if hasattr(ENGINE, "_refresh_queue_from_pool"):
        try:
            ENGINE._refresh_queue_from_pool()
        except Exception:
            pass

    return WorkOrderOut(
        of_id=req.of_id,
        format=req.format,
        due_date=_safe_dt_iso(due),
        priority=req.priority,
        work_nominal_min=req.work_nominal_min,
    )


# -----------------------
# Planning endpoints (override: use preview-from-queue)
# -----------------------
""" @app.get("/plan")
def get_plan(limit: int = 30):
    st = ENGINE.get_state()
    now = datetime.fromisoformat(st["now"])
    prev_fmt = st.get("current_format")

    rows = []
    t = now

    setup_map = _read_setup_matrix()
    for wo in ENGINE.queue[:limit]:
        fmt = getattr(wo, "format", "")
        of_id = getattr(wo, "of_id", "")

        setup = _get_setup_minutes(setup_map, prev_fmt, fmt)
        start = t
        t = t + timedelta(minutes=setup)

        work = getattr(wo, "work_nominal_min", 60)
        end = t + timedelta(minutes=int(work))

        rows.append({
            "of_id": str(of_id),
            "format": str(fmt),
            "start": start.isoformat(timespec="minutes"),
            "end": end.isoformat(timespec="minutes"),
            "setup_min": int(setup),
            "work_nominal_min": int(work),
            "note": "preview_from_queue"
        })

        t = end
        prev_fmt = fmt

    return rows
 """
""" @app.get("/plan")
def get_plan(limit: int = 30):
    return [{"note": "PLAN_ROUTE_V2", "of_id": "TEST", "format":"F1", "start":"x", "end":"y", "setup_min":1, "work_nominal_min":2}]


@app.get("/plan/export.csv")
def export_plan_csv(limit: int = 200):
    rows = build_plan_preview_from_queue(limit=limit)

    def esc(s: str) -> str:
        s = "" if s is None else str(s)
        if "," in s or '"' in s or "\n" in s:
            return '"' + s.replace('"', '""') + '"'
        return s

    lines = ["of_id,format,start,end,setup_min,work_nominal_min,note"]
    for r in rows:
        lines.append(",".join([
            esc(r["of_id"]),
            esc(r["format"]),
            esc(r["start"]),
            esc(r["end"]),
            esc(r["setup_min"]),
            esc(r["work_nominal_min"]),
            esc(r["note"]),
        ]))
    return Response(content="\n".join(lines), media_type="text/csv")
 """

# -----------------------
# (Optional) Setup matrix upsert
# -----------------------
@app.post("/setup-matrix")
def upsert_setup_matrix(req: SetupMatrixUpsertIn):
    # charge tout, update la clé, réécrit le CSV
    setup_map = _read_setup_matrix()
    setup_map[(req.from_format, req.to_format)] = int(req.setup_min)

    with SETUP_MATRIX_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["from_format", "to_format", "setup_min"])
        writer.writeheader()
        for (a, b), v in sorted(setup_map.items()):
            writer.writerow({"from_format": a, "to_format": b, "setup_min": v})

    return {"ok": True, "from_format": req.from_format, "to_format": req.to_format, "setup_min": req.setup_min}

# -----------------------
# Planning endpoints
# -----------------------

@app.get("/plan", response_model=List[PlanRowOut])
def get_plan(limit: int = 30):
    try:
        rows = safe_get_plan_rows(limit=limit)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"/plan failed: {type(e).__name__}: {e}. See /debug/plan-error for traceback."
        )

    def getv(r, key, default=""):
        # ✅ support dict rows AND object rows
        if isinstance(r, dict):
            return r.get(key, default)
        return getattr(r, key, default)

    def to_iso_minutes(x) -> str:
        # x can be datetime OR already a string
        if x is None:
            return ""
        if isinstance(x, str):
            return x
        try:
            return x.isoformat(timespec="minutes")
        except Exception:
            return ""

    out: List[PlanRowOut] = []
    for r in rows:
        out.append(
            PlanRowOut(
                of_id=str(getv(r, "of_id", "")),
                format=str(getv(r, "format", "")),
                start=to_iso_minutes(getv(r, "start", None)),
                end=to_iso_minutes(getv(r, "end", None)),
                setup_min=int(getv(r, "setup_min", 0) or 0),
                work_nominal_min=int(getv(r, "work_nominal_min", 0) or 0),
                note=str(getv(r, "note", "")),
                machine_id=str(getv(r, "machine_id", "") or ""),
                due_date=to_iso_minutes(getv(r, "due_date", None)),
            )
        )
    return out


@app.get("/plan/export.csv")
def export_plan_csv(limit: int = 200):
    rows = safe_get_plan_rows(limit=limit)

    def getv(r, key, default=""):
        if isinstance(r, dict):
            return r.get(key, default)
        return getattr(r, key, default)

    def to_iso_minutes(x) -> str:
        if x is None:
            return ""
        if isinstance(x, str):
            return x
        try:
            return x.isoformat(timespec="minutes")
        except Exception:
            return ""

    def esc(x) -> str:
        s = "" if x is None else str(x)
        if "," in s or '"' in s or "\n" in s:
            return '"' + s.replace('"', '""') + '"'
        return s

    lines = ["of_id,format,machine_id,due_date,start,end,setup_min,work_nominal_min,note"]

    for r in rows:
        lines.append(",".join([
            esc(getv(r, "of_id", "")),
            esc(getv(r, "format", "")),
            esc(getv(r, "machine_id", "")),
            esc(to_iso_minutes(getv(r, "due_date", None))),
            esc(to_iso_minutes(getv(r, "start", None))),
            esc(to_iso_minutes(getv(r, "end", None))),
            esc(getv(r, "setup_min", 0)),
            esc(getv(r, "work_nominal_min", 0)),
            esc(getv(r, "note", "")),
        ]))

    return Response(content="\n".join(lines), media_type="text/csv")

@app.get("/machines/history")
def get_machine_history():
    """
    Expose l'historique TRS par machine/format.
    """
    return {"items": _read_machine_history_rows()}


@app.get("/machines/state")
def get_machines_state():
    """
    Etat courant des machines (format courant, dispo).
    """
    machines = getattr(ENGINE, "machines", {}) or {}
    out = []
    for mid, st in machines.items():
        out.append({
            "machine_id": mid,
            "available_from": getattr(st.get("available_from"), "isoformat", lambda **k: None)(timespec="minutes") if isinstance(st, dict) else "",
            "current_format": st.get("current_format") if isinstance(st, dict) else None,
            "is_running": st.get("is_running", True) if isinstance(st, dict) else True,
            "is_down": st.get("is_down", False) if isinstance(st, dict) else False,
            "speed_factor": st.get("speed_factor", 1.0) if isinstance(st, dict) else 1.0,
        })
    return {"items": out, "now": ENGINE.get_state().get("now")}

from fastapi import Body
from datetime import datetime
from typing import Optional

import os

@app.get("/debug/pid")
def debug_pid():
    return {"pid": os.getpid()}


from collections import defaultdict
from datetime import datetime

# ... ReplanRequest ...
class ReplanRequest(BaseModel):
    now: Optional[str] = None
    strategy: str = "MULTI_MACHINE_TRS"  # stratégie unique

@app.post("/plan/recompute")
def recompute_plan(req: ReplanRequest = Body(default=ReplanRequest())):
    if req.now:
        ENGINE.set_time(parse_iso(req.now))

    q = list(getattr(ENGINE, "queue", []) or [])
    if not q:
        return {"ok": True, "changed": False, "reason": "empty_queue"}

    if not hasattr(ENGINE, "_replan_queue_multi"):
        raise HTTPException(status_code=500, detail="Engine does not support multi-machine replan")

    before = [getattr(x, "of_id", "") for x in q]
    candidate = ENGINE._replan_queue_multi(q)
    ENGINE.queue = candidate

    # calcul preview pour debug / front
    _, plan_rows = ENGINE._simulate_plan(candidate)
    total_setup = sum(getattr(r, "setup_min", 0) or 0 for r in plan_rows)

    after = [getattr(x, "of_id", "") for x in candidate]
    changed = before != after

    assignments = [
        {
            "of_id": getattr(r, "of_id", ""),
            "machine_id": getattr(r, "machine_id", ""),
            "start": getattr(getattr(r, "start", None), "isoformat", lambda **k: None)(timespec="minutes") if getattr(r, "start", None) else None,
            "end": getattr(getattr(r, "end", None), "isoformat", lambda **k: None)(timespec="minutes") if getattr(r, "end", None) else None,
        }
        for r in plan_rows
    ]

    return {
        "ok": True,
        "changed": changed,
        "strategy": "MULTI_MACHINE_TRS",
        "total_setup_min_est": total_setup,
        "before": before[:30],
        "after": after[:30],
        "assignments": assignments[:50],
    }

@app.get("/debug/setup")
def debug_setup(a: str = "F6", b: str = "F1"):
    setup_map = _read_setup_matrix()
    return {
        "a": a,
        "b": b,
        "setup_min": _get_setup_minutes(setup_map, a, b),
        "keys_sample": list(setup_map.keys())[:10],
    }

@app.get("/debug/queue")
def debug_queue(limit: int = 50):
    q = getattr(ENGINE, "queue", []) or []
    return {
        "len": len(q),
        "first": [getattr(x, "of_id", "") for x in q[:limit]]
    }
