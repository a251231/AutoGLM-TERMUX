from __future__ import annotations

import socket


def guess_lan_ip() -> str | None:
    """
    尽量获取局域网可访问的 IPv4 地址。
    说明：通过 UDP “伪连接”获取路由出口 IP，不会实际发送数据包。
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
        finally:
            sock.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        return None
    return None


def candidate_urls(host: str, port: int) -> list[str]:
    host = (host or "").strip()
    try:
        port = int(port)
    except Exception:
        port = 8000

    if host in {"", "0.0.0.0", "::"}:
        urls: list[str] = []
        ip = guess_lan_ip()
        if ip:
            urls.append(f"http://{ip}:{port}/")
        urls.append(f"http://127.0.0.1:{port}/")
        return urls
    return [f"http://{host}:{port}/"]

