# 🛡️ Python Firewall Port Tester

[![Python 3.6+](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/release/python-360/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A lightweight, high-concurrency port scanner designed for network validation and firewall auditing.  
Built specifically for environments where **Python ≥ 3.6** is available.

---

## ✨ Key Features

- **Protocol Support**
  - `TCP`: Reliable connection attempts
  - `UDP`: Best-effort probing
- **Flexible Inputs**
  - Individual ports
  - Comma-separated lists
  - Port ranges (e.g. `30000-30010`)
- **IP Binding**
  - Use `--bind <source-ip>` to force traffic through a specific local interface
- **Reporting**
  - Export results directly to **CSV** or **JSON** for automated analysis
- **Legacy Ready**
  - Fully compatible with Python 3.6

---

## 🚀 Usage Examples

### For getting help
Help from command line
```bash
python3 firewall_port_tester_py36v1.py --help
```

### 1. Simple Port Scan
Test standard web and SSH ports on a single target:

```bash
python3 firewall_port_tester_py36.py \
  --targets 100.124.168.52 \
  --ports 22,443,6443 \
  --proto tcp
```
### 2. Bulk Scanning with JSON Output

Create a file named hosts.txt: \
100.124.168.52 \
10.10.1.10 \
abc.example.com

```bash
python3 firewall_port_tester_py36.py \
  --targets-file hosts.txt \
  --ports 22,53,30000-30010 \
  --proto both \
  --output results.json \
  --format json
```

### 3. Interface Binding
Force the scan to originate from a specific internal IP:

```bash
python3 firewall_port_tester_py36.py \
  --targets abc.example.com \
  --ports 2181,9092 \
  --bind 10.10.1.25 \
  --proto tcp
