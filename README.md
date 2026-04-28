# 🤖 Network AI Monitor v2

A real-time network anomaly detection and **auto-remediation** system using Machine Learning + Discord ChatOps Bot, connected to Cisco Routers via GNS3.

> Built  — exploring how AI and Network Automation can work together to detect and fix network issues automatically, without human intervention.

---

## 📌 Project Overview

```
Cisco Routers (GNS3)
        ↓  Netmiko / Telnet (every 10 seconds)
collector.py  ──→  MySQL Database
        ↓
predictor.py  ──→  Random Forest AI Model
        ↓
bot.py  ──→  Discord Bot
              ├── 🚨 Real-time Anomaly Alert
              ├── 🔧 Fix Now (auto no shutdown)
              ├── 🚦 Rate Limit (auto bandwidth limit)
              ├── 📊 Check Status (live show interface)
              └── 📈 !analytics (network dashboard)
```

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Network Simulation | GNS3 + VMware |
| Router | Cisco IOS (4 Routers) |
| Routing Protocol | OSPF (full mesh) |
| Data Collection | Python + Netmiko |
| Database | MySQL |
| Machine Learning | scikit-learn (Random Forest) |
| DB Connection | SQLAlchemy |
| Config Management | YAML |
| ChatOps | Discord.py |

---

## 📁 Project Structure

```
network-ai-v2/
├── main.py               # Entry point — starts collector + Discord Bot together
├── collector.py          # Connects to routers, collects interface metrics every 10s
├── predictor.py          # AI inference + root cause analysis
├── bot.py                # Discord Bot — alerts, buttons, commands
├── db.py                 # All database queries (logs, predictions, analytics)
├── train_model.py        # Train / retrain the AI model
├── devices.yaml          # Router list — add new routers here (no code changes)
├── config.yaml           # Thresholds, DB URL, Discord token
├── config_example.yaml   # Example config (safe to share)
├── devices_example.yaml  # Example devices (safe to share)
└── anomaly_model_v2.pkl  # Trained Random Forest model
```

---

## 🌐 Network Topology
<img width="1397" height="542" alt="image" src="https://github.com/user-attachments/assets/016d0f81-4e64-424b-ba1a-6ff163886cee" />

Mid-scale enterprise network with **4 Cisco Routers**, **2 Switches**, **6 PCs**, full-mesh OSPF routing, DHCP, and NAT.

```
[PC1] [PC2] [PC3]
       ↓
   [Switch1]  192.168.1.0/24
       ↓
      [R2] ←──────────────────────────────→ [R4]
   192.168.189.10                        192.168.189.20
       ↑                                      ↑
       └───── [R1] ←──── OSPF ────→ [R3] ─────┘
           10.10.100.1           10.10.100.3
                                      ↓
                                  [Switch2]  192.168.2.0/24
                                      ↓
                               [PC4] [PC5] [PC6]
```

| Device | Management IP | Role |
|---|---|---|
| R1 | 10.10.100.1 (Loopback) | Core Router — OSPF |
| R2 | 192.168.189.10 | Core + DHCP (LAN Left) + NAT |
| R3 | 10.10.100.3 (Loopback) | Core Router — OSPF |
| R4 | 192.168.189.20 | Core + DHCP (LAN Right) + NAT |

**Python connects to all 4 routers via Cloud1 (Management Network 192.168.189.0/24)**

---

## ⚙️ Installation

### 1. Install Python Libraries

```bash
pip install netmiko sqlalchemy mysql-connector-python pyyaml scikit-learn pandas joblib discord.py
```

### 2. Create Database

```sql
CREATE DATABASE network_ai_v2;
```

### 3. Configure Files

Copy example files and fill in your values:

```bash
cp config_example.yaml config.yaml
cp devices_example.yaml devices.yaml
```

`config.yaml`:
```yaml
database:
  url: "mysql+mysqlconnector://root:@localhost/network_ai_v2"

model:
  path: "anomaly_model_v2.pkl"
  threshold_load: 20        # 0-255 scale (20 ≈ 8% load)
  threshold_reliability: 200
  threshold_errors: 10

collector:
  interval: 10              # collect every 10 seconds

discord:
  token: "YOUR_BOT_TOKEN_HERE"
  channel_id: YOUR_CHANNEL_ID_HERE
```

`devices.yaml` — add any number of routers here:
```yaml
devices:
  - name: R1
    host: 10.10.100.1
    device_type: cisco_ios_telnet
    username: admin
    password: your_password
    secret: your_secret
    location: Core
    zone: A
```

---

## 🚀 How to Use

### Step 1 — Train the AI Model (first time only)

```bash
python train_model.py
```

### Step 2 — Run the System

```bash
python main.py
```

This starts **everything at once**:
- Connects to all routers every 10 seconds
- Runs AI prediction on every interface
- Discord Bot goes online and starts monitoring

---

## 🤖 AI Model Details

| Detail | Value |
|---|---|
| Algorithm | Random Forest Classifier |
| Number of Trees | 100 |
| Training Data | 3,052 rows |
| Test Data | 764 rows |
| Accuracy | 100% |
| Features Used | 6 features |

### Features Used for Training

| Feature | Description | Importance |
|---|---|---|
| network_load | TX traffic load (0-255) | 22.5% |
| input_errors | Cumulative input errors | 19.9% |
| reliability | Link stability score (0-255) | 19.6% |
| rxload | RX traffic load (0-255) | 19.6% |
| protocol_num | Line protocol up=1 / down=0 | 18.3% |
| status_num | Physical status up=1 / down=0 | 0% |

### Anomaly Classification Rules

| Condition | Type | Label |
|---|---|---|
| status = admin_down | Port shutdown by admin | anomaly |
| protocol = down (status = up) | Link down / cable issue | anomaly |
| network_load > threshold | High outbound traffic | anomaly |
| rxload > threshold | High inbound traffic | anomaly |
| reliability < threshold | Unstable link | anomaly |
| input_errors > threshold | Physical errors | anomaly |
| All conditions normal | Everything OK | normal |

---

## 🔔 Discord Bot — Commands

| Command | Description |
|---|---|
| `!status` | Show real-time status of every interface across all routers |
| `!history` | Show last 10 anomaly events with timestamps and fix status |
| `!analytics` | Full network analytics dashboard (5 embed panels) |
| `!help` | Show all available commands |

---

## 🚨 Anomaly Alert — What It Looks Like



When the AI detects an anomaly, Discord sends an alert embed with:

```
🚨 ANOMALY DETECTED!
Device    : R1
Interface : FastEthernet0/1 (10.10.2.1)
Link Type : Core
Confidence: 100%

Status    : admin_down    Protocol  : down
TX Load   : 1/255 (0.4%)  RX Load   : 1/255 (0.4%)
Reliability: 255/255

🔎 สาเหตุ:
• Port ถูกปิดด้วยคำสั่ง shutdown

💡 คำแนะนำ:
• no shutdown บน FastEthernet0/1

[ 🔧 Fix Now ]  [ 📊 Check Status ]  [ 🚦 Rate Limit ]  [ 🔓 Remove Limit ]  [ ❌ Ignore ]
```

---

## 🔧 Anomaly Alert Buttons — What Each Button Does

### 🔧 Fix Now
**Use case:** Interface is `admin_down` or `protocol down`

**What it does:**
- Python connects to the affected router via Netmiko
- Runs `interface <intf>` → `no shutdown` automatically
- Reports the full CLI output back to Discord
- Marks the anomaly as **Fixed** in the database

```
R1(config)#interface FastEthernet0/1
R1(config-if)#no shutdown
```

> After clicking, the button turns grey and shows "✅ Fix สำเร็จ!" with the result
<img width="780" height="524" alt="image" src="https://github.com/user-attachments/assets/d34d1d3d-7b1d-4a2f-9bb7-959a5ff44573" />


---

### 📊 Check Status
<img width="764" height="808" alt="image" src="https://github.com/user-attachments/assets/6cc68b13-e360-4c5b-bc80-bfbf39f12477" />

**Use case:** Want to see the live interface state without fixing anything

**What it does:**
- Runs `show interface <intf>` on the router in real-time
- Returns the full output directly to Discord (truncated to 500 chars)
- Useful to verify if the problem is still active or already resolved

---

### 🚦 Rate Limit


**Use case:** Interface has abnormally high TX/RX traffic (possible flood or DDoS)

**What it does:**
- Applies rate-limit policy on the interface to cap bandwidth at **50 Mbps**
- Runs these commands automatically:

```
interface <intf>
rate-limit input  50000000 8000 8000 conform-action transmit exceed-action drop
rate-limit output 50000000 8000 8000 conform-action transmit exceed-action drop
```

> ⚠️ This is a temporary measure. You should still investigate the root cause.

---

### 🔓 Remove Limit
**Use case:** Traffic has returned to normal and you want to remove the rate limit

**What it does:**
- Removes the rate-limit policy that was applied
- Interface returns to its original bandwidth capacity

```
interface <intf>
no rate-limit input  50000000 ...
no rate-limit output 50000000 ...
```

---

### ❌ Ignore
**Use case:** The alert is a known false positive or expected maintenance

**What it does:**
- Dismisses the alert message
- Disables all buttons on that alert
- Does **not** make any changes to the router

---

## 📊 !analytics — Network Dashboard

The `!analytics` command sends **5 embed panels** to Discord:
<img width="841" height="629" alt="image" src="https://github.com/user-attachments/assets/b8469cd4-0c75-4ca9-a0e8-5100f4cc14ee" />
<img width="767" height="609" alt="image" src="https://github.com/user-attachments/assets/b62aa594-df7c-40b3-a2b3-551b320673ef" />


### Panel 1 — Overview
| Field | Description |
|---|---|
| Total Records | Total interface log entries collected |
| Total Anomaly | Number of anomalies detected (with %) |
| Total Normal | Number of normal readings |
| Anomaly Today | Anomalies detected today |
| Fix Rate | % of anomalies that were fixed via bot |

### Panel 2 — Device Uptime
Shows uptime % per device based on ratio of normal vs total readings.
- 🟢 ≥ 99% — Excellent
- 🟡 ≥ 95% — Warning
- 🔴 < 95% — Critical

### Panel 3 — Top Problem Devices & Interfaces
Ranks devices and interfaces by total anomaly count — helps identify recurring problem spots.

### Panel 4 — Traffic Trend (Last 6 Hours)
Shows average and max TX load per hour.
- 🟢 Load < 20% — Normal
- 🟡 Load 20-50% — Elevated
- 🔴 Load > 50% — High

### Panel 5 — Anomaly by Type
Breakdown of what caused anomalies:
- 🟡 High Traffic — TX/RX load exceeded threshold
- 🔴 Admin Down — Interface was shut down
- 🟠 Protocol Down — Link protocol failed

---

## 🚨 Scenario Examples

### Scenario 1 — Router Interface Shutdown

**What happens in the network:**
```
R1(config-if)# shutdown
→ FastEthernet0/1 goes admin_down
→ Protocol also goes down

```

**What the system does:**
1. Python detects `status=admin_down` within 10 seconds
2. AI classifies as **anomaly** (confidence 100%)
3. Discord sends alert with cause: "Port ถูกปิดด้วยคำสั่ง shutdown"
4. Admin clicks **🔧 Fix Now**
5. Python runs `no shutdown` automatically
6. Interface comes back up within seconds
7. Next collection cycle confirms recovery → `!status` shows ✅

<img width="850" height="485" alt="image" src="https://github.com/user-attachments/assets/0faa062d-0018-40e2-9b35-f1283b47a897" />
---

### Scenario 2 — High Traffic (Flood / DDoS)

**What happens in the network:**
```
R1# ping 192.168.2.1 repeat 9999999 size 1500
→ TX/RX load climbs above threshold
```

**What the system does:**
1. Python detects `network_load > threshold` or `rxload > threshold`
2. AI classifies as **anomaly**
3. Discord sends alert with cause: "Traffic ขาออก/ขาเข้าสูงผิดปกติ (XX%)"
4. Admin clicks **🚦 Rate Limit** to cap bandwidth at 50Mbps
5. After traffic normalizes, admin clicks **🔓 Remove Limit**
<img width="842" height="513" alt="image" src="https://github.com/user-attachments/assets/18075341-de2a-47a6-a920-b99b81d16bb7" />
---

### Scenario 3 — Device Timeout (Router unreachable)

**What happens:**
- Router cannot be reached (GNS3 cloud disconnects, router crashes, etc.)

**What the system does:**
1. Python retries 3 times (5 second delay each)
2. After all retries fail, Discord sends a **⚠️ Device Timeout!** alert with:
   - Device name and host IP
   - Zone information
   - Error message
3. Admin knows to check the router manually
<img width="644" height="483" alt="image" src="https://github.com/user-attachments/assets/72b5e862-bfc2-4fa7-8bd4-94d9cc758f2f" />


---

## 🔧 Customization

### Add a New Router (Zero Code Changes)

Add one entry in `devices.yaml`:
```yaml
- name: R5
  host: 192.168.189.30
  device_type: cisco_ios_telnet
  username: admin
  password: your_password
  secret: your_secret
  location: Branch
  zone: C
```

Restart `python main.py` — R5 is now monitored automatically.

### Change Anomaly Sensitivity

```yaml
model:
  threshold_load: 191   # 75% = production standard
  threshold_load: 20    # 8%  = sensitive (lab environment)
```

### Change Collection Interval

```yaml
collector:
  interval: 10   # seconds — lower = more data, higher CPU usage
```

---

## 📈 Future Improvements

- [ ] Web Dashboard (Flask + Chart.js) — visual real-time graphs
- [ ] SSH support instead of Telnet — production security
- [ ] SNMP polling — CPU, memory, temperature metrics
- [ ] Line / Email notification — multi-channel alerting
- [ ] Alert cooldown — prevent duplicate alerts for same issue
- [ ] EVE-NG support — larger and more realistic topology simulation
- [ ] Predictive maintenance — predict failures before they happen

---

## 👨‍💻 About

Built exploring how **AI and Network Automation** can work together. Instead of waiting for users to report problems, this system detects anomalies proactively and fixes them automatically through Discord.

The architecture is designed to scale — adding new routers requires no code changes, just a single entry in `devices.yaml`.

---

