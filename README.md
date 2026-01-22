Python 3.6–compatible firewall port tester.
- TCP: attempts connects (reliable for "open").
- UDP: best-effort probe (no guaranteed "open/closed").
- Supports: port lists & ranges, concurrency, CSV/JSON output.
- Records source (local) and destination IPs.
- Bind <source-ip> to force the local interface used.
- Compatible with Python

Examples:
  python3 firewall_port_tester_py36.py --targets 100.124.168.52 --ports 22,443,6443 --proto tcp
  python3 firewall_port_tester_py36.py --targets-file hosts.txt --ports 22,53,30000-30010 --proto both --output results.json --format json
  python3 firewall_port_tester_py36.py --targets vendor.example.com --ports 2181,9092 --bind 10.10.1.25 --proto tcp
