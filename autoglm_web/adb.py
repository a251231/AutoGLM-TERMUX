from __future__ import annotations

import os
import re
import shlex
import subprocess
from base64 import b64encode
from collections import OrderedDict
from dataclasses import dataclass
from time import sleep


@dataclass(frozen=True)
class AdbDevice:
    serial: str
    status: str
    product: str | None = None
    model: str | None = None
    device: str | None = None
    transport_id: str | None = None


def _in_termux() -> bool:
    return bool(os.environ.get("TERMUX_VERSION"))


def _adb_not_found_message() -> str:
    if _in_termux():
        return "未找到 adb 命令：请在 Termux 执行 `pkg install android-tools` 后重试"
    return "未找到 adb 命令：请先安装 ADB 并确保 adb 在 PATH 中"


def _adb_base_args(device_id: str | None = None) -> list[str]:
    base = ["adb"]
    if device_id:
        base += ["-s", device_id]
    return base


def _run_adb(args: list[str], timeout_s: int = 20, *, device_id: str | None = None) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            _adb_base_args(device_id) + args,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out.strip()
    except FileNotFoundError:
        return 127, _adb_not_found_message()
    except subprocess.TimeoutExpired:
        return 124, f"adb 执行超时（>{timeout_s}s）：{' '.join(_adb_base_args(device_id) + args)}"
    except Exception as e:
        return 1, f"adb 执行失败: {e}"


def devices(*, raise_on_error: bool = False) -> list[AdbDevice]:
    code, out = _run_adb(["devices", "-l"], timeout_s=20)
    if code != 0:
        if raise_on_error:
            raise RuntimeError(out or "adb devices 执行失败")
        return []
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    if not lines:
        return []
    result: list[AdbDevice] = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, status = parts[0], parts[1]
        kv = {}
        for p in parts[2:]:
            if ":" in p:
                k, v = p.split(":", 1)
                kv[k] = v
        result.append(
            AdbDevice(
                serial=serial,
                status=status,
                product=kv.get("product"),
                model=kv.get("model"),
                device=kv.get("device"),
                transport_id=kv.get("transport_id"),
            )
        )
    return result


def pair(host_port: str, code: str) -> tuple[bool, str]:
    rc, out = _run_adb(["pair", host_port, code], timeout_s=60)
    return rc == 0, out


def connect(host_port: str) -> tuple[bool, str]:
    rc, out = _run_adb(["connect", host_port], timeout_s=30)
    return rc == 0, out


def disconnect(host_port: str | None = None) -> tuple[bool, str]:
    args = ["disconnect"] if not host_port else ["disconnect", host_port]
    rc, out = _run_adb(args, timeout_s=30)
    return rc == 0, out


def restart_server() -> tuple[bool, str]:
    rc1, out1 = _run_adb(["kill-server"], timeout_s=10)
    rc2, out2 = _run_adb(["start-server"], timeout_s=10)
    ok = rc1 == 0 and rc2 == 0
    out = "\n".join([s for s in [out1, out2] if s]).strip()
    return ok, out


def version() -> tuple[bool, str]:
    rc, out = _run_adb(["version"], timeout_s=8)
    return rc == 0, out


def list_packages(
    third_party: bool = True, *, device_id: str | None = None, raise_on_error: bool = False
) -> list[str]:
    args = ["shell", "pm", "list", "packages"]
    if third_party:
        args.append("-3")
    code, out = _run_adb(args, timeout_s=30, device_id=device_id)
    if code != 0:
        if raise_on_error:
            raise RuntimeError(out or "adb shell pm list packages 执行失败")
        return []
    pkgs = []
    for ln in out.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if ln.startswith("package:"):
            ln = ln.replace("package:", "", 1)
        pkgs.append(ln)
    return pkgs


def _package_label(pkg: str, *, device_id: str | None = None) -> str | None:
    # 尝试从 dumpsys 中获取 application-label
    cmd = ["shell", "dumpsys", "package", pkg]
    code, out = _run_adb(cmd, timeout_s=8, device_id=device_id)
    if code != 0 or not out:
        return None
    for ln in out.splitlines():
        ln = ln.strip()
        if "application-label:" in ln:
            return ln.split("application-label:", 1)[1].strip()
        if "application-label-zh:" in ln:
            return ln.split("application-label-zh:", 1)[1].strip()
    return None


def list_packages_with_labels(
    third_party: bool = True,
    limit: int | None = None,
    *,
    device_id: str | None = None,
    raise_on_error: bool = False,
) -> list[dict[str, str]]:
    pkgs = list_packages(third_party=third_party, device_id=device_id, raise_on_error=raise_on_error)
    if limit is not None:
        pkgs = pkgs[:limit]
    result: list[dict[str, str]] = []
    for pkg in pkgs:
        label = _package_label(pkg, device_id=device_id) or ""
        result.append({"package": pkg, "label": label})
    return result


def shell(cmd: str, timeout_s: int = 20, *, device_id: str | None = None) -> tuple[bool, str]:
    rc, out = _run_adb(["shell", cmd], timeout_s=timeout_s, device_id=device_id)
    return rc == 0, out


def shell_argv(argv: list[str], timeout_s: int = 20, *, device_id: str | None = None) -> tuple[bool, str]:
    """
    以参数数组方式执行 `adb shell ...`，避免把带空格的整条命令作为单一参数传入时的兼容性问题。
    """
    rc, out = _run_adb(["shell", *argv], timeout_s=timeout_s, device_id=device_id)
    return rc == 0, out


def input_text(text: str, *, device_id: str | None = None) -> tuple[bool, str]:
    # 使用 shell 转义规避命令注入，同时去掉换行符避免意外分行
    sanitized = text.replace("\r", " ").replace("\n", " ")
    safe = shlex.quote(sanitized)
    return shell(f"input text {safe}", device_id=device_id)


def tap(x: int, y: int, *, device_id: str | None = None) -> tuple[bool, str]:
    return shell_argv(["input", "tap", str(int(x)), str(int(y))], device_id=device_id)


def swipe(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    duration_ms: int = 300,
    *,
    device_id: str | None = None,
) -> tuple[bool, str]:
    return shell_argv(
        ["input", "swipe", str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(int(duration_ms))],
        device_id=device_id,
    )


def keyevent(key: str, *, device_id: str | None = None) -> tuple[bool, str]:
    key = str(key or "").strip()
    if not key:
        return False, "invalid keyevent"
    if not (re.fullmatch(r"\d+", key) or re.fullmatch(r"KEYCODE_[A-Z0-9_]+", key)):
        return False, "invalid keyevent"
    return shell_argv(["input", "keyevent", key], device_id=device_id)


def start_app(
    package: str, activity: str | None = None, action: str = "auto", *, device_id: str | None = None
) -> tuple[bool, str]:
    # 严格限制包名/Activity 以防命令注入
    def _validate(name: str, field: str) -> None:
        if not name or not all(ch.isalnum() or ch in "._$" for ch in name):
            raise ValueError(f"{field} 非法：仅允许字母/数字/._$")

    _validate(package, "package")
    if activity:
        # Activity 形如 com.xx/.MainActivity 或 com.xx/com.xx.MainActivity，统一校验组件名
        parts = activity.split("/", 1)
        for p in parts:
            _validate(p, "activity")

    if action == "monkey" or (action == "auto" and not activity):
        return shell_argv(
            ["monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"],
            device_id=device_id,
        )
    if activity:
        return shell_argv(["am", "start", "-n", f"{package}/{activity}"], device_id=device_id)
    return shell_argv(
        ["monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"],
        device_id=device_id,
    )


def pause_ms(ms: int) -> None:
    sleep(max(ms, 0) / 1000)


def tcpip(port: int = 5555, *, device_id: str | None = None) -> tuple[bool, str]:
    port = int(port or 5555)
    rc, out = _run_adb(["tcpip", str(port)], timeout_s=10, device_id=device_id)
    return rc == 0, out


def get_wifi_ip(*, device_id: str | None = None) -> str | None:
    """
    尽量获取设备 WiFi IP，优先 route src，并跳过常见的移动网络接口。
    参考 AutoGLM-GUI 的 adb_plus/ip.py，但不引入额外依赖。
    """

    def _extract_ipv4(text: str) -> str | None:
        m = re.search(r"\\b(?:[0-9]{1,3}\\.){3}[0-9]{1,3}\\b", text or "")
        if not m:
            return None
        ip = m.group(0)
        if ip == "0.0.0.0":
            return None
        return ip

    try:
        ok, out = shell("ip -4 route get 8.8.8.8", timeout_s=6, device_id=device_id)
        if ok and out:
            for line in out.splitlines():
                if " src " not in line:
                    continue
                parts = line.split()
                iface = None
                ip = None
                if "dev" in parts:
                    try:
                        iface = parts[parts.index("dev") + 1]
                    except Exception:
                        pass
                if "src" in parts:
                    try:
                        ip = parts[parts.index("src") + 1]
                    except Exception:
                        pass
                if not ip or ip == "0.0.0.0":
                    continue
                if iface and (iface.startswith("ccmni") or iface.startswith("rmnet")):
                    continue
                return ip
    except Exception:
        pass

    try:
        ok, out = shell("ip -4 addr show wlan0", timeout_s=6, device_id=device_id)
        if ok and out:
            return _extract_ipv4(out)
    except Exception:
        pass

    return None


def connect_wifi(*, device_id: str | None = None, port: int = 5555) -> tuple[bool, str, str | None]:
    """
    USB -> WiFi：读取设备 WiFi IP，启用 tcpip，然后 adb connect。
    返回 (ok, output, address)。
    """
    ip = get_wifi_ip(device_id=device_id)
    if not ip:
        return False, "无法获取设备 WiFi IP", None
    ok, out = tcpip(port, device_id=device_id)
    if not ok:
        return False, out or "adb tcpip 失败", None
    addr = f"{ip}:{int(port or 5555)}"
    ok2, out2 = connect(addr)
    msg = "\n".join([s for s in [out, out2] if s]).strip()
    return ok2, msg, addr


def _run_adb_bytes(args: list[str], timeout_s: int = 10, *, device_id: str | None = None) -> tuple[int, bytes, str]:
    try:
        proc = subprocess.run(
            _adb_base_args(device_id) + args,
            capture_output=True,
            timeout=timeout_s,
        )
        stdout = proc.stdout if isinstance(proc.stdout, (bytes, bytearray)) else b""
        stderr = (
            proc.stderr.decode("utf-8", errors="replace")
            if isinstance(proc.stderr, (bytes, bytearray))
            else str(proc.stderr or "")
        )
        return proc.returncode, bytes(stdout), (stderr or "").strip()
    except FileNotFoundError:
        return 127, b"", _adb_not_found_message()
    except subprocess.TimeoutExpired:
        return 124, b"", f"adb 执行超时（>{timeout_s}s）：{' '.join(_adb_base_args(device_id) + args)}"
    except Exception as e:
        return 1, b"", f"adb 执行失败: {e}"


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def screenshot_png(*, device_id: str | None = None, timeout_s: int = 10, retries: int = 1) -> tuple[bool, bytes, str]:
    """
    使用 `adb exec-out screencap -p` 截图，返回 (ok, png_bytes, message)。
    参考 AutoGLM-GUI 的 adb_plus/screenshot.py，但不引入 PIL。
    """
    attempts = max(1, int(retries) + 1)
    last_err = ""
    for _ in range(attempts):
        rc, data, err = _run_adb_bytes(
            ["exec-out", "screencap", "-p"], timeout_s=timeout_s, device_id=device_id
        )
        if rc != 0 or not data:
            last_err = err or f"exec-out failed rc={rc}"
            continue
        if len(data) <= len(PNG_SIGNATURE) + 8 or not data.startswith(PNG_SIGNATURE):
            last_err = "截图格式异常（PNG signature 不匹配）"
            continue
        return True, data, "ok"
    return False, b"", last_err or "截图失败"


def png_dimensions(png: bytes) -> tuple[int | None, int | None]:
    """从 PNG IHDR 解析宽高，无需 Pillow。"""
    try:
        if not png.startswith(PNG_SIGNATURE):
            return None, None
        # signature(8) + length(4) + type(4) => IHDR data starts at 16
        if len(png) < 24:
            return None, None
        if png[12:16] != b"IHDR":
            return None, None
        w = int.from_bytes(png[16:20], "big", signed=False)
        h = int.from_bytes(png[20:24], "big", signed=False)
        if w <= 0 or h <= 0:
            return None, None
        return w, h
    except Exception:
        return None, None


def screenshot_base64(
    *, device_id: str | None = None, timeout_s: int = 10, retries: int = 1
) -> tuple[bool, str, dict[str, int | None], str]:
    ok, png, msg = screenshot_png(device_id=device_id, timeout_s=timeout_s, retries=retries)
    if not ok:
        return False, "", {"width": None, "height": None}, msg
    w, h = png_dimensions(png)
    b64 = b64encode(png).decode("ascii")
    return True, b64, {"width": w, "height": h}, "ok"


def _package_apk_path(package: str, *, device_id: str | None = None) -> str | None:
    ok, out = shell_argv(["pm", "path", package], timeout_s=8, device_id=device_id)
    if not ok or not out:
        return None
    for ln in out.splitlines():
        ln = (ln or "").strip()
        if not ln:
            continue
        if ln.startswith("package:"):
            return ln.split("package:", 1)[1].strip() or None
        # 兼容部分输出格式
        if ln.startswith("/") and ln.endswith(".apk"):
            return ln.strip()
    return None


def _icon_density_score(path: str) -> int:
    p = path.lower()
    if "xxxhdpi" in p:
        return 6
    if "xxhdpi" in p:
        return 5
    if "xhdpi" in p:
        return 4
    if "hdpi" in p:
        return 3
    if "mdpi" in p:
        return 2
    if "ldpi" in p:
        return 1
    return 0


def _best_launcher_icon_entry(entries: list[str]) -> str | None:
    """
    从 APK 条目列表中挑选一个较可能的 launcher PNG。
    依赖 toybox/unzip 的列表输出，不需要把整个 APK 拉回本机。
    """
    candidates: list[str] = []
    for e in entries:
        e = (e or "").strip()
        if not e:
            continue
        el = e.lower()
        if not (el.endswith(".png")):
            continue
        if not ("/res/" in el or el.startswith("res/")):
            continue
        base = el.rsplit("/", 1)[-1]
        if "launcher" not in base and "ic_" not in base:
            continue
        # 过滤常见非最终 icon 资源
        if "ic_launcher_foreground" in el or "ic_launcher_background" in el:
            continue
        if "ic_launcher" in el or "launcher" in el:
            candidates.append(e)

    if not candidates:
        return None

    def score(e: str) -> tuple[int, int, int]:
        el = e.lower()
        is_mipmap = 2 if "/mipmap" in el else (1 if "/drawable" in el else 0)
        density = _icon_density_score(el)
        # 越短越像主入口资源名
        shortness = -len(el)
        return (is_mipmap, density, shortness)

    candidates.sort(key=score, reverse=True)
    return candidates[0]


_icon_cache: "OrderedDict[str, tuple[str, dict[str, int | None]]]" = OrderedDict()
_ICON_CACHE_MAX = 60


def package_icon_base64(
    package: str, *, device_id: str | None = None
) -> tuple[bool, str, dict[str, int | None], str]:
    """
    获取应用图标（尽量返回 PNG base64）。

    实现策略：
    1) `pm path` 拿到 base.apk 路径
    2) 用 `toybox unzip -Z1` 列出条目
    3) 选择一个疑似 launcher 的 PNG
    4) 用 `adb exec-out toybox unzip -p` 直接导出该 PNG（二进制），避免拉整包

    注意：并非所有 ROM 都带 toybox unzip；此时返回失败并提示原因。
    """
    package = str(package or "").strip()
    if not package:
        return False, "", {"width": None, "height": None}, "package 不能为空"

    cache_key = f"{device_id or ''}::{package}"
    cached = _icon_cache.get(cache_key)
    if cached:
        # LRU
        _icon_cache.move_to_end(cache_key)
        b64, meta = cached
        return True, b64, meta, "ok"

    apk = _package_apk_path(package, device_id=device_id)
    if not apk:
        return False, "", {"width": None, "height": None}, "无法获取 APK 路径（pm path 失败）"

    unzip_cmds: list[list[str]] = [
        ["toybox", "unzip"],
        ["unzip"],
        ["busybox", "unzip"],
    ]

    listing = ""
    unzip_bin: list[str] | None = None
    for cmd in unzip_cmds:
        ok, out = shell_argv([*cmd, "-Z1", apk], timeout_s=12, device_id=device_id)
        if ok and out and "not found" not in out.lower():
            listing = out
            unzip_bin = cmd
            break
    if not listing or unzip_bin is None:
        return False, "", {"width": None, "height": None}, "设备缺少 unzip（toybox/unzip/busybox）或无法读取 APK"

    entries = [ln.strip() for ln in listing.splitlines() if ln.strip()]
    entry = _best_launcher_icon_entry(entries)
    if not entry:
        return False, "", {"width": None, "height": None}, "未在 APK 中找到可用的 PNG launcher 图标"

    rc, data, err = _run_adb_bytes(
        ["exec-out", *unzip_bin, "-p", apk, entry], timeout_s=12, device_id=device_id
    )
    if rc != 0 or not data:
        return False, "", {"width": None, "height": None}, err or "导出图标失败"
    if not data.startswith(PNG_SIGNATURE):
        return False, "", {"width": None, "height": None}, "图标不是 PNG（可能为 webp/xml，自行降级忽略）"

    w, h = png_dimensions(data)
    b64 = b64encode(data).decode("ascii")
    meta = {"width": w, "height": h}
    _icon_cache[cache_key] = (b64, meta)
    _icon_cache.move_to_end(cache_key)
    while len(_icon_cache) > _ICON_CACHE_MAX:
        _icon_cache.popitem(last=False)
    return True, b64, meta, "ok"

