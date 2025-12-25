from __future__ import annotations

import os
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from . import __version__
from .adb import (
    connect,
    connect_wifi as adb_connect_wifi,
    devices,
    disconnect,
    list_packages,
    pair,
    restart_server,
    screenshot_base64,
    swipe as adb_swipe,
    tap as adb_tap,
    version as adb_version,
)
from .autoglm_process import start as start_autoglm
from .autoglm_process import status as autoglm_status
from .autoglm_process import stop as stop_autoglm
from .autoglm_process import tail_log
from .apps_config import add_entries, load_app_packages
from .auth import AuthResult, require_token
from .config import AutoglmConfig, config_exists, config_sh_path, read_config, update_device_id, write_config
from .net import candidate_urls
from .storage import delete_task, list_tasks, upsert_task
from . import schedule
from .tasks_runner import get_interactive_log, new_session, run_prompt_once, run_task_by_id, send_interactive

app = FastAPI(title="AutoGLM Web", version=__version__)


def _api_key_configured(cfg: AutoglmConfig) -> bool:
    key = str(cfg.api_key or "").strip()
    if not key:
        return False
    if key in {"sk-your-apikey", "EMPTY"}:
        return False
    return True


def _server_info() -> dict[str, Any]:
    host = os.environ.get("AUTOGLM_WEB_HOST", "0.0.0.0")
    port = int(os.environ.get("AUTOGLM_WEB_PORT", "8000"))
    return {"version": __version__, "host": host, "port": port, "urls": candidate_urls(host, port)}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AutoGLM Web</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #f6f7fb;
      --card: rgba(255, 255, 255, 0.72);
      --border: rgba(15, 23, 42, 0.12);
      --text: #0f172a;
      --muted: rgba(15, 23, 42, 0.6);
      --shadow: 0 18px 45px rgba(2, 6, 23, 0.08);
      --primary: rgba(59, 130, 246, 0.14);
      --primary-border: rgba(59, 130, 246, 0.35);
      --danger: rgba(239, 68, 68, 0.12);
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #0b1220;
        --card: rgba(15, 23, 42, 0.60);
        --border: rgba(148, 163, 184, 0.18);
        --text: rgba(226, 232, 240, 0.95);
        --muted: rgba(148, 163, 184, 0.70);
        --shadow: 0 18px 45px rgba(0, 0, 0, 0.42);
        --primary: rgba(96, 165, 250, 0.14);
        --primary-border: rgba(96, 165, 250, 0.40);
        --danger: rgba(248, 113, 113, 0.14);
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial;
      margin: 0;
      padding: 16px;
      background:
        radial-gradient(1200px 480px at 10% -10%, rgba(59, 130, 246, 0.20), rgba(0, 0, 0, 0)),
        radial-gradient(900px 420px at 95% 0%, rgba(168, 85, 247, 0.18), rgba(0, 0, 0, 0)),
        var(--bg);
      color: var(--text);
    }}
    .wrap {{ max-width: 1240px; margin: 0 auto; }}
    .row {{ display: flex; gap: 12px; flex-wrap: wrap; }}
    .stack {{ display: flex; flex-direction: column; gap: 12px; }}
    .grid2 {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }}
    @media (max-width: 980px) {{ .grid2 {{ grid-template-columns: 1fr; }} }}
    .card {{
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px;
      background: var(--card);
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }}
    .title {{ margin: 0; font-size: 20px; line-height: 1.2; }}
    .muted {{ opacity: 1; color: var(--muted); font-size: 12px; }}
    .topbar {{ display: flex; gap: 12px; flex-wrap: wrap; align-items: stretch; }}
    .brand {{ flex: 1; min-width: 260px; }}
    .tokenCard {{ flex: 1; min-width: 360px; }}
    .layout {{ display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: 12px; margin-top: 12px; }}
    @media (max-width: 980px) {{
      .layout {{ grid-template-columns: 1fr; }}
    }}
    .sidebar {{ position: sticky; top: 12px; align-self: start; padding: 10px; }}
    @media (max-width: 980px) {{
      .sidebar {{ position: static; }}
    }}
    .navTitle {{ margin: 0 0 8px 0; font-size: 12px; }}
    .nav {{ display: flex; flex-direction: column; gap: 6px; }}
    @media (max-width: 980px) {{
      .nav {{ flex-direction: row; overflow-x: auto; padding-bottom: 4px; }}
    }}
    .navbtn {{
      width: 100%;
      text-align: left;
      padding: 10px 10px;
      border-radius: 12px;
      border: 1px solid transparent;
      background: transparent;
      color: inherit;
      cursor: pointer;
      user-select: none;
      white-space: nowrap;
    }}
    .navbtn:hover {{ border-color: var(--border); }}
    .navbtn.active {{ background: var(--primary); border-color: var(--primary-border); }}
    label {{ display: block; font-size: 12px; color: var(--muted); margin-top: 10px; }}
    input, textarea, select {{
      width: 100%;
      padding: 10px;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: transparent;
      color: inherit;
      outline: none;
    }}
    textarea {{ resize: vertical; }}
    button {{
      padding: 10px 12px;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: transparent;
      color: inherit;
      cursor: pointer;
    }}
    button.primary {{ background: var(--primary); border-color: var(--primary-border); }}
    button.danger {{ background: var(--danger); }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 12px;
      min-height: 220px;
      max-height: 520px;
      overflow: auto;
      background: rgba(0, 0, 0, 0.03);
    }}
    @media (prefers-color-scheme: dark) {{
      pre {{ background: rgba(255, 255, 255, 0.03); }}
    }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid var(--border); padding: 8px; text-align: left; font-size: 13px; }}
    th {{ color: var(--muted); font-weight: 600; }}
    .pill {{ display:inline-block; padding: 2px 8px; border-radius: 999px; border: 1px solid var(--border); font-size: 12px; }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }}
    .tab {{ display: none; }}
    .tab.active {{ display: block; }}
    .cardHead {{ display:flex; align-items:center; gap: 10px; flex-wrap: wrap; }}
    .cardHead h3 {{ margin: 0; font-size: 15px; }}
    .cardHead .grow {{ flex: 1; min-width: 180px; }}
    .screenWrap {{ position: relative; display: inline-block; max-width: 720px; width: 100%; }}
    .screenImg {{ display:block; width: 100%; height: auto; border: 1px solid var(--border); border-radius: 14px; cursor: pointer; }}
    @keyframes ripple {{ 0% {{ transform: translate(-50%, -50%) scale(.2); opacity: 1; }} 100% {{ transform: translate(-50%, -50%) scale(1); opacity: 0; }} }}
    .ripple-circle {{ position: absolute; width: 64px; height: 64px; border-radius: 50%; border: 2px solid var(--primary-border); background: var(--primary); animation: ripple 520ms ease-out; pointer-events: none; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <div class="brand">
        <h1 class="title">AutoGLM Web <span class="muted">v{__version__}</span></h1>
        <div class="muted" id="serverInfo"></div>
        <div class="muted" id="checkMsg"></div>
      </div>

      <div class="card tokenCard">
        <div class="cardHead">
          <h3 class="grow">访问控制</h3>
          <button class="primary" onclick="refreshAll()">刷新全部</button>
        </div>
        <label>管理 Token（首次运行后由 autoglm-web 生成）</label>
        <div class="row" style="align-items:end;">
          <div style="flex:1; min-width:220px;">
            <input id="token" placeholder="粘贴 Token（将保存在本浏览器 localStorage）" />
          </div>
          <div style="display:flex; gap:8px; flex-wrap:wrap;">
            <button class="primary" onclick="saveToken()">保存 Token</button>
            <button onclick="clearToken()">清除</button>
          </div>
        </div>
        <div class="muted">安全提示：不要把 Token 发给任何人；如怀疑泄露，请在 Termux 执行 <code>autoglm-web reset-token</code>。</div>
      </div>
    </div>

    <div class="layout">
      <aside class="card sidebar">
        <div class="navTitle muted">功能区域</div>
        <div class="nav">
          <button class="navbtn" data-tab="config" onclick="showTab('config')">配置</button>
          <button class="navbtn" data-tab="adb" onclick="showTab('adb')">设备 / ADB</button>
          <button class="navbtn" data-tab="screen" onclick="showTab('screen')">屏幕预览</button>
          <button class="navbtn" data-tab="tasks" onclick="showTab('tasks')">任务</button>
          <button class="navbtn" data-tab="run" onclick="showTab('run')">运行 / 日志</button>
          <button class="navbtn" data-tab="interactive" onclick="showTab('interactive')">交互</button>
        </div>
      </aside>

      <main class="stack">
        <div class="tab" id="tab-config">
          <div class="card">
            <div class="cardHead">
              <h3 class="grow">配置</h3>
              <div class="muted" id="configMsg"></div>
            </div>
            <label>Base URL</label>
            <input id="base_url" />
            <label>Model</label>
            <input id="model" />
            <label>API Key</label>
            <input id="api_key" placeholder="为空则保持不变" />
            <div class="muted" id="apiKeyHint"></div>
            <div class="muted" id="configPathHint"></div>
            <div class="grid2">
              <div>
                <label>Max Steps</label>
                <input id="max_steps" />
              </div>
              <div>
                <label>语言 (cn/en)</label>
                <input id="lang" />
              </div>
            </div>
            <label>Device ID（留空自动检测）</label>
            <input id="device_id" />
            <div class="row" style="margin-top:12px;">
              <button class="primary" onclick="saveConfig()">保存配置</button>
              <button onclick="loadConfig()">重新加载</button>
            </div>
          </div>
        </div>

        <div class="tab" id="tab-adb">
          <div class="stack">
            <div class="card">
              <div class="cardHead">
                <h3 class="grow">设备 / ADB</h3>
                <div class="muted" id="adbMsg"></div>
              </div>
              <div class="grid2">
                <div>
                  <label>配对 IP:Port（Wireless Debugging 配对弹窗）</label>
                  <div class="row" style="align-items:end;">
                    <div style="flex:1; min-width:220px;">
                      <input id="pair_host" placeholder="例如 192.168.1.13:42379" />
                    </div>
                    <div style="width:160px;">
                      <label style="margin-top:0;">配对码</label>
                      <input id="pair_code" placeholder="6 位数字" />
                    </div>
                    <button class="primary" onclick="adbPair()">配对</button>
                  </div>
                </div>
                <div>
                  <label>连接 IP:Port（Wireless Debugging 主界面）</label>
                  <div class="row" style="align-items:end;">
                    <div style="flex:1; min-width:220px;">
                      <input id="connect_host" placeholder="例如 192.168.1.13:5555" />
                    </div>
                    <button class="primary" onclick="adbConnect()">连接</button>
                    <button onclick="adbConnectWifi()">USB→WiFi</button>
                    <button onclick="adbDisconnectAll()">断开全部</button>
                    <button onclick="adbRestart()">重启 ADB</button>
                  </div>
                </div>
              </div>
            </div>

            <div class="card">
              <div class="cardHead">
                <h3 class="grow">设备列表</h3>
                <button onclick="loadDevices()">刷新</button>
              </div>
              <table>
                <thead>
                  <tr><th>Serial</th><th>Status</th><th>Model</th><th>操作</th></tr>
                </thead>
                <tbody id="devicesBody"></tbody>
              </table>
              <div class="muted">提示：点“选用”会写入配置的 Device ID，供任务/点击/截图等统一使用。</div>
            </div>

            <div class="card">
              <div class="cardHead">
                <h3 class="grow">已安装应用（第三方）</h3>
                <button onclick="fetchPackages()">获取包名</button>
              </div>
              <div class="grid2">
                <div>
                  <label>包名</label>
                  <select id="pkg_select" size="10" style="height:240px;"></select>
                  <div class="muted">提示：列表较长时可直接输入首字母快速定位；选择后点击“添加到 apps.py”。</div>
                </div>
                <div>
                  <label>应用名称（可选，默认使用包名）</label>
                  <input id="pkg_name" placeholder="例如 微信" />
                </div>
              </div>
              <div class="row" style="margin-top:10px;">
                <button class="primary" onclick="addToAppsConfig()">添加到 apps.py</button>
              </div>
              <div class="muted" id="pkgMsg"></div>
            </div>
          </div>
        </div>

        <div class="tab" id="tab-screen">
          <div class="card">
            <div class="cardHead">
              <h3 class="grow">屏幕预览</h3>
              <button onclick="refreshScreenshot()">刷新</button>
              <button onclick="toggleScreenAuto()" id="screenAutoBtn">自动刷新</button>
            </div>
            <div class="muted" id="screenMsg"></div>
            <div class="screenWrap" id="screenWrap">
              <img id="screenImg" class="screenImg" alt="screen" />
            </div>
            <div class="muted">提示：点击图片发送 tap；自动刷新会在页面隐藏时降频，并在失败时退避。</div>
          </div>
        </div>

        <div class="tab" id="tab-tasks">
          <div class="stack">
            <div class="card">
              <div class="cardHead">
                <h3 class="grow">编辑任务</h3>
                <div class="muted" id="taskMsg"></div>
              </div>
              <pre id="taskRunOutput" style="min-height:120px; max-height:260px;"></pre>
              <div class="grid2">
                <div>
                  <label>任务 ID（留空则新增）</label>
                  <input id="task_id" placeholder="留空代表新任务" />
                </div>
                <div>
                  <label>名称</label>
                  <input id="task_name" />
                </div>
              </div>
              <label>描述</label>
              <input id="task_desc" />
              <label>自然语言指令（可选，填了则直接调用模型执行，无需写步骤）</label>
              <textarea id="task_prompt" rows="3" placeholder="例如：打开微信并给张三发一条消息"></textarea>
              <label>步骤（JSON 数组，支持 adb_shell/adb_input/adb_tap/adb_swipe/adb_keyevent/app_launch/sleep/autoglm_prompt/note）</label>
              <textarea id="task_steps" rows="7" placeholder='[{{"type":"adb_input","text":"Hello"}}]'></textarea>
              <div class="row" style="margin-top:10px;">
                <button class="primary" onclick="saveTask()">保存/更新</button>
                <button onclick="resetTaskForm()">清空表单</button>
              </div>
              <div class="muted">提示：如需指定设备，可在每个 step 里加 `device_id` 字段覆盖默认设备。</div>
            </div>

            <div class="card">
              <div class="cardHead">
                <h3 class="grow">调度（秒级 cron，北京时区）</h3>
                <button onclick="loadSchedules()">刷新调度</button>
              </div>
              <div class="grid2">
                <div>
                  <label>任务</label>
                  <select id="sched_task"></select>
                </div>
                <div>
                  <label>cron（6 段，秒 分 时 日 月 周）</label>
                  <input id="sched_cron" placeholder="0 */5 * * * *" />
                </div>
              </div>
              <div class="row" style="margin-top:10px; align-items:center;">
                <label style="margin:0;">调度 ID（留空则新增）</label>
                <input id="sched_id" style="flex:1;" placeholder="可选，用于更新已有调度" />
                <label style="margin:0; margin-left:10px;">启用</label>
                <input type="checkbox" id="sched_enabled" checked />
              </div>
              <div class="row" style="margin-top:10px;">
                <button class="primary" onclick="saveSchedule()">保存调度</button>
                <button onclick="resetScheduleForm()">清空调度表单</button>
              </div>
              <div class="muted" id="schedMsg"></div>
              <table style="margin-top:10px;">
                <thead><tr><th>ID</th><th>任务</th><th>cron</th><th>状态</th><th>最近运行</th><th>操作</th></tr></thead>
                <tbody id="schedBody"></tbody>
              </table>
            </div>

            <div class="card">
              <div class="cardHead">
                <h3 class="grow">任务列表</h3>
                <button onclick="loadTasks()">刷新列表</button>
              </div>
              <table>
                <thead><tr><th>ID</th><th>名称</th><th>操作</th></tr></thead>
                <tbody id="tasksBody"></tbody>
              </table>
            </div>
          </div>
        </div>

        <div class="tab" id="tab-run">
          <div class="grid2">
            <div class="card">
              <div class="cardHead">
                <h3 class="grow">运行</h3>
                <span class="pill" id="runPill">unknown</span>
              </div>
              <div class="row" style="margin-top:6px;">
                <button class="primary" onclick="autoglmStart()">启动 AutoGLM</button>
                <button class="danger" onclick="autoglmStop()">停止 AutoGLM</button>
                <button onclick="autoglmStatus()">刷新状态</button>
              </div>
              <div class="muted" id="runMsg" style="margin-top:10px;"></div>
            </div>

            <div class="card">
              <div class="cardHead">
                <h3 class="grow">日志</h3>
                <button onclick="clearLogView()">清屏</button>
                <button onclick="toggleFollow()" id="followBtn">暂停滚动</button>
              </div>
              <div class="muted">自动轮询（本页不把 Token 放到 URL）</div>
              <pre id="logBox"></pre>
            </div>
          </div>
        </div>

        <div class="tab" id="tab-interactive">
          <div class="card">
            <div class="cardHead">
              <h3 class="grow">交互模式（仅记录日志片段）</h3>
              <button class="primary" onclick="startSession()">新建会话</button>
            </div>
            <div class="muted" id="sessionLabel">尚未创建</div>
            <label>发送内容</label>
            <input id="session_input" placeholder="输入指令/备注，将写入日志并保持 AutoGLM 运行" />
            <div class="row" style="margin-top:8px;">
              <button onclick="sendSession()">发送</button>
              <button onclick="loadSessionLog()">刷新日志</button>
            </div>
            <pre id="sessionLog" style="min-height:160px; max-height:320px;"></pre>
            <div class="muted" id="sessionMsg"></div>
          </div>
        </div>
      </main>
    </div>
  </div>

<script>
const LS_TOKEN_KEY = "autoglm_web_token";
const LS_TAB_KEY = "autoglm_web_tab";
let logOffset = 0;
let follow = true;
let sessionId = "";
let tasksCache = [];
let screenAuto = false;
let screenTimer = 0;
let screenMeta = {{ width: 0, height: 0, device_id: "" }};
let screenFailCount = 0;
let screenTapInflight = false;
let packagesCache = [];

function authHeader() {{
  const t = localStorage.getItem(LS_TOKEN_KEY) || "";
  return t ? {{ "Authorization": "Bearer " + t }} : {{}};
}}

function showTab(name) {{
  const id = "tab-" + name;
  document.querySelectorAll(".tab").forEach(el => {{
    el.classList.toggle("active", el.id === id);
  }});
  document.querySelectorAll(".navbtn").forEach(btn => {{
    btn.classList.toggle("active", btn.dataset.tab === name);
  }});
  try {{ localStorage.setItem(LS_TAB_KEY, name); }} catch (e) {{ }}
}}

function initTabs() {{
  const saved = (localStorage.getItem(LS_TAB_KEY) || "").trim();
  const name = saved || "screen";
  showTab(name);
}}

function hasToken() {{
  return !!((localStorage.getItem(LS_TOKEN_KEY) || "").trim());
}}

function setMsg(id, msg) {{
  const el = document.getElementById(id);
  if (el) el.textContent = msg || "";
}}

function saveToken() {{
  const t = document.getElementById("token").value.trim();
  if (!t) return;
  localStorage.setItem(LS_TOKEN_KEY, t);
  refreshAll();
}}

function clearToken() {{
  localStorage.removeItem(LS_TOKEN_KEY);
  document.getElementById("token").value = "";
  setMsg("configMsg", "Token 已清除");
}}

async function apiJson(path, options={{}}) {{
  const headers = Object.assign({{ "Content-Type": "application/json" }}, authHeader(), options.headers || {{}});
  const resp = await fetch(path, Object.assign({{}}, options, {{ headers }}));
  const text = await resp.text();
  let data = null;
  try {{ data = text ? JSON.parse(text) : null; }} catch (e) {{ data = null; }}
  if (!resp.ok) {{
    const msg = (data && data.detail) ? data.detail : text || (resp.status + "");
    throw new Error(msg);
  }}
  return data;
}}

async function loadConfig() {{
  try {{
    const data = await apiJson("/api/config");
    document.getElementById("base_url").value = data.base_url || "";
    document.getElementById("model").value = data.model || "";
    document.getElementById("api_key").value = "";
    const hint = document.getElementById("apiKeyHint");
    if (hint) {{
      const configured = (data.api_key_configured !== undefined) ? !!data.api_key_configured : !!(data.api_key && data.api_key !== "***");
      hint.textContent = configured ? ("当前 Key: " + (data.api_key || "***")) : "当前 Key: 未配置";
    }}
    const pathHint = document.getElementById("configPathHint");
    if (pathHint) {{
      const p = data.config_path || "";
      const exists = (data.config_exists !== undefined) ? (!!data.config_exists) : true;
      pathHint.textContent = p ? ("配置文件: " + p + (exists ? "" : "（不存在）")) : "";
    }}
    document.getElementById("max_steps").value = data.max_steps || "";
    document.getElementById("device_id").value = data.device_id || "";
    document.getElementById("lang").value = data.lang || "";
    setMsg("configMsg", "配置已加载（API Key 已隐藏，修改时请重新填写）");
  }} catch (e) {{
    setMsg("configMsg", "加载失败: " + e.message);
  }}
}}

async function saveConfig() {{
  const payload = {{
    base_url: document.getElementById("base_url").value.trim(),
    model: document.getElementById("model").value.trim(),
    api_key: document.getElementById("api_key").value.trim(),
    max_steps: document.getElementById("max_steps").value.trim(),
    device_id: document.getElementById("device_id").value.trim(),
    lang: document.getElementById("lang").value.trim(),
  }};
  try {{
    const data = await apiJson("/api/config", {{ method: "POST", body: JSON.stringify(payload) }});
    setMsg("configMsg", data.message || "已保存");
    await loadConfig();
  }} catch (e) {{
    setMsg("configMsg", "保存失败: " + e.message);
  }}
}}

function renderDevices(list, selected) {{
  const body = document.getElementById("devicesBody");
  body.textContent = "";
  for (const d of list) {{
    const tr = document.createElement("tr");

    const tdSerial = document.createElement("td");
    tdSerial.textContent = d.serial || "";
    if (selected && d.serial === selected) {{
      tdSerial.appendChild(document.createTextNode(" "));
      const pill = document.createElement("span");
      pill.className = "pill";
      pill.textContent = "selected";
      tdSerial.appendChild(pill);
    }}
    tr.appendChild(tdSerial);

    const tdStatus = document.createElement("td");
    tdStatus.textContent = d.status || "";
    tr.appendChild(tdStatus);

    const tdModel = document.createElement("td");
    tdModel.textContent = d.model || "";
    tr.appendChild(tdModel);

    const tdOps = document.createElement("td");
    const btnSelect = document.createElement("button");
    btnSelect.textContent = "选用";
    btnSelect.onclick = () => selectDevice(d.serial);
    const btnDisconnect = document.createElement("button");
    btnDisconnect.textContent = "断开";
    btnDisconnect.onclick = () => disconnectOne(d.serial);
    tdOps.appendChild(btnSelect);
    tdOps.appendChild(document.createTextNode(" "));
    tdOps.appendChild(btnDisconnect);
    tr.appendChild(tdOps);

    body.appendChild(tr);
  }}
}}

async function loadDevices() {{
  try {{
    const data = await apiJson("/api/adb/devices");
    renderDevices(data.devices || [], data.selected_device || "");
    setMsg("adbMsg", "设备已刷新");
  }} catch (e) {{
    setMsg("adbMsg", "刷新失败: " + e.message);
  }}
}}

async function adbPair() {{
  const host = document.getElementById("pair_host").value.trim();
  const code = document.getElementById("pair_code").value.trim();
  try {{
    const data = await apiJson("/api/adb/pair", {{ method: "POST", body: JSON.stringify({{ host, code }}) }});
    setMsg("adbMsg", data.output || data.message || "完成");
    await loadDevices();
  }} catch (e) {{
    setMsg("adbMsg", "配对失败: " + e.message);
  }}
}}

async function adbConnect() {{
  const host = document.getElementById("connect_host").value.trim();
  try {{
    const data = await apiJson("/api/adb/connect", {{ method: "POST", body: JSON.stringify({{ host }}) }});
    setMsg("adbMsg", data.output || data.message || "完成");
    await loadDevices();
  }} catch (e) {{
    setMsg("adbMsg", "连接失败: " + e.message);
  }}
}}

async function disconnectOne(serial) {{
  try {{
    const data = await apiJson("/api/adb/disconnect", {{ method: "POST", body: JSON.stringify({{ target: serial }}) }});
    setMsg("adbMsg", data.output || data.message || "完成");
    await loadDevices();
  }} catch (e) {{
    setMsg("adbMsg", "断开失败: " + e.message);
  }}
}}

async function adbDisconnectAll() {{
  try {{
    const data = await apiJson("/api/adb/disconnect", {{ method: "POST", body: JSON.stringify({{ target: "" }}) }});
    setMsg("adbMsg", data.output || data.message || "完成");
    await loadDevices();
  }} catch (e) {{
    setMsg("adbMsg", "断开失败: " + e.message);
  }}
}}

async function adbRestart() {{
  try {{
    const data = await apiJson("/api/adb/restart", {{ method: "POST" }});
    setMsg("adbMsg", data.output || data.message || "完成");
    await loadDevices();
  }} catch (e) {{
    setMsg("adbMsg", "重启失败: " + e.message);
  }}
}}

async function adbConnectWifi() {{
  try {{
    const data = await apiJson("/api/adb/connect_wifi", {{ method: "POST", body: JSON.stringify({{ port: 5555 }}) }});
    const addr = data.address ? (" | " + data.address) : "";
    setMsg("adbMsg", (data.output || data.message || "完成") + addr);
    await loadDevices();
  }} catch (e) {{
    setMsg("adbMsg", "USB→WiFi 失败: " + e.message);
  }}
}}

function setScreenMsg(msg) {{
  setMsg("screenMsg", msg);
}}

function stopScreenAuto() {{
  screenAuto = false;
  if (screenTimer) {{
    clearTimeout(screenTimer);
    screenTimer = 0;
  }}
  screenFailCount = 0;
  const btn = document.getElementById("screenAutoBtn");
  if (btn) btn.textContent = "自动刷新";
}}

function toggleScreenAuto() {{
  screenAuto = !screenAuto;
  const btn = document.getElementById("screenAutoBtn");
  if (btn) btn.textContent = screenAuto ? "停止自动" : "自动刷新";
  if (screenAuto) {{
    scheduleScreenAuto(0);
  }} else {{
    stopScreenAuto();
  }}
}}

function _screenBackoffMs() {{
  const base = 1200;
  const pow = Math.min(screenFailCount, 4);
  return Math.min(15000, base * Math.pow(2, pow));
}}

function scheduleScreenAuto(delayMs) {{
  if (!screenAuto) return;
  if (screenTimer) {{
    clearTimeout(screenTimer);
    screenTimer = 0;
  }}
  const ms = Math.max(0, parseInt(delayMs || 0, 10));
  screenTimer = setTimeout(async () => {{
    if (!screenAuto) return;
    if (!hasToken()) {{
      stopScreenAuto();
      return;
    }}
    if (document.visibilityState === "hidden") {{
      scheduleScreenAuto(5000);
      return;
    }}
    const ok = await refreshScreenshot();
    scheduleScreenAuto(ok ? 1200 : _screenBackoffMs());
  }}, ms);
}}

async function refreshScreenshot() {{
  try {{
    const data = await apiJson("/api/screen/screenshot");
    const img = document.getElementById("screenImg");
    if (!img) return;
    img.src = "data:image/png;base64," + (data.image_base64 || "");
    screenMeta = {{
      width: data.width || img.naturalWidth || 0,
      height: data.height || img.naturalHeight || 0,
      device_id: data.device_id || "",
    }};
    const sizeText = (screenMeta.width && screenMeta.height) ? (screenMeta.width + "x" + screenMeta.height) : "unknown";
    setScreenMsg("设备: " + (screenMeta.device_id || "(自动)") + " | 分辨率: " + sizeText);
    screenFailCount = 0;
    return true;
  }} catch (e) {{
    setScreenMsg("截图失败: " + e.message);
    screenFailCount += 1;
    return false;
  }}
}}

function addRipple(x, y) {{
  const wrap = document.getElementById("screenWrap");
  if (!wrap) return;
  const el = document.createElement("div");
  el.className = "ripple-circle";
  el.style.left = x + "px";
  el.style.top = y + "px";
  wrap.appendChild(el);
  setTimeout(() => {{
    try {{ wrap.removeChild(el); }} catch (e) {{ }}
  }}, 600);
}}

async function onScreenClick(ev) {{
  if (!hasToken()) return;
  if (screenTapInflight) return;
  const img = document.getElementById("screenImg");
  if (!img || !img.src) return;
  const rect = img.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const relX = (ev.clientX - rect.left) / rect.width;
  const relY = (ev.clientY - rect.top) / rect.height;
  const w = screenMeta.width || img.naturalWidth || 0;
  const h = screenMeta.height || img.naturalHeight || 0;
  if (!w || !h) return;
  const x = Math.max(0, Math.min(w - 1, Math.round(relX * w)));
  const y = Math.max(0, Math.min(h - 1, Math.round(relY * h)));
  addRipple(ev.clientX - rect.left, ev.clientY - rect.top);
  try {{
    screenTapInflight = true;
    const payload = {{ x, y, device_id: (screenMeta.device_id || "") }};
    const resp = await apiJson("/api/control/tap", {{ method: "POST", body: JSON.stringify(payload) }});
    const extra = (resp && resp.output) ? (" | " + resp.output) : "";
    setScreenMsg("已发送 tap: (" + x + "," + y + ")" + extra);
    // 截图是静态的；发送 tap 后小延迟刷新一帧，避免用户误以为没生效
    setTimeout(() => {{
      if (hasToken()) refreshScreenshot();
    }}, 350);
  }} catch (e) {{
    setScreenMsg("tap 失败: " + e.message);
  }} finally {{
    screenTapInflight = false;
  }}
}}

async function selectDevice(serial) {{
  try {{
    const data = await apiJson("/api/config/device", {{ method: "POST", body: JSON.stringify({{ device_id: serial }}) }});
    setMsg("adbMsg", data.message || "已设置");
    await loadDevices();
  }} catch (e) {{
    setMsg("adbMsg", "设置失败: " + e.message);
  }}
}}

// 任务
function renderTasks(list) {{
  tasksCache = list || [];
  const body = document.getElementById("tasksBody");
  body.textContent = "";
  const sel = document.getElementById("sched_task");
  if (sel) {{
    sel.textContent = "";
    for (const t of tasksCache) {{
      const opt = document.createElement("option");
      opt.value = t.id || "";
      opt.textContent = (t.name || t.id || "");
      sel.appendChild(opt);
    }}
  }}
  for (const t of tasksCache) {{
    const tr = document.createElement("tr");

    const tdId = document.createElement("td");
    tdId.textContent = t.id || "";
    tr.appendChild(tdId);

    const tdName = document.createElement("td");
    tdName.textContent = t.name || "";
    tr.appendChild(tdName);

    const tdOps = document.createElement("td");
    const btnRun = document.createElement("button");
    btnRun.textContent = "运行";
    btnRun.onclick = () => runTask(t.id);
    const btnEdit = document.createElement("button");
    btnEdit.textContent = "编辑";
    btnEdit.onclick = () => editTask(t.id);
    const btnDelete = document.createElement("button");
    btnDelete.textContent = "删除";
    btnDelete.onclick = () => deleteTask(t.id);
    tdOps.appendChild(btnRun);
    tdOps.appendChild(document.createTextNode(" "));
    tdOps.appendChild(btnEdit);
    tdOps.appendChild(document.createTextNode(" "));
    tdOps.appendChild(btnDelete);
    tr.appendChild(tdOps);

    body.appendChild(tr);
  }}
}}

async function loadTasks() {{
  try {{
    const data = await apiJson("/api/tasks");
    renderTasks(data.tasks || []);
    setMsg("taskMsg", "任务列表已刷新");
  }} catch (e) {{
    setMsg("taskMsg", "刷新失败: " + e.message);
  }}
}}

function resetTaskForm() {{
  document.getElementById("task_id").value = "";
  document.getElementById("task_name").value = "";
  document.getElementById("task_desc").value = "";
  document.getElementById("task_prompt").value = "";
  document.getElementById("task_steps").value = "";
  const out = document.getElementById("taskRunOutput");
  if (out) out.textContent = "";
}}

async function saveTask() {{
  const stepsRaw = document.getElementById("task_steps").value.trim() || "[]";
  let steps;
  try {{
    steps = JSON.parse(stepsRaw);
  }} catch (e) {{
    setMsg("taskMsg", "步骤 JSON 解析失败: " + e.message);
    return;
  }}
  const payload = {{
    id: document.getElementById("task_id").value.trim(),
    name: document.getElementById("task_name").value.trim(),
    description: document.getElementById("task_desc").value.trim(),
    prompt: document.getElementById("task_prompt").value.trim(),
    steps,
  }};
  try {{
    const data = await apiJson("/api/tasks", {{ method: "POST", body: JSON.stringify(payload) }});
    setMsg("taskMsg", data.message || "已保存");
    await loadTasks();
    if (!payload.id) resetTaskForm();
  }} catch (e) {{
    setMsg("taskMsg", "保存失败: " + e.message);
  }}
}}

function editTask(id) {{
  const t = tasksCache.find(x => x.id === id);
  if (!t) return;
  document.getElementById("task_id").value = t.id;
  document.getElementById("task_name").value = t.name || "";
  document.getElementById("task_desc").value = t.description || "";
  document.getElementById("task_prompt").value = t.prompt || "";
  document.getElementById("task_steps").value = JSON.stringify(t.steps || [], null, 2);
}}

// 调度
function resetScheduleForm() {{
  document.getElementById("sched_id").value = "";
  document.getElementById("sched_cron").value = "";
  document.getElementById("sched_enabled").checked = true;
  setMsg("schedMsg", "");
}}

function renderSchedules(list) {{
  const body = document.getElementById("schedBody");
  body.textContent = "";
  for (const s of list || []) {{
    const tr = document.createElement("tr");
    const tdId = document.createElement("td");
    tdId.textContent = s.id || "";
    tr.appendChild(tdId);
    const tdTask = document.createElement("td");
    const task = tasksCache.find(t => t.id === s.task_id);
    tdTask.textContent = task ? (task.name || task.id) : (s.task_id || "");
    tr.appendChild(tdTask);
    const tdCron = document.createElement("td");
    tdCron.textContent = s.cron || "";
    tr.appendChild(tdCron);
    const tdEnabled = document.createElement("td");
    const lastHist = (s.history || []).slice(-1)[0];
    const lastResult = lastHist ? ((lastHist.ok ? "OK" : "FAIL") + (lastHist.output ? (": " + lastHist.output) : "")) : "";
    tdEnabled.textContent = s.enabled ? "启用" : "停用";
    if (lastResult) tdEnabled.title = lastResult;
    tr.appendChild(tdEnabled);
    const tdLast = document.createElement("td");
    const lastTs = parseInt(s.last_run_ts || 0, 10);
    tdLast.textContent = lastTs ? new Date(lastTs * 1000).toLocaleString("zh-CN", {{ timeZone: "Asia/Shanghai" }}) : "-";
    tr.appendChild(tdLast);
    const tdOps = document.createElement("td");
    const btnFill = document.createElement("button");
    btnFill.textContent = "填入表单";
    btnFill.onclick = () => {{
      document.getElementById("sched_id").value = s.id || "";
      document.getElementById("sched_cron").value = s.cron || "";
      document.getElementById("sched_enabled").checked = !!s.enabled;
      document.getElementById("sched_task").value = s.task_id || "";
    }};
    const btnDel = document.createElement("button");
    btnDel.textContent = "删除";
    btnDel.onclick = () => deleteSchedule(s.id || "");
    tdOps.appendChild(btnFill);
    tdOps.appendChild(document.createTextNode(" "));
    tdOps.appendChild(btnDel);
    tr.appendChild(tdOps);
    body.appendChild(tr);
  }}
}}

async function loadSchedules() {{
  try {{
    const data = await apiJson("/api/schedules");
    renderSchedules(data.schedules || []);
    setMsg("schedMsg", "调度已刷新");
  }} catch (e) {{
    setMsg("schedMsg", "刷新失败: " + e.message);
  }}
}}

async function saveSchedule() {{
  const schedId = document.getElementById("sched_id").value.trim();
  const taskId = document.getElementById("sched_task").value.trim();
  const cron = document.getElementById("sched_cron").value.trim();
  const enabled = document.getElementById("sched_enabled").checked;
  if (!taskId) {{
    setMsg("schedMsg", "请选择任务");
    return;
  }}
  if (!cron) {{
    setMsg("schedMsg", "请填写 cron 表达式");
    return;
  }}
  try {{
    const payload = {{ id: schedId, task_id: taskId, cron, enabled }};
    const data = await apiJson("/api/schedules", {{ method: "POST", body: JSON.stringify(payload) }});
    setMsg("schedMsg", data.message || "已保存");
    await loadSchedules();
  }} catch (e) {{
    setMsg("schedMsg", "保存失败: " + e.message);
  }}
}}

async function deleteSchedule(id) {{
  if (!id) return;
  if (!confirm("删除该调度？")) return;
  try {{
    await apiJson(`/api/schedules/${{id}}`, {{ method: "DELETE" }});
    setMsg("schedMsg", "已删除");
    await loadSchedules();
  }} catch (e) {{
    setMsg("schedMsg", "删除失败: " + e.message);
  }}
}}

async function deleteTask(id) {{
  if (!confirm("删除该任务？")) return;
  try {{
    await apiJson(`/api/tasks/${{id}}`, {{ method: "DELETE" }});
    setMsg("taskMsg", "已删除");
    await loadTasks();
  }} catch (e) {{
    setMsg("taskMsg", "删除失败: " + e.message);
  }}
}}

function _clipText(s, maxLen) {{
  const t = (s || "").toString();
  const n = Math.max(200, parseInt(maxLen || 800, 10));
  return t.length > n ? (t.slice(0, n) + "...(truncated)") : t;
}}

async function runTask(id) {{
  try {{
    setMsg("taskMsg", "执行中…");
    const out = document.getElementById("taskRunOutput");
    if (out) out.textContent = "";
    const data = await apiJson(`/api/tasks/${{id}}/run`, {{ method: "POST", body: JSON.stringify({{}}) }});
    const results = (data && data.results) ? data.results : [];
    const lines = [];
    for (const r of results) {{
      const ok = !!r.ok;
      const t = (r.type || "step").toString();
      const o = _clipText(r.output || "", 1200);
      lines.push((ok ? "[OK] " : "[FAIL] ") + t + (o ? (\": \" + o) : \"\"));
    }}
    if (out) out.textContent = lines.join(\"\\n\\n\") || \"(无输出)\";
    const anyFail = results.some(r => !r.ok);
    setMsg("taskMsg", anyFail ? "执行结束（存在失败步骤）" : "执行完成");
  }} catch (e) {{
    setMsg("taskMsg", "执行失败: " + e.message);
  }}
}}

// 交互模式
async function startSession() {{
  try {{
    const data = await apiJson("/api/interactive/start", {{ method: "POST" }});
    sessionId = data.session_id;
    document.getElementById("sessionLabel").textContent = "会话: " + sessionId;
    setMsg("sessionMsg", "会话已创建");
    document.getElementById("sessionLog").textContent = "";
  }} catch (e) {{
    setMsg("sessionMsg", "创建失败: " + e.message);
  }}
}}

async function sendSession() {{
  const text = document.getElementById("session_input").value.trim();
  if (!sessionId) {{
    setMsg("sessionMsg", "请先创建会话");
    return;
  }}
  if (!text) return;
  try {{
    const data = await apiJson(`/api/interactive/${{sessionId}}/send`, {{ method: "POST", body: JSON.stringify({{ text }}) }});
    document.getElementById("sessionLog").textContent = (data.logs || []).join("\\n");
    document.getElementById("session_input").value = "";
  }} catch (e) {{
    setMsg("sessionMsg", "发送失败: " + e.message);
  }}
}}

// 已安装包名
async function fetchPackages() {{
  try {{
    const data = await apiJson("/api/adb/packages");
    const pkgs = data.packages || [];
    renderPackages(pkgs);
    setMsg("pkgMsg", "已获取 " + pkgs.length + " 个包名");
  }} catch (e) {{
    setMsg("pkgMsg", "获取失败: " + e.message);
  }}
}}

async function addToAppsConfig() {{
  const pkg = (document.getElementById("pkg_select").value || "").trim();
  if (!pkg) {{
    setMsg("pkgMsg", "请先获取并选择包名");
    return;
  }}
  const nameInput = document.getElementById("pkg_name").value.trim() || pkg;
  const payload = {{ items: [{{ name: nameInput, package: pkg }}] }};
  try {{
    const data = await apiJson("/api/adb/packages/add", {{ method: "POST", body: JSON.stringify(payload) }});
    setMsg("pkgMsg", data.message || "已写入 apps.py");
  }} catch (e) {{
    setMsg("pkgMsg", "写入失败: " + e.message);
  }}
}}

function renderPackages(list) {{
  packagesCache = Array.isArray(list) ? list : [];
  const sel = document.getElementById("pkg_select");
  if (!sel) return;
  sel.textContent = "";
  for (const pkg of packagesCache) {{
    const p = (pkg || "").toString();
    if (!p) continue;
    const opt = document.createElement("option");
    opt.value = p;
    opt.textContent = p;
    sel.appendChild(opt);
  }}
}}

async function loadSessionLog() {{
  if (!sessionId) return;
  try {{
    const data = await apiJson(`/api/interactive/${{sessionId}}/log`);
    document.getElementById("sessionLog").textContent = (data.logs || []).join("\\n");
  }} catch (e) {{
    setMsg("sessionMsg", "获取日志失败: " + e.message);
  }}
}}

async function autoglmStart() {{
  try {{
    const data = await apiJson("/api/autoglm/start", {{ method: "POST" }});
    setMsg("runMsg", data.message || "已启动");
    await autoglmStatus();
  }} catch (e) {{
    setMsg("runMsg", "启动失败: " + e.message);
  }}
}}

async function autoglmStop() {{
  try {{
    const data = await apiJson("/api/autoglm/stop", {{ method: "POST" }});
    setMsg("runMsg", data.message || "已停止");
    await autoglmStatus();
  }} catch (e) {{
    setMsg("runMsg", "停止失败: " + e.message);
  }}
}}

async function autoglmStatus() {{
  try {{
    const data = await apiJson("/api/autoglm/status");
    document.getElementById("runPill").textContent = data.running ? ("running pid=" + data.pid) : "stopped";
  }} catch (e) {{
    document.getElementById("runPill").textContent = "unknown";
    setMsg("runMsg", "状态获取失败: " + e.message);
  }}
}}

function clearLogView() {{
  document.getElementById("logBox").textContent = "";
}}

function toggleFollow() {{
  follow = !follow;
  document.getElementById("followBtn").textContent = follow ? "暂停滚动" : "恢复滚动";
}}

async function pollLogs() {{
  try {{
    const data = await apiJson("/api/logs/tail?offset=" + logOffset);
    if (data && data.text) {{
      const box = document.getElementById("logBox");
      box.textContent += data.text;
      if (follow) box.scrollTop = box.scrollHeight;
    }}
    logOffset = data.offset || logOffset;
  }} catch (e) {{
    // token 未填/服务未启动时会报错，忽略即可
  }}
  setTimeout(pollLogs, 1000);
}}

async function loadChecks() {{
  try {{
    const data = await apiJson("/api/checks");
    const items = [];
    if (data.adb && !data.adb.ok) items.push("ADB: " + (data.adb.message || "异常"));
    if (data.autoglm_dir && !data.autoglm_dir.ok) items.push("Open-AutoGLM: " + (data.autoglm_dir.message || "异常"));
    if (data.config && !data.config.ok) items.push("配置: " + (data.config.message || "异常"));
    if (data.device && !data.device.ok) items.push("设备: " + (data.device.message || "异常"));
    setMsg("checkMsg", items.length ? ("自检: " + items.join(" | ")) : "自检: OK");
  }} catch (e) {{
    // 没有 Token 时会报错，忽略即可
    setMsg("checkMsg", "");
  }}
}}

async function refreshAll() {{
  if (!hasToken()) {{
    setMsg("checkMsg", "请先粘贴并保存 Token");
    setMsg("configMsg", "");
    setMsg("apiKeyHint", "");
    setMsg("configPathHint", "");
    setMsg("adbMsg", "");
    setMsg("taskMsg", "");
    setMsg("runMsg", "");
    setScreenMsg("");
    stopScreenAuto();
    return;
  }}
  await loadChecks();
  await loadConfig();
  await loadDevices();
  await loadTasks();
  await loadSchedules();
  await autoglmStatus();
  await refreshScreenshot();
}}

async function loadServerInfo() {{
  const r = await fetch("/api/info");
  const j = await r.json();
  let text = "监听 " + j.host + ":" + j.port;
  if (j.urls && j.urls.length) {{
    text += " | 访问: " + j.urls.join("  ");
  }}
  document.getElementById("serverInfo").textContent = text;
}}

document.getElementById("token").value = localStorage.getItem(LS_TOKEN_KEY) || "";
const screenImgEl = document.getElementById("screenImg");
if (screenImgEl) screenImgEl.addEventListener("click", onScreenClick);
initTabs();
document.addEventListener("visibilitychange", () => {{
  if (!screenAuto) return;
  if (document.visibilityState === "visible") {{
    scheduleScreenAuto(0);
  }}
}});
loadServerInfo();
refreshAll();
pollLogs();
</script>
</body>
</html>"""


@app.get("/api/info")
def info() -> dict[str, Any]:
    return _server_info()

@app.get("/api/checks")
def checks(_: AuthResult = Depends(require_token)) -> dict[str, Any]:
    ok_adb, out_adb = adb_version()
    st = autoglm_status()
    autoglm_dir = st.autoglm_dir
    ok_dir = bool(autoglm_dir) and os.path.isdir(autoglm_dir)
    cfg = read_config()
    ok_cfg = _api_key_configured(cfg)
    cfg_msg = "已配置" if ok_cfg else "API Key 未配置（请在 Web 配置中填写并保存）"

    # 设备自检：未选设备且多设备在线时，任务/交互模式可能失败
    try:
        ds = devices(raise_on_error=False)
        online = [d.serial for d in ds if d.status == "device"]
    except Exception:
        online = []
    device_id = (cfg.device_id or "").strip()
    ok_device = bool(device_id) or len(online) == 1
    if device_id:
        device_msg = f"已选择: {device_id}"
    elif len(online) == 1:
        device_msg = f"未选择（将自动使用: {online[0]}）"
    elif len(online) > 1:
        device_msg = "未选择（多设备在线，请在设备列表点“选用”）"
    else:
        device_msg = "未检测到在线设备"
    return {
        "adb": {"ok": ok_adb, "message": out_adb or ("正常" if ok_adb else "异常")},
        "autoglm_dir": {"ok": ok_dir, "path": autoglm_dir, "message": ("目录存在" if ok_dir else f"目录不存在: {autoglm_dir}")},
        "config": {"ok": ok_cfg, "message": cfg_msg},
        "device": {"ok": ok_device, "selected": device_id, "online": online, "message": device_msg},
    }


@app.get("/api/config")
def get_config(_: AuthResult = Depends(require_token)) -> JSONResponse:
    cfg = read_config()
    data = cfg.as_public_dict(mask_api_key=True)
    data["api_key_configured"] = _api_key_configured(cfg)
    data["config_path"] = str(config_sh_path())
    data["config_exists"] = config_exists()
    return JSONResponse(data)


@app.post("/api/config")
def set_config(payload: dict[str, Any], _: AuthResult = Depends(require_token)) -> dict[str, Any]:
    cfg = read_config()
    base_url = str(payload.get("base_url", cfg.base_url) or cfg.base_url).strip()
    model = str(payload.get("model", cfg.model) or cfg.model).strip()
    api_key = str(payload.get("api_key", "") or "").strip()
    max_steps = str(payload.get("max_steps", cfg.max_steps) or cfg.max_steps).strip()
    device_id_raw = payload.get("device_id", None)
    device_id = str(device_id_raw if device_id_raw is not None and str(device_id_raw).strip() != "" else cfg.device_id).strip()
    lang = str(payload.get("lang", cfg.lang) or cfg.lang).strip()

    if not api_key:
        # 如果当前配置文件不存在或仍是默认占位符，则拒绝保存空的 API Key，避免覆盖真实配置
        if not config_exists() or cfg.api_key == "sk-your-apikey":
            raise HTTPException(status_code=400, detail="首次保存配置必须填写有效的 API Key")
        api_key = cfg.api_key

    updated = AutoglmConfig(
        base_url=base_url,
        model=model,
        api_key=api_key,
        max_steps=max_steps,
        device_id=device_id,
        lang=lang,
    )
    write_config(updated)
    return {"ok": True, "message": "配置已保存"}


@app.post("/api/config/device")
def set_device(payload: dict[str, Any], _: AuthResult = Depends(require_token)) -> dict[str, Any]:
    device_id = str(payload.get("device_id", "") or "").strip()
    update_device_id(device_id)
    return {"ok": True, "message": f"已设置设备: {device_id or '自动检测'}"}


@app.get("/api/adb/devices")
def adb_devices(_: AuthResult = Depends(require_token)) -> dict[str, Any]:
    cfg = read_config()
    try:
        ds = devices(raise_on_error=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"devices": [d.__dict__ for d in ds], "selected_device": cfg.device_id or ""}

@app.get("/api/adb/packages")
def adb_packages(limit: int | None = None, _: AuthResult = Depends(require_token)) -> dict[str, Any]:
    max_limit = 5000
    if limit is None or limit <= 0:
        limit = max_limit
    limit = min(limit, max_limit)
    cfg = read_config()
    device_id = (cfg.device_id or "").strip() or None
    if not device_id:
        ds = devices(raise_on_error=False)
        for d in ds:
            if d.status == "device":
                device_id = d.serial
                break
    if not device_id:
        raise HTTPException(status_code=400, detail="未选择设备（请先在设备列表中点“选用”）")
    try:
        pkgs = list_packages(third_party=True, device_id=device_id, raise_on_error=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    pkgs = pkgs[:limit]
    return {"packages": pkgs, "device_id": device_id, "count": len(pkgs), "limit": limit}

# 写入 apps.py
@app.post("/api/adb/packages/add")
def adb_packages_add(payload: dict[str, Any], _: AuthResult = Depends(require_token)) -> dict[str, Any]:
    items = payload.get("items", [])
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=400, detail="items 不能为空")
    entries: dict[str, str] = {}
    for it in items:
        name = str(it.get("name", "")).strip()
        pkg = str(it.get("package", "")).strip()
        if not name or not pkg:
            continue
        entries[name] = pkg
    if not entries:
        raise HTTPException(status_code=400, detail="未提供有效的 name/package")
    try:
        data = add_entries(entries)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True, "size": len(data), "message": f"已写入 {len(entries)} 项到 apps.py"}

# 任务
@app.get("/api/tasks")
def api_list_tasks(_: AuthResult = Depends(require_token)) -> dict[str, Any]:
    return {"tasks": list_tasks()}


@app.post("/api/tasks")
def api_save_task(payload: dict[str, Any], _: AuthResult = Depends(require_token)) -> dict[str, Any]:
    steps = payload.get("steps", [])
    if not isinstance(steps, list):
        raise HTTPException(status_code=400, detail="steps 必须为数组")
    task = {
        "id": str(payload.get("id", "") or ""),
        "name": str(payload.get("name", "") or ""),
        "description": str(payload.get("description", "") or ""),
        "prompt": str(payload.get("prompt", "") or ""),
        "steps": steps,
    }
    saved = upsert_task(task)
    return {"ok": True, "task": saved, "message": "已保存"}


@app.delete("/api/tasks/{task_id}")
def api_delete_task(task_id: str, _: AuthResult = Depends(require_token)) -> dict[str, Any]:
    ok = delete_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="未找到任务")
    return {"ok": True}


@app.post("/api/tasks/{task_id}/run")
def api_run_task(task_id: str, payload: dict[str, Any] | None = None, _: AuthResult = Depends(require_token)) -> dict[str, Any]:
    params = payload or {}
    try:
        results = run_task_by_id(task_id, params)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True, "results": results}


# 调度
@app.get("/api/schedules")
def api_list_schedules(_: AuthResult = Depends(require_token)) -> dict[str, Any]:
    return {"schedules": schedule.list_schedules()}


@app.post("/api/schedules")
def api_save_schedule(payload: dict[str, Any], _: AuthResult = Depends(require_token)) -> dict[str, Any]:
    task_id = str(payload.get("task_id", "")).strip()
    cron = str(payload.get("cron", "")).strip()
    sched_id = str(payload.get("id", "")).strip()
    enabled = bool(payload.get("enabled", True))
    tasks = list_tasks()
    if not task_id or not any(t.get("id") == task_id for t in tasks):
        raise HTTPException(status_code=400, detail="任务不存在")
    if not cron or not schedule.is_valid_cron(cron):
        raise HTTPException(status_code=400, detail="cron 表达式无效（需 6 段，秒 分 时 日 月 周）")
    existing = None
    for s in schedule.list_schedules():
        if s.get("id") == sched_id:
            existing = s
            break
    base = existing or {}
    new_sched = {
        "id": sched_id,
        "task_id": task_id,
        "cron": cron,
        "enabled": enabled,
        "last_run_ts": base.get("last_run_ts", 0),
        "history": base.get("history", []),
    }
    saved = schedule.upsert_schedule(new_sched)
    schedule.ensure_scheduler_started()
    return {"ok": True, "schedule": saved, "message": "调度已保存"}


@app.delete("/api/schedules/{sched_id}")
def api_delete_schedule(sched_id: str, _: AuthResult = Depends(require_token)) -> dict[str, Any]:
    ok = schedule.delete_schedule(sched_id)
    if not ok:
        raise HTTPException(status_code=404, detail="未找到调度")
    return {"ok": True}

# 交互模式（仅日志片段）
@app.post("/api/interactive/start")
def api_interactive_start(_: AuthResult = Depends(require_token)) -> dict[str, Any]:
    sid = new_session()
    return {"session_id": sid}


@app.post("/api/interactive/{sid}/send")
def api_interactive_send(sid: str, payload: dict[str, Any], _: AuthResult = Depends(require_token)) -> dict[str, Any]:
    text = str(payload.get("text", "") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text 不能为空")
    try:
        logs = send_interactive(sid, text)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"logs": logs}


@app.get("/api/interactive/{sid}/log")
def api_interactive_log(sid: str, _: AuthResult = Depends(require_token)) -> dict[str, Any]:
    logs = get_interactive_log(sid)
    return {"logs": logs}


@app.post("/api/adb/pair")
def adb_pair(payload: dict[str, Any], _: AuthResult = Depends(require_token)) -> dict[str, Any]:
    host = str(payload.get("host", "") or "").strip()
    code = str(payload.get("code", "") or "").strip()
    if not host or not code:
        raise HTTPException(status_code=400, detail="host/code 不能为空")
    ok, out = pair(host, code)
    if not ok:
        raise HTTPException(status_code=500, detail=out or "pair failed")
    return {"ok": True, "output": out}


@app.post("/api/adb/connect")
def adb_connect(payload: dict[str, Any], _: AuthResult = Depends(require_token)) -> dict[str, Any]:
    host = str(payload.get("host", "") or "").strip()
    if not host:
        raise HTTPException(status_code=400, detail="host 不能为空")
    ok, out = connect(host)
    if not ok:
        raise HTTPException(status_code=500, detail=out or "connect failed")
    return {"ok": True, "output": out}


@app.post("/api/adb/disconnect")
def adb_disconnect(payload: dict[str, Any], _: AuthResult = Depends(require_token)) -> dict[str, Any]:
    target = str(payload.get("target", "") or "").strip()
    ok, out = disconnect(target or None)
    if not ok:
        raise HTTPException(status_code=500, detail=out or "disconnect failed")
    return {"ok": True, "output": out}


@app.post("/api/adb/restart")
def adb_restart(_: AuthResult = Depends(require_token)) -> dict[str, Any]:
    ok, out = restart_server()
    if not ok:
        raise HTTPException(status_code=500, detail=out or "restart failed")
    return {"ok": True, "output": out}


@app.post("/api/adb/connect_wifi")
def adb_connect_wifi_api(payload: dict[str, Any] | None = None, _: AuthResult = Depends(require_token)) -> dict[str, Any]:
    payload = payload or {}
    port = int(payload.get("port", 5555) or 5555)
    cfg = read_config()
    device_id = str(payload.get("device_id", "") or "").strip() or (cfg.device_id or "")
    if not device_id:
        # 兜底：选择第一个在线设备
        ds = devices(raise_on_error=False)
        for d in ds:
            if d.status == "device":
                device_id = d.serial
                break
    if not device_id:
        raise HTTPException(status_code=400, detail="未指定 device_id，且未检测到在线设备")

    ok, out, address = adb_connect_wifi(device_id=device_id, port=port)
    if not ok:
        raise HTTPException(status_code=500, detail=out or "connect_wifi failed")
    return {"ok": True, "output": out, "address": address, "device_id": device_id}


@app.get("/api/screen/screenshot")
def api_screenshot(device_id: str | None = None, _: AuthResult = Depends(require_token)) -> dict[str, Any]:
    cfg = read_config()
    resolved = (device_id or "").strip() or (cfg.device_id or "").strip() or None
    if not resolved:
        ds = devices(raise_on_error=False)
        for d in ds:
            if d.status == "device":
                resolved = d.serial
                break
    if not resolved:
        raise HTTPException(status_code=400, detail="未选择设备（请先在设备列表中点“选用”）")
    ok, b64, meta, msg = screenshot_base64(device_id=resolved, timeout_s=10, retries=1)
    if not ok:
        raise HTTPException(status_code=500, detail=msg or "screenshot failed")
    return {
        "ok": True,
        "device_id": resolved or "",
        "image_base64": b64,
        "width": meta.get("width"),
        "height": meta.get("height"),
    }


@app.post("/api/control/tap")
def api_control_tap(payload: dict[str, Any], _: AuthResult = Depends(require_token)) -> dict[str, Any]:
    cfg = read_config()
    try:
        x = int(payload.get("x", 0))
        y = int(payload.get("y", 0))
    except Exception:
        raise HTTPException(status_code=400, detail="x/y 必须为整数")
    device_id = str(payload.get("device_id", "") or "").strip() or (cfg.device_id or "").strip() or None
    if not device_id:
        ds = devices(raise_on_error=False)
        for d in ds:
            if d.status == "device":
                device_id = d.serial
                break
    if not device_id:
        raise HTTPException(status_code=400, detail="未选择设备（请先在设备列表中点“选用”）")
    ok, out = adb_tap(x, y, device_id=device_id)
    if not ok:
        raise HTTPException(status_code=500, detail=out or "tap failed")
    return {"ok": True, "output": out or ""}


@app.post("/api/control/swipe")
def api_control_swipe(payload: dict[str, Any], _: AuthResult = Depends(require_token)) -> dict[str, Any]:
    cfg = read_config()
    try:
        x1 = int(payload.get("x1", 0))
        y1 = int(payload.get("y1", 0))
        x2 = int(payload.get("x2", 0))
        y2 = int(payload.get("y2", 0))
        duration_ms = int(payload.get("duration_ms", 300))
    except Exception:
        raise HTTPException(status_code=400, detail="x1/y1/x2/y2/duration_ms 必须为整数")
    device_id = str(payload.get("device_id", "") or "").strip() or (cfg.device_id or "").strip() or None
    if not device_id:
        ds = devices(raise_on_error=False)
        for d in ds:
            if d.status == "device":
                device_id = d.serial
                break
    if not device_id:
        raise HTTPException(status_code=400, detail="未选择设备（请先在设备列表中点“选用”）")
    ok, out = adb_swipe(x1, y1, x2, y2, duration_ms, device_id=device_id)
    if not ok:
        raise HTTPException(status_code=500, detail=out or "swipe failed")
    return {"ok": True, "output": out or ""}


@app.get("/api/autoglm/status")
def get_status(_: AuthResult = Depends(require_token)) -> dict[str, Any]:
    st = autoglm_status()
    return {"running": st.running, "pid": st.pid, "log_path": st.log_path, "autoglm_dir": st.autoglm_dir}


@app.post("/api/autoglm/start")
def start(_: AuthResult = Depends(require_token)) -> dict[str, Any]:
    cfg = read_config()
    ok, msg = start_autoglm(cfg)
    if not ok:
        raise HTTPException(status_code=500, detail=msg)
    return {"ok": True, "message": msg}


@app.post("/api/autoglm/stop")
def stop(_: AuthResult = Depends(require_token)) -> dict[str, Any]:
    ok, msg = stop_autoglm()
    if not ok:
        raise HTTPException(status_code=500, detail=msg)
    return {"ok": True, "message": msg}


@app.get("/api/logs/tail")
def logs_tail(offset: int = 0, _: AuthResult = Depends(require_token)) -> dict[str, Any]:
    new_offset, text = tail_log(offset)
    return {"offset": new_offset, "text": text}
