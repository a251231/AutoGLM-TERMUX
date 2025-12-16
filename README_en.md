AutoGLM-Termux Deployment Tool

[![Version](https://img.shields.io/badge/Version-4.6.0-brightgreen)](https://github.com/eraycc/AutoGLM-TERMUX)
[![Open-AutoGLM](https://img.shields.io/badge/Open--AutoGLM-Latest-blue)](https://github.com/zai-org/Open-AutoGLM)
[![Termux](https://img.shields.io/badge/Termux-Supported-black)](https://termux.dev/)
[![License](https://img.shields.io/badge/License-MIT-orange)](https://opensource.org/licenses/MIT)

[🌐 Switch to Chinese document / 切换到中文文档](https://github.com/eraycc/AutoGLM-TERMUX/blob/main/README.md)

Quickly deploy the Open-AutoGLM agent on your Android phone via Termux—no ROOT or PC required. Achieve full phone automation!

---

📖 Project Overview

AutoGLM-Termux is a one-click deployment solution for Open-AutoGLM, optimized for Termux. Using a pure-ADB approach, it turns your Android phone into an AI agent that can:
- Understand natural-language commands
- Automatically perform phone operations (tap, swipe, type, etc.)
- Support 50+ mainstream apps
- Enhanced ADB device management: multi-device switching, fast connection, device-status monitoring
- One-click uninstall: completely remove the project and runtime environment
- Fully wireless control—no Root required
- NEW: full internationalization support; switch between Chinese and English

> ⚠️ Compliance statement: this project is for educational and research purposes only. Any illegal use is strictly prohibited. Please comply with the [Open-AutoGLM Terms of Use](https://github.com/zai-org/Open-AutoGLM/blob/main/resources/privacy_policy.txt).

---

✨ Features

- One-click deployment: automatically installs all dependencies and configures the environment
- Smart mirrors: auto-configures domestic pip & Cargo mirrors for faster downloads (type `default` to use recommended Chinese sources)
- Wireless ADB: built-in wizard for wireless-debugging setup—no cable needed
- ADB device manager: visual device list, switch active device, disconnect, quick-reconnect
- Interactive menu: visual launch panel for easier config management
- Auto-reconnect: automatic ADB device detection & connection
- Persistent config: environment variables auto-saved; no re-config needed after Termux restarts
- Multi-device support: on the same LAN (VPN off), one Android device can wirelessly debug and control other Android phones; manage multiple ADB devices
- One-click uninstall: basic or full uninstall modes for clean removal
- NEW: multi-language support—freely switch between Chinese and English

---

🍭 Deployment Demo

![1000114284](https://github.com/user-attachments/assets/d4e89a3c-8d39-41a8-a44e-bed00c74fdb0)

![1000114273](https://github.com/user-attachments/assets/3ca780ce-631c-4ae3-996a-8f3bf4eb4037)

![1000114283](https://github.com/user-attachments/assets/dd618ffc-4138-4bcf-bf0a-03562b364875)

---

📱 Prerequisites

1. Android phone (Android 7.0+)
2. Termux installed ([download](https://github.com/termux/termux-app/releases/))
3. Network: phone and Termux on the same Wi-Fi
4. API Key: Zhipu AI or ModelScope (or any image-capable AI model)
5. ADB Keyboard (mandatory):
   - Download: https://github.com/senzhk/ADBKeyBoard/blob/master/ADBKeyboard.apk
   - After install: Settings → System → Languages & input → Virtual keyboard → Manage keyboards → enable “ADB Keyboard”
   - Required—otherwise Chinese input fails

---

🚀 Quick Start (Recommended)

Run inside Termux:

```bash
# 1. Update Termux package list
pkg upgrade -y

# 2. Download deployment script
curl -O https://raw.githubusercontent.com/eraycc/AutoGLM-TERMUX/refs/heads/main/deploy.sh

# 3. Make executable
chmod +x deploy.sh

# 4. Run
./deploy.sh
```

After deployment, type `autoglm` to launch the control panel.

---

📋 Detailed Installation

Step 1: Install Termux

Download the latest Termux APK from [GitHub Releases](https://github.com/termux/termux-app/releases/) and install.

Step 2: Update Termux

On first launch run:

```bash
pkg upgrade -y
```

Step 3: Speed up Termux pkg mirrors

Run:

```bash
termux-change-repo
```

- Select “Mirror group – Rotate between several mirrors (recommended)”
- Choose “Mirrors in your area”
- Confirm and wait for auto-configuration

Step 4: Run deployment script

```bash
curl -O https://raw.githubusercontent.com/eraycc/AutoGLM-TERMUX/refs/heads/main/deploy.sh
chmod +x deploy.sh
./deploy.sh
```

Step 5: Script workflow

The script will:
1. Language selection (Chinese / English)
2. Install dependencies: Python, pip, Git, Rust, ADB (auto-detects package managers)
3. Mirror config (optional; type `default` for recommended Chinese mirrors)
4. Install Python packages: maturin, openai, requests, Pillow (Pillow via pkg in Termux)
5. Clone project: pull latest Open-AutoGLM from GitHub
6. Interactive config: API Key, model params, device ID
7. Remind you to install ADB Keyboard (mandatory)
8. Wireless ADB wizard (auto-detects already-paired devices)
9. Create launcher: `autoglm` command added to PATH

---

🎮 Usage

Start control panel

```bash
autoglm
```

Main menu

```
1. 🚀 Start with current config   # Run AutoGLM (auto-detects device)
2. 📱 ADB device manager          # Enhanced device-management sub-menu
3. ⚙️  Modify AI config            # Change API Key, model, etc.
4. 📋 List supported apps          # Show 50+ supported apps
5. 🔍 View detailed config         # Display all current settings
6. 🌐 Switch language              # Toggle Chinese / English
7. 🗑️  One-click uninstall         # Enter uninstall menu
0. ❌ Exit                         # Quit
```

ADB device manager sub-menu

```
1. 📱 Pair new device (pair + connect)
2. ⚡ Quick connect (already paired)
3. 📋 Detailed device list
4. 🔄 Switch active device
5. 🔌 Disconnect device
6. ❓ ADB Keyboard install guide
0. ↩️  Back to main menu
```

Command-line options

```bash
# Start directly (skip menu)
autoglm --start

# Enter ADB manager
autoglm --setup-adb

# Quick device list
autoglm --devices

# Switch active device
autoglm --switch-device

# Disconnect
autoglm --disconnect

# Re-configure
autoglm --reconfig

# List supported apps
autoglm --list-apps

# Uninstall menu
autoglm --uninstall

# Switch language
autoglm --lang cn    # Chinese
autoglm --lang en    # English

# Manual launch with params
autoglm --base-url URL --model MODEL --apikey KEY --device-id ID "your command"

# Help
autoglm --help
```

Examples

```bash
# Ex 1: Open Meituan and search for hot-pot
autoglm
# Then type: 打开美团搜索附近的火锅店

# Ex 2: Run command directly
autoglm --base-url https://open.bigmodel.cn/api/paas/v4 \
        --model autoglm-4.6.0 \
        --apikey sk-xxxxx \
        "Open WeChat and send 'Hello World' to File Transfer"

# Ex 3: Multi-device—switch to specific device
autoglm --switch-device
# or
autoglm --device-id 192.168.1.100:5555 "Open Bilibili"

# Ex 4: Quick device status
autoglm --devices

# Ex 5: Switch to English
autoglm --lang en
```

---

🎯 Advanced: Add Custom Apps

Besides the built-in 50+ apps, you can extend support by editing the config file.

Preparation

Install MT Manager: https://mt2.cn/download/

Steps  
1. Grant MT Manager access to Termux files  
   - Open MT Manager → side-bar → “⋮” → “Add local storage”  
   - “⋮” again → choose “Termux” → “Use this folder”

2. Edit app config  
   - Navigate to: `Open-AutoGLM/phone_agent/config/apps.py`  
   - Open `apps.py`, locate `APP_PACKAGES` dict  
   - Append: `"AppName": "package.name"`

Example

```python
    # Custom apps
    "via": "mark.via",
    "Browser": "mark.via",
    "ViaBrowser": "mark.via",
    "HoYolab": "com.mihoyo.hyperion",
    "FClash": "com.follow.clash",
    "ClashMeta": "com.github.metacubex.clash.meta",
    "DeepSeek": "chat.deepseek.com",
    "GenshinCloud": "com.miHoYo.cloudgames.ys",
    "Firefox": "org.mozilla.firefox",
    "Telegram": "org.telegram.messenger.web",
    "Kimi": "com.moonshot.kimichat",
    "Kugou Lite": "com.kugou.android.lite",
    "MT Manager": "bin.mt.plus",
    "YouTube": "com.google.android.youtube",
    "Weibo Lite": "com.web.weibo",
    # add more...
```

Save and restart AutoGLM.

Notes  
- Find exact package names via store links or MT Manager’s “Installed packages” tool  
- Back up the original file before editing  
- Some apps may need extra steps for full automation

---

⚙️ Configuration

Environment variables

Stored in `~/.autoglm/config.sh`:

Variable	Meaning	Default	
`PHONE_AGENT_BASE_URL`	API base URL	`https://open.bigmodel.cn/api/paas/v4`	
`PHONE_AGENT_MODEL`	Model name	`autoglm-phone`	
`PHONE_AGENT_API_KEY`	Your API key	`sk-your-apikey`	
`PHONE_AGENT_MAX_STEPS`	Max steps	`100`	
`PHONE_AGENT_DEVICE_ID`	ADB device ID (new)	auto-detected (empty)	
`PHONE_AGENT_LANG`	UI language	`cn`	

New:
- `PHONE_AGENT_DEVICE_ID`: specify target device as `IP:port` or serial; leave empty to auto-detect single online device
- `PHONE_AGENT_LANG`: `cn` (Chinese) or `en` (English)

Supported model services (image understanding required)

1. Zhipu BigModel (recommended; official autoglm-phone currently free)

   Base URL: `https://open.bigmodel.cn/api/paas/v4`

   Model: `autoglm-phone`

   Apply: [BigModel AFF](https://www.bigmodel.cn/claude-code?ic=COJZ8EMHXZ)

2. ModelScope

   Base URL: `https://api-inference.modelscope.cn/v1`

   Model: `ZhipuAI/AutoGLM-Phone-9B`

   Apply: [ModelScope](https://modelscope.cn/)

3. Other OpenAI-compatible APIs

   Ensure the model supports image input

---

📦 Project Layout

```
~/
├── Open-AutoGLM/            # Project code
├── .autoglm/
│   └── config.sh           # Config file
├── bin/
│   └── autoglm             # Launcher (auto-added to PATH)
└── .cargo/
    └── config.toml         # Cargo mirror config
```

---

🔍 Supported Apps

Run `autoglm --list-apps` for the full list. Highlights:

- Social: WeChat, QQ, Weibo  
- Shopping: Taobao, JD, Pinduoduo  
- Food delivery: Meituan, Ele.me, KFC  
- Travel: Ctrip, 12306, Didi  
- Video: Bilibili, Douyin, iQiyi  
- Music: NetEase Cloud, QQ Music, Ximalaya  
- Lifestyle: Dianping, Amap, Baidu Maps  
- Communities: Xiaohongshu, Zhihu, Douban

---

🗑️ Uninstall

Two safe modes:

Basic uninstall (recommended)

Removes Open-AutoGLM + control panel; optionally deletes pip deps, project folder, command, config; keeps runtime environment untouched.

Full uninstall (caution)

Also removes core pip packages (maturin, openai, requests, Pillow), pip/Cargo mirrors, Termux system packages (python-pillow, rust, android-tools).

⚠️ May break other programs that depend on these packages.

Run:

```bash
autoglm --uninstall
```

Follow the interactive menu.

---

⚠️ Troubleshooting

1. `adb devices` empty or unauthorized  
   - Enable USB debugging & wireless debugging  
   - Same Wi-Fi  
   - Tap “Allow USB debugging” on phone  
   - Re-pair: `adb pair`  
   - Restart server: `adb kill-server && adb start-server`

2. App opens but no tap/input  
   - Enable “USB debugging (security settings)” on some brands  
   - ADB Keyboard MUST be enabled and selected (Agent auto-switches)

3. Black screenshots  
   - Normal for sensitive pages (payment, banking)  
   - Some apps block screenshots; Agent will ask for manual takeover

4. Model connection fails  
   - Check API Key validity  
   - Termux must reach internet  
   - Base URL must end with `/v1`

5. Multi-device selection issues  
   - `autoglm --devices` to list  
   - `autoglm --switch-device` to pick  
   - Or set `PHONE_AGENT_DEVICE_ID="IP:port"`

6. Env vars not applied

```bash
   source ~/.bashrc
   # or
   source ~/.autoglm/config.sh
```

7. `autoglm` still available after uninstall  
   - Restart terminal, or  
   - `source ~/.bashrc`, or  
   - `hash -r`

8. Update fails

```bash
   rm -rf ~/Open-AutoGLM
   ./deploy.sh
```

9. Language switch  
   - `autoglm --lang cn` / `autoglm --lang en`  
   - Or use main-menu option

---

🔄 Changelog

v4.6.0 (current)  
- Full i18n: Chinese/English UI toggle  
- Language wizard during deployment

v4.5.0  
- Enhanced ADB manager: list, switch, disconnect, quick-connect  
- One-click uninstall (basic / full)  
- Multi-device: specify device ID, auto-detect online devices  
- Cleaner status display (online/offline/unauthorized)  
- Fixed device-count arithmetic  
- New CLI flags: `--devices`, `--switch-device`, `--disconnect`, `--uninstall`  
- Compatible with multiple package managers (apt, yum, pacman, brew)

v4.3.0  
- Interactive launcher `autoglm`  
- Wireless ADB pairing wizard  
- Auto pip & Cargo mirror config  
- Multi-device support

v4.2.0  
- Better Termux compatibility  
- ADB Keyboard install reminder  
- Persistent configuration

---

🤝 Contributing

Issues & PRs welcome!

1. Fork the repo  
2. Create feature branch (`git checkout -b feature/AmazingFeature`)  
3. Commit (`git commit -m 'Add some AmazingFeature'`)  
4. Push (`git push origin feature/AmazingFeature`)  
5. Open Pull Request

---

📄 License

MIT. See [LICENSE](LICENSE).

---

🔗 Links

- Open-AutoGLM: https://github.com/zai-org/Open-AutoGLM  
- Termux: https://termux.dev/  
- AutoGLM paper: https://arxiv.org/abs/2411.00820  
- Zhipu AI: https://www.zhipuai.cn/  
- ModelScope: https://modelscope.cn/

---

🙏 Credits

- [Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM) – core framework  
- [ADBKeyBoard](https://github.com/senzhk/ADBKeyBoard) – input solution  
- [Termux](https://termux.dev/) – powerful terminal emulator

---

💬 Community

Need help?

- Open an [Issue](https://github.com/eraycc/AutoGLM-TERMUX/issues)  
- Read [Open-AutoGLM docs](https://github.com/zai-org/Open-AutoGLM/blob/main/README.md)  
- Join Open-AutoGLM WeChat group (see official repo README)

---

⭐ If this project helps you, please give it a star!

---

📢 Disclaimer

This tool only automates Open-AutoGLM deployment; all core functions are provided by Open-AutoGLM. Obey local laws and use responsibly. Developers assume no liability for misuse.
