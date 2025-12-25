# realtime_runner.py
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from scheduler_core import SchedulerEngine, Event


@dataclass
class RunnerConfig:
    day_start: datetime
    day_end: datetime
    compress_to_seconds: int = 600  # 10 minutes by default
    tick_seconds: float = 0.5       # update frequency (wall clock)


class RealTimeRunner:
    """
    Runs a simulation "in real-time" (compressed), advancing the engine continuously.
    Produces hourly reports according to simulated time.
    """

    def __init__(self, engine: SchedulerEngine):
        self.engine = engine
        self._lock = threading.Lock()

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._running = False
        self._config: Optional[RunnerConfig] = None

        self._hourly_reports: List[Dict[str, Any]] = []
        self._next_report_time: Optional[datetime] = None

    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def start(
        self,
        cfg: RunnerConfig,
        on_started: Optional[Callable[[SchedulerEngine], None]] = None,
    ) -> Dict[str, Any]:
        """
        Start the realtime compressed simulation.
        `on_started(engine)` is called AFTER engine init (set_time + SHIFT_START),
        so you can re-apply an ordering / recompute strategy without it being reset.
        """
        with self._lock:
            if self._running:
                return {"status": "already_running"}

            self._config = cfg
            self._hourly_reports = []
            self._next_report_time = cfg.day_start

            # reset engine to start
            self.engine.set_time(cfg.day_start)

            # initialize shift
            self.engine.handle_event(
                Event(timestamp=cfg.day_start, type="SHIFT_START", value=""),
                source="realtime/auto",
            )

        # IMPORTANT: run on_started outside the lock to avoid deadlocks
        if on_started is not None:
            try:
                on_started(self.engine)
            except Exception as e:
                # Do not block startup; just report warning
                with self._lock:
                    self._stop_event.clear()
                    self._thread = threading.Thread(target=self._loop, daemon=True)
                    self._running = True
                    self._thread.start()
                return {"status": "started_with_warning", "warning": str(e)}

        with self._lock:
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._running = True
            self._thread.start()

            return {"status": "started"}

    def stop(self) -> Dict[str, Any]:
        with self._lock:
            if not self._running:
                return {"status": "not_running"}
            self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=2.0)

        with self._lock:
            self._running = False
            return {"status": "stopped"}

    def state(self) -> Dict[str, Any]:
        st = self.engine.get_state()
        with self._lock:
            cfg = self._config
            running = self._running
            next_r = (
                self._next_report_time.isoformat(timespec="minutes")
                if self._next_report_time
                else None
            )

        return {
            "runner": {
                "running": running,
                "day_start": cfg.day_start.isoformat(timespec="minutes") if cfg else None,
                "day_end": cfg.day_end.isoformat(timespec="minutes") if cfg else None,
                "compress_to_seconds": cfg.compress_to_seconds if cfg else None,
                "tick_seconds": cfg.tick_seconds if cfg else None,
                "next_report_time": next_r,
            },
            "engine": st,
        }

    def hourly_reports(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._hourly_reports)

    # ------------- internal -------------
    def _loop(self):
        with self._lock:
            cfg = self._config
        if cfg is None:
            return

        total_sim_minutes = int((cfg.day_end - cfg.day_start).total_seconds() // 60)
        total_real_seconds = max(1, int(cfg.compress_to_seconds))

        sim_minutes_per_sec = total_sim_minutes / float(total_real_seconds)

        tick = max(0.1, float(cfg.tick_seconds))
        sim_minutes_per_tick = sim_minutes_per_sec * tick

        acc = 0.0

        while not self._stop_event.is_set():
            now_sim = datetime.fromisoformat(self.engine.get_state()["now"])

            if now_sim >= cfg.day_end:
                break

            acc += sim_minutes_per_tick
            step_min = int(acc)

            if step_min > 0:
                acc -= step_min
                self.engine.set_time(now_sim + timedelta(minutes=step_min))
                self._maybe_push_reports()

            time.sleep(tick)

        with self._lock:
            self._running = False

    def _make_hourly_snapshot(self) -> Dict[str, Any]:
        """
        SchedulerEngine n'a pas forcément get_hourly_report().
        On fabrique donc un "rapport" stable basé sur get_state().
        """
        st = self.engine.get_state()
        # st contient déjà kpi, breakdown, queue_size, etc.
        return {
            "time": st.get("now"),
            "machine": {
                "is_running": st.get("is_running"),
                "is_down": st.get("is_down"),
                "speed_factor": st.get("speed_factor"),
                "current_format": st.get("current_format"),
                "current_job_id": (st.get("current_job") or {}).get("of_id") if isinstance(st.get("current_job"), dict) else None,
            },
            "queue_size": st.get("queue_size"),
            "pool_remaining": st.get("pool_remaining"),
            "kpi": st.get("kpi"),
            "breakdown": st.get("breakdown"),
        }

    def _maybe_push_reports(self):
        """
        Push report each time simulated time passes the next hour mark.
        """
        with self._lock:
            if self._config is None or self._next_report_time is None:
                return
            cfg = self._config
            next_report = self._next_report_time

        now_sim = datetime.fromisoformat(self.engine.get_state()["now"])

        while now_sim >= next_report:
            rep = self._make_hourly_snapshot()
            with self._lock:
                self._hourly_reports.append(rep)
                next_report = next_report + timedelta(hours=1)
                self._next_report_time = next_report

            if next_report > cfg.day_end:
                break
