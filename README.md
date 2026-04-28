# 🤖 Network AI Monitor v2

A real-time network anomaly detection and auto-remediation system using Machine Learning + Discord Bot, connected to Cisco Routers via GNS3. Built as my final year project.

---

## 📌 Project Overview

```
Cisco Routers (GNS3)
        ↓  Netmiko / Telnet
collector.py  →  MySQL Database
        ↓
predictor.py  →  Random Forest AI Model
        ↓
bot.py  →  Discord Bot (Alert + Auto-Fix)
```

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Network Simulation | GNS3 + VMware |
| Router | Cisco IOS (4 Routers) |
| Routing Protocol | OSPF |
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
├── main.py               # Entry point — runs collector + bot together
├── collector.py          # Collects interface data from all routers
├── predictor.py          # AI prediction + anomaly analysis
├── bot.py                # Discord Bot — alerts + buttons
├── db.py                 # Database operations
├── train_model.py        # Train the AI model
├── devices.yaml          # Router config (add new routers here)
├── config.yaml           # System config (thresholds, DB, Discord)
└── anomaly_model_v2.pkl  # Trained AI model
```

---

## 🌐 Network Topology

Mid-scale enterprise network with 4 routers, 2 switches, and 6 PCs — fully meshed with redundant paths.

```
PC1, PC2, PC3
      ↓
   Switch1 (192.168.1.x)
      ↓
     R2 (192.168.189.10) ←→ R1 ←→ R3 ←→ R4 (192.168.189.20)
                                              ↓
                                          Switch2 (192.168.2.x)
                                              ↓
                                     PC4, PC5, PC6
```

| Device | Management IP | Role |
|---|---|---|
| R1 | 10.10.100.1 (Loopback) | Core Router |
| R2 | 192.168.189.10 | Core + DHCP + NAT |
| R3 | 10.10.100.3 (Loopback) | Core Router |
| R4 | 192.168.189.20 | Core + DHCP + NAT |

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

Edit `config.yaml`:
```yaml
database:
  url: "mysql+mysqlconnector://root:@localhost/network_ai_v2"

model:
  path: "anomaly_model_v2.pkl"
  threshold_load: 20
  threshold_reliability: 200
  threshold_errors: 10

collector:
  interval: 10

discord:
  token: "YOUR_BOT_TOKEN"
  channel_id: YOUR_CHANNEL_ID
```

Edit `devices.yaml` — add new routers here without touching code:
```yaml
devices:
  - name: R1
    host: 10.10.100.1
    device_type: cisco_ios_telnet
    username: admin
    password: admin123
    secret: admin123
    location: Core
    zone: A
  # Add more routers here...
```

---

## 🚀 How to Use

### Step 1 — Run the System

```bash
python main.py
```

This starts everything at once — data collection, AI prediction, and Discord Bot.

### Step 2 — Train the AI Model

```bash
python train_model.py
```

Expected output:
```
✅ Loaded data: 3816 rows
📈 Classification Report:
              precision    recall  f1-score
     anomaly       1.00      1.00      1.00
      normal       1.00      1.00      1.00
    accuracy                           1.00
⭐ Feature Importance:
network_load    0.225
input_errors    0.199
reliability     0.196
rxload          0.196
protocol_num    0.183
```

---

## 🤖 AI Model Details

| Detail | Value |
|---|---|
| Algorithm | Random Forest |
| Number of Trees | 100 |
| Training Data | 3,052 rows |
| Test Data | 764 rows |
| Accuracy | 100% |
| Features Used | 6 features |

### Features Used for Training

| Feature | Description | Importance |
|---|---|---|
| network_load | Outbound traffic (0-255) | 22.5% |
| input_errors | Error count | 19.9% |
| reliability | Link stability (0-255) | 19.6% |
| rxload | Inbound traffic (0-255) | 19.6% |
| protocol_num | Protocol up/down | 18.3% |
| status_num | Port up/down | 0% |

### Anomaly Rules

| Condition | Label |
|---|---|
| protocol = down | anomaly |
| status = admin_down | anomaly |
| network_load > threshold | anomaly |
| rxload > threshold | anomaly |
| reliability < threshold | anomaly |
| input_errors > threshold | anomaly |

---

## 🔔 Discord Bot Commands

| Command | Description |
|---|---|
| `!status` | Show current status of all interfaces |
| `!history` | Show last 10 anomaly records |
| `!analytics` | Full analytics — anomaly summary, uptime, fix rate, traffic trend |
| `!help` | Show all available commands |

### Anomaly Alert Buttons

When an anomaly is detected, the bot sends an alert with action buttons:

| Button | Action |
|---|---|
| 🔧 Fix Now | Runs `no shutdown` automatically on the affected interface |
| 📊 Check Status | Shows live interface status via `show interface` |
| 🚦 Rate Limit | Applies 50Mbps rate limit for high traffic |
| 🔓 Remove Limit | Removes rate limit after traffic normalizes |
| ❌ Ignore | Dismisses the alert |

---

## 📊 Analytics Dashboard (!analytics)

- **Overview** — Total records, anomaly count, fix rate, today's anomalies
- **Device Uptime** — Uptime % per device (🟢 ≥99% / 🟡 ≥95% / 🔴 <95%)
- **Top Problem Devices & Interfaces** — Ranked by anomaly count
- **Traffic Trend** — Avg/max load per hour (last 6 hours)
- **Anomaly by Type** — High Traffic / Admin Down / Protocol Down breakdown

---

## 🔧 Customization

### Add a New Router

Just add one entry in `devices.yaml` — no code changes needed:

```yaml
- name: R5
  host: 192.168.189.30
  device_type: cisco_ios_telnet
  username: admin
  password: admin123
  secret: admin123
  location: Core
  zone: C
```

### Change Monitoring Interval

```yaml
collector:
  interval: 10  # seconds
```

---

## 📈 Future Improvements

- [ ] Web Dashboard (Flask + Chart.js)
- [ ] SSH support instead of Telnet
- [ ] SNMP polling for deeper metrics
- [ ] Email / Line notification
- [ ] Support for larger topologies (EVE-NG)

---

## 👨‍💻 About

Built as a final year project exploring the intersection of AI and Network Automation. The goal was to create a practical system that can monitor, detect, and auto-remediate network issues in real time.

---

## 📄 License

MIT License
