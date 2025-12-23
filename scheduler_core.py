# scheduler_core.py
import csv
import copy
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any


# =========================
# Models
# =========================

@dataclass
class WorkOrder:
    of_id: str
    created_at: datetime
    due_date: datetime
    priority: int
    product: str
    format: str
    qty: int
    nominal_rate_u_per_h: int
    nominal_duration_min: int  # nominal minutes at speed=1.0


@dataclass
class Event:
    timestamp: datetime
    type: str
    value: str = ""


@dataclass
class IncomingEvent:
    receive_time: datetime
    event: Event
    source: str = "simulation"


class SetupMatrix:
    def __init__(self, setup_min: Dict[str, Dict[str, int]]):
        self.setup_min = setup_min

    def get(self, from_fmt: Optional[str], to_fmt: str) -> int:
        if from_fmt is None:
            return 0
        return self.setup_min.get(from_fmt, {}).get(to_fmt, 0)


@dataclass
class PlanRow:
    of_id: str
    format: str
    start: datetime
    end: datetime
    setup_min: int
    work_nominal_min: int
    note: str


# =========================
# Parsing helpers
# =========================

def parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts)

def read_work_orders(path: Path) -> List[WorkOrder]:
    out: List[WorkOrder] = []
    with path.open("r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            out.append(WorkOrder(
                of_id=row["of_id"],
                created_at=parse_iso(row["created_at"]),
                due_date=parse_iso(row["due_date"]),
                priority=int(row["priority"]),
                product=row["product"],
                format=row["format"],
                qty=int(row["qty"]),
                nominal_rate_u_per_h=int(row["nominal_rate_u_per_h"]),
                nominal_duration_min=int(row["nominal_duration_min"]),
            ))
    return out

def read_setup_matrix(path: Path) -> SetupMatrix:
    mat: Dict[str, Dict[str, int]] = {}
    with path.open("r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            ff = row["from_format"]
            tf = row["to_format"]
            mat.setdefault(ff, {})[tf] = int(row["setup_min"])
    return SetupMatrix(mat)

def parse_urgent_payload(payload: str, created_at: datetime) -> WorkOrder:
    kv: Dict[str, str] = {}
    for part in [p.strip() for p in payload.split(";") if p.strip()]:
        if "=" in part:
            k, v = part.split("=", 1)
            kv[k.strip()] = v.strip()

    due = parse_iso(kv["due"])
    fmt = kv["format"]
    qty = int(kv["qty"])
    rate = int(kv["nominal_rate"])
    dur = int(kv["duration_min"])
    prio = int(kv.get("priority", "5"))

    return WorkOrder(
        of_id=kv["of_id"],
        created_at=created_at,
        due_date=due,
        priority=prio,
        product=f"PRODUCT_{fmt}",
        format=fmt,
        qty=qty,
        nominal_rate_u_per_h=rate,
        nominal_duration_min=dur,
    )


# =========================
# Scheduler engine
# =========================

class SchedulerEngine:
    """
    Key change (Correction B):
    - Breakdown events trigger replanning ONLY if downtime duration >= 30 min.
    """

    def __init__(self, work_orders: List[WorkOrder], setup: SetupMatrix):
        self._lock = threading.Lock()
        self.setup = setup

        self._pool: List[WorkOrder] = list(work_orders)

        # machine time/state
        self.now: datetime = min((o.created_at for o in self._pool), default=datetime.now())
        self.is_running: bool = False
        self.is_down: bool = False
        self.speed_factor: float = 1.0
        self.current_format: Optional[str] = None

        # current job
        self.current_job: Optional[WorkOrder] = None
        self.remaining_setup_min: int = 0
        self.remaining_work_nominal_min: int = 0
        self._work_acc: float = 0.0

        # queue
        self.queue: List[WorkOrder] = []

        # late events policy
        self.max_event_lateness_min: int = 120
        self.late_policy: str = "APPLY_NOW"  # APPLY_NOW or IGNORE

        # replanning policy
        self.replan_threshold_total_late_min: int = 30  # KPI-based (still used for non-breakdown)
        self.breakdown_replan_threshold_min: int = 30   # NEW: downtime duration threshold

        # breakdown tracking
        self._down_start_time: Optional[datetime] = None
        self._down_reason: str = ""
        self._last_breakdown_duration_min: int = 0

        # journal
        self._event_log: List[Dict[str, Any]] = []

        # KPI counters
        self._downtime_min: int = 0
        self._stopped_min: int = 0
        self._idle_min: int = 0
        self._producing_min: int = 0
        self._completed: List[Dict[str, Any]] = []

        self._refresh_queue_from_pool()

    # ----- deepcopy helper (fix cannot pickle lock) -----
    def __getstate__(self):
        state = self.__dict__.copy()
        state.pop("_lock", None)
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._lock = threading.Lock()

    def clone(self) -> "SchedulerEngine":
        with self._lock:
            return copy.deepcopy(self)

    # ---------- Public ----------
    def set_time(self, new_now: datetime) -> Dict[str, str]:
        with self._lock:
            self._advance_to(new_now)
            self._refresh_queue_from_pool()
            self._start_next_if_possible()
            return {"status": "ok", "now": self.now.isoformat(timespec="minutes")}

    def handle_event(self, ev: Event, source: str = "events") -> Dict[str, Any]:
        with self._lock:
            return self._handle_event_locked(ev=ev, source=source, received_at=self.now)

    def handle_incoming(self, inc: IncomingEvent) -> Dict[str, Any]:
        with self._lock:
            # advance to receive time first (realistic)
            self._advance_to(inc.receive_time)
            self._refresh_queue_from_pool()
            self._start_next_if_possible()
            return self._handle_event_locked(ev=inc.event, source=inc.source, received_at=inc.receive_time)

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "now": self.now.isoformat(timespec="minutes"),
                "is_running": self.is_running,
                "is_down": self.is_down,
                "speed_factor": self.speed_factor,
                "current_format": self.current_format,
                "current_job": None if self.current_job is None else {
                    "of_id": self.current_job.of_id,
                    "format": self.current_job.format,
                    "due_date": self.current_job.due_date.isoformat(timespec="minutes"),
                    "priority": self.current_job.priority,
                },
                "remaining_setup_min": self.remaining_setup_min,
                "remaining_work_nominal_min": self.remaining_work_nominal_min,
                "queue_size": len(self.queue),
                "pool_remaining": len(self._pool),
                "breakdown": {
                    "down_start_time": None if self._down_start_time is None else self._down_start_time.isoformat(timespec="minutes"),
                    "down_reason": self._down_reason,
                    "last_breakdown_duration_min": self._last_breakdown_duration_min,
                    "replan_threshold_min": self.breakdown_replan_threshold_min
                },
                "kpi": {
                    "downtime_min": self._downtime_min,
                    "stopped_min": self._stopped_min,
                    "idle_min": self._idle_min,
                    "producing_min": self._producing_min,
                    "completed_count": len(self._completed),
                }
            }

    def get_event_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            return self._event_log[-max(1, limit):]

    # ---------- Internal ----------
    def _handle_event_locked(self, ev: Event, source: str, received_at: datetime) -> Dict[str, Any]:
        log_entry = {
            "received_at": received_at.isoformat(timespec="minutes"),
            "source": source,
            "engine_now_before": self.now.isoformat(timespec="minutes"),
            "event_timestamp": ev.timestamp.isoformat(timespec="minutes"),
            "type": ev.type,
            "value": ev.value,
            "status": "ok",
            "reason": "",
            "late_applied": False,
            "replanned": False,
            "replan_reason": "",
            "breakdown_duration_min": None,
            "engine_now_after": "",
        }

        # advance if event is in the future
        if ev.timestamp > self.now:
            self._advance_to(ev.timestamp)
            self._refresh_queue_from_pool()

        # late event handling
        if ev.timestamp < self.now:
            lateness = int((self.now - ev.timestamp).total_seconds() // 60)

            if lateness > self.max_event_lateness_min:
                log_entry["status"] = "ignored"
                log_entry["reason"] = f"late event too old ({lateness}min > {self.max_event_lateness_min})"
                log_entry["engine_now_after"] = self.now.isoformat(timespec="minutes")
                self._event_log.append(log_entry)
                return log_entry

            if self.late_policy.upper() == "IGNORE":
                log_entry["status"] = "ignored"
                log_entry["reason"] = f"late event ignored by policy (lateness={lateness}min)"
                log_entry["engine_now_after"] = self.now.isoformat(timespec="minutes")
                self._event_log.append(log_entry)
                return log_entry

            log_entry["late_applied"] = True

        # apply event
        # (also sets breakdown tracking fields)
        breakdown_duration_min = self._apply_event(ev)
        if breakdown_duration_min is not None:
            log_entry["breakdown_duration_min"] = breakdown_duration_min

        self._refresh_queue_from_pool()

        # Decide replanning
        replanned, why = self._should_and_maybe_replan(ev, breakdown_duration_min)
        log_entry["replanned"] = replanned
        log_entry["replan_reason"] = why

        self._start_next_if_possible()
        log_entry["engine_now_after"] = self.now.isoformat(timespec="minutes")

        self._event_log.append(log_entry)
        return log_entry

    def _should_and_maybe_replan(self, ev: Event, breakdown_duration_min: Optional[int]) -> (bool, str):
        """
        New rule:
        - For breakdowns: only if downtime duration >= breakdown_replan_threshold_min
        - For urgent orders: always try
        - For speed change: treat as critical (KPI based)
        - For shift: no replan
        """
        t = ev.type.upper().strip()

        # Breakdown logic (the core of correction B)
        if t in {"BREAKDOWN_START", "BREAKDOWN_END"}:
            # if we do not know duration yet (start), we don't replan
            if breakdown_duration_min is None:
                return (False, "breakdown_start_no_duration")

            if breakdown_duration_min < self.breakdown_replan_threshold_min:
                return (False, f"breakdown_duration<{self.breakdown_replan_threshold_min}min")

            # downtime is big enough => replan
            changed = self._maybe_replan(reason="BREAKDOWN_MAJOR")
            return (changed, f"breakdown_duration>={self.breakdown_replan_threshold_min}min")

        # urgent => always try
        if t == "URGENT_ORDER":
            changed = self._maybe_replan(reason="URGENT_ORDER")
            return (changed, "urgent_order")

        # speed change => KPI-based
        if t == "SPEED_CHANGE":
            changed = self._maybe_replan(reason="SPEED_CHANGE")
            return (changed, "speed_change")

        return (False, "not_critical")

    def _refresh_queue_from_pool(self):
        existing_ids = {wo.of_id for wo in self.queue}
        if self.current_job:
            existing_ids.add(self.current_job.of_id)

        newly_added: List[WorkOrder] = []
        remaining_pool: List[WorkOrder] = []

        for wo in self._pool:
            if wo.created_at <= self.now and wo.of_id not in existing_ids:
                newly_added.append(wo)
                existing_ids.add(wo.of_id)
            else:
                remaining_pool.append(wo)

        self._pool = remaining_pool
        self.queue.extend(newly_added)
        self.queue.sort(key=lambda x: (x.due_date, -x.priority))

    def _advance_to(self, target: datetime):
        if target <= self.now:
            self.now = target
            return
        dt_total = int((target - self.now).total_seconds() // 60)
        for _ in range(dt_total):
            self._advance_one_minute()
        self.now = target

    def _advance_one_minute(self):
        # KPI counters
        if self.is_down:
            self._downtime_min += 1
        elif not self.is_running:
            self._stopped_min += 1
        else:
            if self.current_job is None:
                self._idle_min += 1
            else:
                self._producing_min += 1

        # no progress
        if self.is_down or (not self.is_running) or self.current_job is None:
            self.now += timedelta(minutes=1)
            return

        # setup
        if self.remaining_setup_min > 0:
            self.remaining_setup_min -= 1
            self.now += timedelta(minutes=1)
            return

        # work
        self._work_acc += float(self.speed_factor)
        consume_nom = int(self._work_acc)
        if consume_nom > 0:
            self._work_acc -= consume_nom
            self.remaining_work_nominal_min = max(0, self.remaining_work_nominal_min - consume_nom)

        self.now += timedelta(minutes=1)

        # finish
        if self.remaining_setup_min == 0 and self.remaining_work_nominal_min == 0:
            finished_id = self.current_job.of_id
            self.current_format = self.current_job.format
            self.current_job = None
            self._work_acc = 0.0
            self._completed.append({"of_id": finished_id, "finished_at": self.now.isoformat(timespec="minutes")})

    def _apply_event(self, ev: Event) -> Optional[int]:
        """
        Returns breakdown duration minutes only when BREAKDOWN_END occurs and we have a start.
        Otherwise returns None.
        """
        t = ev.type.upper().strip()

        if t == "SHIFT_START":
            self.is_running = True
            return None

        if t == "SHIFT_STOP":
            self.is_running = False
            return None

        if t == "SPEED_CHANGE":
            try:
                sf = float(ev.value)
                if sf > 0:
                    self.speed_factor = sf
            except ValueError:
                pass
            return None

        if t == "URGENT_ORDER":
            urgent = parse_urgent_payload(ev.value, created_at=self.now)
            self.queue.append(urgent)
            self.queue.sort(key=lambda x: (x.due_date, -x.priority))
            return None

        if t == "BREAKDOWN_START":
            self.is_down = True
            # Track start time ONLY when entering downtime
            if self._down_start_time is None:
                self._down_start_time = self.now
                self._down_reason = ev.value or ""
            return None

        if t == "BREAKDOWN_END":
            # end downtime
            self.is_down = False
            # compute duration if we know start
            if self._down_start_time is not None:
                duration = int((self.now - self._down_start_time).total_seconds() // 60)
                self._last_breakdown_duration_min = max(0, duration)
                # reset
                self._down_start_time = None
                self._down_reason = ""
                return self._last_breakdown_duration_min
            return 0

        # unknown
        return None

    def _start_next_if_possible(self):
        if self.current_job is not None:
            return
        if self.is_down or (not self.is_running):
            return
        if not self.queue:
            return

        wo = self.queue.pop(0)
        setup_min = self.setup.get(self.current_format, wo.format)
        self.current_job = wo
        self.remaining_setup_min = setup_min
        self.remaining_work_nominal_min = wo.nominal_duration_min
        self._work_acc = 0.0

    # ---------- Replanning ----------
    def _maybe_replan(self, reason: str) -> bool:
        before = self._kpi_total_lateness(self.queue)
        candidate = self._replan_queue(self.queue)
        after = self._kpi_total_lateness(candidate)

        changed = [w.of_id for w in candidate] != [w.of_id for w in self.queue]
        if not changed:
            return False

        if after < before:
            self.queue = candidate
            return True

        if reason.upper() == "URGENT_ORDER":
            self.queue = candidate
            return True

        if (after - before) > self.replan_threshold_total_late_min:
            self.queue = candidate
            return True

        return False

    def _kpi_total_lateness(self, queue: List[WorkOrder]) -> int:
        sim_now = self.now
        sim_fmt = self.current_format
        sim_speed = self.speed_factor

        total_late = 0
        for wo in queue:
            setup_min = self.setup.get(sim_fmt, wo.format)
            real_work_min = int(wo.nominal_duration_min / max(sim_speed, 1e-6))
            finish = sim_now + timedelta(minutes=setup_min + real_work_min)
            late = max(0, int((finish - wo.due_date).total_seconds() // 60))
            total_late += late
            sim_now = finish
            sim_fmt = wo.format
        return total_late

    def _replan_queue(self, queue: List[WorkOrder]) -> List[WorkOrder]:
        remaining = queue[:]
        new_q: List[WorkOrder] = []
        sim_now = self.now
        sim_fmt = self.current_format

        while remaining:
            best = min(remaining, key=lambda wo: self._score(sim_now, sim_fmt, wo))
            remaining.remove(best)
            new_q.append(best)

            setup_min = self.setup.get(sim_fmt, best.format)
            real_work_min = int(best.nominal_duration_min / max(self.speed_factor, 1e-6))
            sim_now = sim_now + timedelta(minutes=setup_min + real_work_min)
            sim_fmt = best.format

        return new_q

    def _score(self, now: datetime, current_format: Optional[str], wo: WorkOrder) -> float:
        setup_min = self.setup.get(current_format, wo.format)
        real_work_min = int(wo.nominal_duration_min / max(self.speed_factor, 1e-6))
        finish = now + timedelta(minutes=setup_min + real_work_min)
        late_min = max(0, int((finish - wo.due_date).total_seconds() // 60))

        W_LATE = 2.5
        W_SETUP = 0.8
        W_PRIO = 20.0

        return (W_LATE * late_min) + (W_SETUP * setup_min) - (W_PRIO * wo.priority)

    # ---------- Day simulation ----------
    def simulate_day(self,
                     day_start: datetime,
                     day_end: datetime,
                     incoming_events: List[IncomingEvent],
                     report_every_min: int = 60) -> Dict[str, Any]:
        sim = self.clone()
        sim.set_time(day_start)

        incoming_events = sorted(incoming_events, key=lambda x: x.receive_time)
        idx = 0

        reports: List[Dict[str, Any]] = []
        next_report = day_start

        stats = {
            "events_received": len(incoming_events),
            "events_applied": 0,
            "events_ignored": 0,
            "late_events_applied": 0,
            "replans": 0,
            "breakdown_replans": 0
        }

        t = day_start
        while t <= day_end:
            # process all incoming events up to time t
            while idx < len(incoming_events) and incoming_events[idx].receive_time <= t:
                res = sim.handle_incoming(incoming_events[idx])
                if res.get("status") == "ignored":
                    stats["events_ignored"] += 1
                else:
                    stats["events_applied"] += 1
                if res.get("late_applied"):
                    stats["late_events_applied"] += 1
                if res.get("replanned"):
                    stats["replans"] += 1
                    if res.get("replan_reason", "").startswith("breakdown_duration"):
                        stats["breakdown_replans"] += 1
                idx += 1

            # advance to current minute
            sim._advance_to(t)

            # hourly report
            if t >= next_report:
                reports.append(sim._hourly_report_snapshot())
                next_report = next_report + timedelta(minutes=report_every_min)

            t = t + timedelta(minutes=1)

        return {
            "day_start": day_start.isoformat(timespec="minutes"),
            "day_end": day_end.isoformat(timespec="minutes"),
            "late_policy": sim.late_policy,
            "max_event_lateness_min": sim.max_event_lateness_min,
            "breakdown_replan_threshold_min": sim.breakdown_replan_threshold_min,
            "stats": stats,
            "reports": reports,
            "last_state": sim.get_state(),
            "event_log_tail": sim.get_event_log(limit=50),
        }

    def _hourly_report_snapshot(self) -> Dict[str, Any]:
        total_late = self._kpi_total_lateness(self.queue)
        return {
            "time": self.now.isoformat(timespec="minutes"),
            "machine": {
                "is_running": self.is_running,
                "is_down": self.is_down,
                "speed_factor": self.speed_factor,
                "current_format": self.current_format,
                "current_job_id": None if self.current_job is None else self.current_job.of_id,
            },
            "queue_size": len(self.queue),
            "completed_count": len(self._completed),
            "total_lateness_min_est": total_late,
            "counters_min": {
                "downtime": self._downtime_min,
                "stopped": self._stopped_min,
                "idle": self._idle_min,
                "producing": self._producing_min,
            }
        }


def load_engine_from_dir(data_dir: str) -> SchedulerEngine:
    d = Path(data_dir)
    orders = read_work_orders(d / "work_orders.csv")
    setup = read_setup_matrix(d / "setup_matrix.csv")
    engine = SchedulerEngine(orders, setup)
    t0 = min((o.created_at for o in orders), default=datetime.now())
    engine.set_time(t0)
    return engine
