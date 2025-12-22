from __future__ import annotations

import os
import signal
import threading
import time
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import AutoglmConfig

_proc: subprocess.Popen | None = None
_lock = threading.RLock()


def _autoglm_dir() -> Path:
    return Path(os.environ.get("AUTOGLM_DIR", str(Path.home() / "Open-AutoGLM"))).expanduser()


def _state_dir() -> Path:
    base = Path(os.environ.get("AUTOGLM_HOME", str(Path.home() / ".autoglm"))).expanduser()
    return base / "web"


def pid_file() -> Path:
    return _state_dir() / "autoglm.pid"


def log_file() -> Path:
    return _state_dir() / "autoglm.log"


@dataclass(frozen=True)
class ProcessStatus:
    running: bool
    pid: int | None
    log_path: str
    autoglm_dir: str


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def status() -> ProcessStatus:
    global _proc
    with _lock:
        _state_dir().mkdir(parents=True, exist_ok=True)
        pid = None
        if pid_file().exists():
            try:
                pid = int(pid_file().read_text(encoding="utf-8").strip())
            except Exception:
                pid = None
        running = bool(pid) and _is_running(pid)
        if pid and not running:
            try:
                pid_file().unlink()
            except Exception:
                pass
            pid = None
        if _proc and _proc.poll() is not None:
            _proc = None
        return ProcessStatus(
            running=running,
            pid=pid,
            log_path=str(log_file()),
            autoglm_dir=str(_autoglm_dir()),
        )


def start(cfg: AutoglmConfig) -> tuple[bool, str]:
    global _proc
    with _lock:
        st = status()
        if st.running:
            return False, f"AutoGLM 已在运行 (pid={st.pid})"

        workdir = _autoglm_dir()
        if not workdir.exists():
            return False, f"未找到 Open-AutoGLM 目录: {workdir}"

        # 设备选择：避免多设备时 Open-AutoGLM 内部 adb 默认设备不明确而失败
        resolved_device_id = str(cfg.device_id or "").strip()
        if not resolved_device_id:
            try:
                from .adb import devices as adb_devices

                ds = adb_devices(raise_on_error=False)
                online = [d.serial for d in ds if d.status == "device"]
                if len(online) == 1:
                    resolved_device_id = online[0]
                elif len(online) > 1:
                    return False, "检测到多个在线设备，请先在 Web 配置中选择设备（设备列表点“选用”）"
                else:
                    return False, "未检测到在线设备：请先通过 ADB 配对/连接，并确认设备状态为 device"
            except Exception:
                # 不阻塞启动，但可能会在上游报更模糊的错误
                resolved_device_id = ""

        _state_dir().mkdir(parents=True, exist_ok=True)
        lf = log_file()
        log_fp = lf.open("a", encoding="utf-8")

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

        try:
            proc = subprocess.Popen(
                args,
                cwd=str(workdir),
                stdout=log_fp,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
            )
        except Exception as e:
            log_fp.close()
            return False, f"启动失败: {e}"

        _proc = proc
        pid_file().write_text(str(proc.pid) + "\n", encoding="utf-8")
        try:
            pid_file().chmod(0o600)
        except Exception:
            pass
        log_fp.write(f"\n[autoglm-web] started pid={proc.pid} at {time.strftime('%F %T')}\n")
        log_fp.flush()
        log_fp.close()
        return True, f"已启动 (pid={proc.pid})"


def stop() -> tuple[bool, str]:
    global _proc
    with _lock:
        st = status()
        if not st.pid:
            return False, "当前没有由 Web 管理端启动的进程"
        pid = st.pid
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception as e:
            return False, f"停止失败: {e}"

        for _ in range(30):
            if not _is_running(pid):
                break
            time.sleep(0.2)
        if _is_running(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass

        try:
            pid_file().unlink()
        except Exception:
            pass
        if _proc and _proc.stdin:
            try:
                _proc.stdin.close()
            except Exception:
                pass
        _proc = None
        return True, "已停止"


def tail_log(offset: int, max_bytes: int = 32_000) -> tuple[int, str]:
    lf = log_file()
    if not lf.exists():
        return 0, ""
    size = lf.stat().st_size
    if offset < 0 or offset > size:
        offset = max(0, size - max_bytes)
    with lf.open("rb") as f:
        f.seek(offset)
        data = f.read(max_bytes)
        new_offset = offset + len(data)
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:
        text = ""
    return new_offset, text


def send_input(text: str) -> tuple[bool, str]:
    """向已运行的 AutoGLM 进程发送一行输入（需先通过 start 启动）"""
    with _lock:
        st = status()
        if not st.running:
            return False, "AutoGLM 未在运行，请先启动"
        if _proc is None or _proc.poll() is not None or _proc.stdin is None:
            return False, "进程句柄不可用，请尝试重新启动 AutoGLM"
        try:
            _proc.stdin.write(text + "\n")
            _proc.stdin.flush()
            return True, "已发送"
        except Exception as e:
            return False, f"发送失败: {e}"

