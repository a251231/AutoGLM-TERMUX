from __future__ import annotations

import os
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from . import adb
from . import autoglm_process
from . import schedule
from .config import config_sh_path, read_config
from .storage import find_by_id, list_tasks


def _log_line(text: str) -> None:
    lf = autoglm_process.log_file()
    lf.parent.mkdir(parents=True, exist_ok=True)
    with lf.open("a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%F %T')}] {text}\n")


def _autoglm_dir() -> Path:
    return Path(os.environ.get("AUTOGLM_DIR", str(Path.home() / "Open-AutoGLM"))).expanduser()


def ensure_autoglm_running() -> None:
    st = autoglm_process.status()
    if not st.running:
        cfg = read_config()
        key = str(cfg.api_key or "").strip()
        if not key or key in {"sk-your-apikey", "EMPTY"}:
            raise RuntimeError(f"API Key 未配置：请在 {config_sh_path()} 填写有效密钥或通过 Web 界面保存配置")
        ok, msg = autoglm_process.start(cfg)
        _log_line(f"[autoglm] start: {msg}")
        if not ok:
            raise RuntimeError(f"启动 AutoGLM 失败: {msg}")


def _collect_autoglm_output(
    offset: int, *, timeout_s: int = 20, stop_on_prompt: bool = True
) -> tuple[int, list[str]]:
    """
    从 AutoGLM 日志中尽量收集一次输入对应的输出片段。

    stop_on_prompt=True 时，看到 "Enter your task:" 视为一次交互结束（AutoGLM 回到等待输入状态）。
    """
    deadline = time.time() + max(1, int(timeout_s or 20))
    collected: list[str] = []
    saw_any = False

    while time.time() < deadline:
        new_offset, chunk = autoglm_process.tail_log(offset)
        offset = new_offset
        if chunk:
            lines = [ln for ln in chunk.splitlines() if ln.strip()]
            if lines:
                collected.extend(lines)
                saw_any = True
                if stop_on_prompt and any("Enter your task:" in ln for ln in lines):
                    break
        # 没有新输出：短暂等待
        if not saw_any:
            time.sleep(0.25)
        else:
            time.sleep(0.15)
    return offset, collected


def _is_fatal_autoglm_output(lines: list[str]) -> bool:
    for ln in lines:
        s = (ln or "").strip()
        if not s:
            continue
        if s.startswith("Error:"):
            return True
        if "Traceback (most recent call last)" in s:
            return True
    return False


def run_prompt_via_process(prompt: str, *, timeout_s: int = 120) -> tuple[bool, str]:
    """
    复用已运行的 AutoGLM 交互进程发送 prompt，作为“交互模式”的补充能力。
    返回 (ok, output_text)。
    """
    ensure_autoglm_running()

    # 从当前日志末尾开始收集，避免夹杂历史输出
    try:
        offset = autoglm_process.log_file().stat().st_size
    except Exception:
        offset = 0

    ok, msg = autoglm_process.send_input(prompt)
    if not ok:
        # 进程句柄不可用时尝试自愈一次
        if "进程句柄不可用" in (msg or ""):
            try:
                autoglm_process.stop()
            except Exception:
                pass
            ensure_autoglm_running()
            try:
                offset = autoglm_process.log_file().stat().st_size
            except Exception:
                offset = 0
            ok, msg = autoglm_process.send_input(prompt)
        if not ok:
            return False, msg or "发送失败"

    offset, lines = _collect_autoglm_output(offset, timeout_s=timeout_s, stop_on_prompt=True)
    if not lines:
        return True, "已发送，暂无新日志（可能仍在执行），请在日志中查看"
    out = "\n".join(lines).strip()
    return (not _is_fatal_autoglm_output(lines)), out


def _format(value: Any, params: dict[str, Any]) -> Any:
    if isinstance(value, str):
        try:
            return value.format(**params)
        except Exception:
            return value
    return value


def _step_device_id(step: dict[str, Any], params: dict[str, Any], default_device_id: str | None) -> str | None:
    raw = step.get("device_id", None)
    if raw is None:
        return default_device_id
    try:
        value = _format(raw, params) if isinstance(raw, str) else raw
        device_id = str(value or "").strip()
    except Exception:
        device_id = ""
    return device_id or default_device_id


def run_step(step: dict[str, Any], params: dict[str, Any], *, default_device_id: str | None = None) -> tuple[bool, str]:
    stype = step.get("type", "")
    device_id = _step_device_id(step, params, default_device_id)
    if stype == "note":
        msg = _format(step.get("text", ""), params)
        _log_line(f"[note] {msg}")
        return True, msg
    if stype == "sleep":
        ms = int(_format(step.get("ms", 500), params) or 500)
        adb.pause_ms(ms)
        return True, f"sleep {ms}ms"
    if stype == "adb_shell":
        cmd = _format(step.get("command", ""), params)
        ok, out = adb.shell(cmd, device_id=device_id)
        _log_line(f"[adb shell] {cmd} -> {out}")
        return ok, out
    if stype == "adb_input":
        text = _format(step.get("text", ""), params)
        ok, out = adb.input_text(text, device_id=device_id)
        _log_line(f"[adb input] {text} -> {out}")
        return ok, out
    if stype == "adb_tap":
        x = int(_format(step.get("x", 0), params) or 0)
        y = int(_format(step.get("y", 0), params) or 0)
        ok, out = adb.tap(x, y, device_id=device_id)
        _log_line(f"[adb tap] ({x},{y}) -> {out}")
        return ok, out
    if stype == "adb_swipe":
        x1 = int(_format(step.get("x1", 0), params) or 0)
        y1 = int(_format(step.get("y1", 0), params) or 0)
        x2 = int(_format(step.get("x2", 0), params) or 0)
        y2 = int(_format(step.get("y2", 0), params) or 0)
        duration_ms = int(_format(step.get("duration_ms", 300), params) or 300)
        ok, out = adb.swipe(x1, y1, x2, y2, duration_ms, device_id=device_id)
        _log_line(f"[adb swipe] ({x1},{y1})->({x2},{y2}) {duration_ms}ms -> {out}")
        return ok, out
    if stype == "adb_keyevent":
        key = _format(step.get("key", ""), params)
        ok, out = adb.keyevent(key, device_id=device_id)
        _log_line(f"[adb keyevent] {key} -> {out}")
        return ok, out
    if stype == "app_launch":
        package = _format(step.get("package", ""), params)
        activity = _format(step.get("activity", ""), params) or None
        action = _format(step.get("action", "auto"), params)
        ok, out = adb.start_app(package, activity, action=action, device_id=device_id)
        _log_line(f"[app launch] {package} {activity or ''} -> {out}")
        return ok, out
    if stype == "autoglm_prompt":
        text = _format(step.get("text", ""), params)
        timeout_s = int(_format(step.get("timeout_s", 120), params) or 120)
        ok, output = run_prompt_via_process(text, timeout_s=timeout_s)
        _log_line(f"[autoglm prompt] {text}")
        for ln in (output or "").splitlines():
            _log_line(f"[autoglm prompt output] {ln}")
        return ok, output
    return False, f"未知步骤类型: {stype}"


def run_task_by_id(task_id: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    params = params or {}
    tasks = list_tasks()
    task = find_by_id(tasks, task_id)
    if not task:
        raise ValueError("未找到任务")
    results: list[dict[str, Any]] = []
    cfg = read_config()
    default_device_id = cfg.device_id or None
    if not default_device_id:
        try:
            ds = adb.devices(raise_on_error=False)
            for d in ds:
                if d.status == "device":
                    default_device_id = d.serial
                    break
        except Exception:
            default_device_id = None
    prompt = task.get("prompt", "")
    steps = task.get("steps", [])
    if prompt:
        timeout_s = 600
        try:
            timeout_s = int(_format(params.get("timeout_s", 600), params) or 600)
        except Exception:
            timeout_s = 600
        ok, out = run_prompt_via_process(str(prompt or ""), timeout_s=timeout_s)
        results.append({"type": "autoglm_prompt", "ok": ok, "output": out})
        return results

    needs_autoglm = any(str(st.get("type", "") or "") == "autoglm_prompt" for st in (steps or []))
    if needs_autoglm:
        ensure_autoglm_running()
    for st in steps:
        if st.get("type") == "app":
            app_id = st.get("app_id", "")
            msg = f"应用库功能已移除，无法执行应用 {app_id or '未指定'}，请直接在任务步骤中编排 adb_* 或 autoglm_prompt"
            results.append({"type": "app", "app_id": app_id, "ok": False, "output": msg})
            break
        ok, out = run_step(st, params, default_device_id=default_device_id)
        results.append({"type": st.get("type"), "ok": ok, "output": out})
        if not ok:
            break
    return results


# 调度器接入：避免循环引用，定义后再配置 runner
schedule.configure_runner(run_task_by_id)
schedule.ensure_scheduler_started()


MAX_SESSIONS = 50  # 会话上限，超出则丢弃最早的
_sessions: dict[str, list[str]] = {}
_session_offsets: dict[str, int] = {}
_sessions_lock = threading.Lock()


def new_session() -> str:
    sid = uuid.uuid4().hex
    with _sessions_lock:
        # 控制会话总数
        if len(_sessions) >= MAX_SESSIONS:
            # FIFO 删除最早创建的会话
            oldest_sid = next(iter(_sessions))
            del _sessions[oldest_sid]
            _session_offsets.pop(oldest_sid, None)
        _sessions[sid] = []
        try:
            _session_offsets[sid] = autoglm_process.log_file().stat().st_size
        except Exception:
            _session_offsets[sid] = 0
    _log_line(f"[session {sid}] started")
    return sid


def send_interactive(sid: str, text: str) -> list[str]:
    with _sessions_lock:
        if sid not in _sessions:
            raise ValueError("会话不存在")
        offset = _session_offsets.get(sid, 0)
    st = autoglm_process.status()
    if not st.running:
        raise ValueError("AutoGLM 未在运行，请先启动")
    output_lines: list[str] = []
    ok, msg = autoglm_process.send_input(text)
    if not ok:
        output_lines = [f"执行失败: {msg}"]
    else:
        collected: list[str] = []
        try:
            # 轮询几次，尽量获取完整日志片段
            for _ in range(12):
                new_offset, chunk = autoglm_process.tail_log(offset)
                offset = new_offset
                if chunk:
                    collected.extend(chunk.splitlines())
                    # 若已有输出，跳出；否则继续等
                    if chunk.strip():
                        break
                time.sleep(0.25)
            output_lines = [ln for ln in collected if ln.strip()]
            if not output_lines:
                output_lines = ["已发送，暂无新日志（可能仍在执行）"]
        except Exception as e:
            output_lines = [f"发送成功，但读取日志失败: {e}"]
    line = f"[session {sid}] {text}"
    with _sessions_lock:
        if sid not in _sessions:
            raise ValueError("会话不存在")
        _session_offsets[sid] = offset
        _sessions[sid].append(line)
        for ln in output_lines:
            _sessions[sid].append(f"[session {sid}] {ln}")
    _log_line(line)
    for ln in output_lines:
        _log_line(f"[session {sid} output] {ln}")
    with _sessions_lock:
        if sid not in _sessions:
            return []
        return _sessions[sid][-20:]


def get_interactive_log(sid: str) -> list[str]:
    with _sessions_lock:
        if sid not in _sessions:
            return []
        return _sessions[sid][-50:]


def run_prompt_once(prompt: str, timeout_s: int = 600) -> str:
    cfg = read_config()
    if not cfg.api_key or str(cfg.api_key).strip() in {"sk-your-apikey", "EMPTY"}:
        raise RuntimeError(f"API Key 未配置：请在 {config_sh_path()} 填写有效密钥或通过 Web 界面保存配置")

    resolved_device_id = str(cfg.device_id or "").strip()
    if not resolved_device_id:
        try:
            ds = adb.devices(raise_on_error=False)
            online = [d.serial for d in ds if d.status == "device"]
            if len(online) == 1:
                resolved_device_id = online[0]
            elif len(online) > 1:
                raise RuntimeError("检测到多个在线设备：请先在 Web 配置中选择设备（设备列表点“选用”）")
            else:
                raise RuntimeError("未检测到在线设备：请先通过 ADB 配对/连接，并确认设备状态为 device")
        except RuntimeError:
            raise
        except Exception:
            resolved_device_id = ""

    workdir = _autoglm_dir()
    if not workdir.exists():
        raise RuntimeError(f"未找到 Open-AutoGLM 目录: {workdir}")
    args = [
        "python",
        "main.py",
        "--base-url",
        cfg.base_url,
        "--model",
        cfg.model,
        "--apikey",
        cfg.api_key,
    ]
    if resolved_device_id:
        args += ["--device-id", resolved_device_id]
    if str(cfg.max_steps).strip():
        args += ["--max-steps", str(cfg.max_steps)]
    if cfg.lang:
        args += ["--lang", cfg.lang]

    input_data = f"{prompt}\nquit\n"
    try:
        proc = subprocess.run(
            args,
            cwd=str(workdir),
            input=input_data,
            text=True,
            capture_output=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("执行超时")
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    if proc.returncode != 0:
        brief_out = output.strip()
        if len(brief_out) > 800:
            brief_out = brief_out[:800] + "...(truncated)"
        raise RuntimeError(f"AutoGLM 子进程退出码 {proc.returncode}，输出: {brief_out or '无'}")
    _log_line(f"[prompt once] {prompt}")
    return output.strip()
