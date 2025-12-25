from __future__ import annotations

import datetime as _dt
import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

_lock = threading.Lock()
_runner: Callable[[str, dict[str, Any]], list[dict[str, Any]]] | None = None
_thread: threading.Thread | None = None
_stop_event = threading.Event()


def _web_dir() -> Path:
    from .config import _autoglm_home  # 延迟导入避免循环

    return _autoglm_home() / "web"


def schedules_path() -> Path:
    return _web_dir() / "schedules.json"


def _log_line(text: str) -> None:
    try:
        from .autoglm_process import log_file

        lf = log_file()
        lf.parent.mkdir(parents=True, exist_ok=True)
        with lf.open("a", encoding="utf-8") as f:
            f.write(f"[{_now_beijing().strftime('%F %T')}] [scheduler] {text}\n")
    except Exception:
        pass


def _load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _dump_json(path: Path, data: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def list_schedules() -> list[dict[str, Any]]:
    with _lock:
        return _load_json(schedules_path())


def _find_index(items: list[dict[str, Any]], sched_id: str) -> int:
    for idx, it in enumerate(items):
        if it.get("id") == sched_id:
            return idx
    return -1


def upsert_schedule(sched: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        items = _load_json(schedules_path())
        if not sched.get("id"):
            sched["id"] = uuid.uuid4().hex
        # 规范化字段
        sched.setdefault("enabled", True)
        sched.setdefault("last_run_ts", 0)
        sched.setdefault("history", [])
        idx = _find_index(items, sched["id"])
        if idx >= 0:
            items[idx] = sched
        else:
            items.append(sched)
        _dump_json(schedules_path(), items)
        return sched


def update_schedule_run_state(sched_id: str, last_run_ts: int, history: list[dict[str, Any]]) -> bool:
    if not sched_id:
        return False
    with _lock:
        items = _load_json(schedules_path())
        idx = _find_index(items, sched_id)
        if idx < 0:
            return False
        item = items[idx]
        item["last_run_ts"] = int(last_run_ts or 0)
        item["history"] = history or []
        items[idx] = item
        _dump_json(schedules_path(), items)
        return True


def delete_schedule(sched_id: str) -> bool:
    with _lock:
        items = _load_json(schedules_path())
        new_items = [it for it in items if it.get("id") != sched_id]
        changed = len(new_items) != len(items)
        if changed:
            _dump_json(schedules_path(), new_items)
        return changed


def _parse_field(field: str, min_v: int, max_v: int) -> set[int]:
    """
    解析单个 cron 字段，支持 *, */n, 逗号、范围。输入已 strip。
    """
    values: set[int] = set()
    if field == "*":
        return set(range(min_v, max_v + 1))
    for part in field.split(","):
        part = part.strip()
        if not part:
            continue
        step = 1
        if "/" in part:
            base, step_s = part.split("/", 1)
            try:
                step = int(step_s)
            except Exception:
                return set()
            part = base or "*"
        if part == "*":
            start, end = min_v, max_v
        elif "-" in part:
            a, b = part.split("-", 1)
            try:
                start, end = int(a), int(b)
            except Exception:
                return set()
        else:
            try:
                val = int(part)
            except Exception:
                return set()
            start = end = val
        start = max(min_v, start)
        end = min(max_v, end)
        if step <= 0:
            return set()
        for v in range(start, end + 1, step):
            values.add(v)
    return values


def _matches(cron: str, dt: _dt.datetime) -> bool:
    """
    6 字段秒级 cron: sec min hour dom month dow（周日=0/7）。要求全部匹配。
    """
    parts = [p.strip() for p in cron.strip().split()]
    if len(parts) != 6:
        return False
    sec_s, min_s, hour_s, dom_s, month_s, dow_s = parts
    try:
        sec_ok = dt.second in _parse_field(sec_s, 0, 59)
        min_ok = dt.minute in _parse_field(min_s, 0, 59)
        hour_ok = dt.hour in _parse_field(hour_s, 0, 23)
        dom_ok = dt.day in _parse_field(dom_s, 1, 31)
        month_ok = dt.month in _parse_field(month_s, 1, 12)
        dow_vals = _parse_field(dow_s, 0, 7)
        cron_dow = (dt.weekday() + 1) % 7  # 周日=0，其余 1-6
        if 7 in dow_vals:
            dow_vals.add(0)
        dow_ok = cron_dow in dow_vals
        return bool(sec_ok and min_ok and hour_ok and dom_ok and month_ok and dow_ok)
    except Exception:
        return False


def is_valid_cron(expr: str) -> bool:
    parts = expr.strip().split()
    if len(parts) != 6:
        return False
    ranges = [(0, 59), (0, 59), (0, 23), (1, 31), (1, 12), (0, 7)]
    for field, (lo, hi) in zip(parts, ranges):
        if not _parse_field(field.strip(), lo, hi):
            return False
    return True


def _cron_sets(expr: str) -> tuple[set[int], set[int], set[int], set[int], set[int], set[int]] | None:
    parts = expr.strip().split()
    if len(parts) != 6:
        return None
    ranges = [(0, 59), (0, 59), (0, 23), (1, 31), (1, 12), (0, 7)]
    values: list[set[int]] = []
    for field, (lo, hi) in zip(parts, ranges):
        parsed = _parse_field(field.strip(), lo, hi)
        if not parsed:
            return None
        values.append(parsed)
    return values[0], values[1], values[2], values[3], values[4], values[5]


def next_run_ts(expr: str, now: _dt.datetime | None = None, max_scan_seconds: int = 31 * 24 * 3600) -> int:
    fields = _cron_sets(expr)
    if not fields:
        return 0
    sec_set, min_set, hour_set, dom_set, month_set, dow_set = fields
    if 7 in dow_set:
        dow_set = set(dow_set)
        dow_set.add(0)
    if now is None:
        now = _now_beijing()
    start = now + _dt.timedelta(seconds=1)
    for offset in range(max_scan_seconds):
        dt = start + _dt.timedelta(seconds=offset)
        if dt.second not in sec_set:
            continue
        if dt.minute not in min_set:
            continue
        if dt.hour not in hour_set:
            continue
        if dt.day not in dom_set:
            continue
        if dt.month not in month_set:
            continue
        cron_dow = (dt.weekday() + 1) % 7
        if cron_dow not in dow_set:
            continue
        return int(dt.timestamp())
    return 0


def _now_beijing() -> _dt.datetime:
    tz = _dt.timezone(_dt.timedelta(hours=8))
    return _dt.datetime.now(tz=tz)


def configure_runner(fn: Callable[[str, dict[str, Any]], list[dict[str, Any]]]) -> None:
    global _runner
    _runner = fn


def _record_result(sched: dict[str, Any], ok: bool, output: str) -> None:
    history = sched.get("history") or []
    entry = {
        "ts": int(_now_beijing().timestamp()),
        "ok": bool(ok),
        "output": output,
    }
    history.append(entry)
    history = history[-10:]
    sched["history"] = history
    sched["last_run_ts"] = entry["ts"]
    _log_line(f"{sched.get('id') or '(new)'} -> {'OK' if ok else 'FAIL'}")


def _run_once(sched: dict[str, Any]) -> None:
    if _runner is None:
        return
    task_id = sched.get("task_id", "")
    try:
        results = _runner(task_id, {})
        ok = all(r.get("ok", True) for r in results)
        out_lines = []
        for r in results:
            t = str(r.get("type") or "step")
            o = str(r.get("output") or "")
            out_lines.append(f"{t}: {o}")
        output = "\n".join(out_lines) if out_lines else "(无输出)"
        _record_result(sched, ok, output)
    except Exception as e:
        _record_result(sched, False, str(e))


def _tick_loop() -> None:
    running_tasks: set[str] = set()
    while not _stop_event.is_set():
        now = _now_beijing()
        try:
            items = list_schedules()
            for sched in items:
                if not sched.get("enabled", True):
                    continue
                cron = str(sched.get("cron", "") or "").strip()
                task_id = str(sched.get("task_id", "") or "").strip()
                if not cron or not task_id:
                    continue
                # 跳过同一任务并发
                if task_id in running_tasks:
                    continue
                last_ts = int(sched.get("last_run_ts", 0) or 0)
                if int(now.timestamp()) == last_ts:
                    continue
                if not _matches(cron, now):
                    continue
                running_tasks.add(task_id)
                try:
                    _run_once(sched)
                    update_schedule_run_state(
                        str(sched.get("id") or ""),
                        int(sched.get("last_run_ts", 0) or 0),
                        sched.get("history") or [],
                    )
                finally:
                    running_tasks.discard(task_id)
        except Exception:
            # 守护线程保持运行
            pass
        time.sleep(1)


def ensure_scheduler_started() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_tick_loop, name="autoglm-scheduler", daemon=True)
    _thread.start()


def stop_scheduler() -> None:
    _stop_event.set()
    if _thread and _thread.is_alive():
        _thread.join(timeout=2)
