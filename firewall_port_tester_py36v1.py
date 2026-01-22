#!/usr/bin/env python3
"""
firewall_port_tester_py36v1.py
Author Murat Bilal
Global Customer Engineering (GCE) – Network Automation Practice (NAP)
Delivery & Operations
NOKIA Network Infrastructure

Python 3.6–compatible firewall port tester.
- TCP: attempts connects (reliable for "open").
- UDP: best-effort probe (no guaranteed "open/closed").
- Supports: port lists & ranges, concurrency, CSV/JSON output.
- Records source (local) and destination IPs.
- Bind <source-ip> to force the local interface used.

Examples:
  python3 firewall_port_tester_py36.py --targets 100.124.168.52 --ports 22,443,6443 --proto tcp
  python3 firewall_port_tester_py36.py --targets-file hosts.txt --ports 22,53,30000-30010 --proto both --output results.json --format json
  python3 firewall_port_tester_py36.py --targets vendor.example.com --ports 2181,9092 --bind 10.10.1.25 --proto tcp
"""

import argparse
import asyncio
import csv
import ipaddress
import json
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor

DEFAULT_CONCURRENCY = 200
DEFAULT_TIMEOUT = 3.0  # seconds

def parse_ports(portspec):
    out = []
    for part in [p.strip() for p in portspec.split(',') if p.strip()]:
        if '-' in part:
            a, b = part.split('-', 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    seen = set()
    uniq = [p for p in out if not (p in seen or seen.add(p))]
    return uniq

def resolve_host(host):
    try:
        return socket.gethostbyname(host)
    except Exception:
        return host

def local_ip_for_target(target):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((target, 53))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return 'unknown'

async def tcp_check(host, port, timeout, bind_ip=None):
    """Attempt TCP connect via a non-blocking socket + loop.sock_connect.
       Returns (src_ip, dst_ip, port, status, elapsed)."""
    start = time.time()
    dst_ip = resolve_host(host)
    rsock = None
    try:
        rsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        rsock.setblocking(False)
        if bind_ip:
            try:
                rsock.bind((bind_ip, 0))
            except Exception:
                pass
        loop = asyncio.get_event_loop()
        # Await the actual TCP connect to (dst_ip, port)
        await asyncio.wait_for(loop.sock_connect(rsock, (dst_ip, port)), timeout=timeout)
        try:
            src_ip = rsock.getsockname()[0]
        except Exception:
            src_ip = bind_ip or local_ip_for_target(dst_ip)
        elapsed = time.time() - start
        return src_ip, dst_ip, port, 'open', elapsed
    except asyncio.TimeoutError:
        return bind_ip or local_ip_for_target(dst_ip), dst_ip, port, 'timeout', time.time() - start
    except ConnectionRefusedError:
        return bind_ip or local_ip_for_target(dst_ip), dst_ip, port, 'closed', time.time() - start
    except OSError as e:
        return bind_ip or local_ip_for_target(dst_ip), dst_ip, port, 'error:{0}'.format(e), time.time() - start
    except Exception as e:
        return bind_ip or local_ip_for_target(dst_ip), dst_ip, port, 'error:{0}'.format(e), time.time() - start
    finally:
        if rsock is not None:
            try:
                rsock.close()
            except Exception:
                pass

def udp_probe_sync(host, port, timeout, bind_ip=None):
    start = time.time()
    dst_ip = resolve_host(host)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(timeout)
        if bind_ip:
            try:
                sock.bind((bind_ip, 0))
            except Exception:
                pass
        sock.connect((dst_ip, port))
        try:
            src_ip = sock.getsockname()[0]
        except Exception:
            src_ip = bind_ip or local_ip_for_target(dst_ip)
        sock.send(b'port-check\n')
        try:
            data = sock.recv(4096)
            status = 'open'
        except socket.timeout:
            status = 'no-response'  # filtered/closed/unknown
        except OSError as e:
            status = 'error:{0}'.format(e)
        return (src_ip, dst_ip, port, status, time.time() - start)
    finally:
        sock.close()

async def udp_check(host, port, timeout, executor, bind_ip=None):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, udp_probe_sync, host, port, timeout, bind_ip)

def expand_targets_from_file(path):
    out = []
    with open(path, 'r') as fh:
        for line in fh:
            s = line.split('#',1)[0].strip()
            if s:
                out.append(s)
    return out

def make_tasks(hosts, ports, proto):
    tasks = []
    for h in hosts:
        for p in ports:
            if proto in ('tcp','both'):
                tasks.append((h,p,'tcp'))
            if proto in ('udp','both'):
                tasks.append((h,p,'udp'))
    return tasks

async def worker(task_queue, results, timeout, executor, bind_ip=None):
    while True:
        try:
            host, port, prot = task_queue.get_nowait()
        except asyncio.QueueEmpty:
            return
        if prot == 'tcp':
            src_ip, dst_ip, prt, status, elapsed = await tcp_check(host, port, timeout, bind_ip=bind_ip)
        else:
            src_ip, dst_ip, prt, status, elapsed = await udp_check(host, port, timeout, executor, bind_ip=bind_ip)
        results.append({'src':src_ip, 'dst':dst_ip, 'port':prt, 'proto':prot, 'status':status, 'elapsed':round(elapsed,3)})
        task_queue.task_done()

async def run_checks(hosts, ports, proto, concurrency, timeout, bind_ip=None):
    tasks_tuples = make_tasks(hosts, ports, proto)
    q = asyncio.Queue()
    for t in tasks_tuples:
        await q.put(t)
    results = []
    executor = ThreadPoolExecutor(max_workers=100)
    workers = []
    for _ in range(min(concurrency, max(1, len(tasks_tuples)))):
        workers.append(asyncio.ensure_future(worker(q, results, timeout, executor, bind_ip=bind_ip)))
    await asyncio.gather(*workers)
    return results

def write_output(results, path, fmt):
    fieldnames = ['src','dst','port','proto','status','elapsed']
    if not path:
        if fmt == 'json':
            print(json.dumps(results, indent=2))
        else:
            w = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
            w.writeheader()
            for r in results:
                w.writerow(r)
        return
    if fmt == 'json':
        with open(path, 'w') as fh:
            json.dump(results, fh, indent=2)
    else:
        with open(path, 'w', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=fieldnames)
            w.writeheader()
            for r in results:
                w.writerow(r)

def validate_hosts(hosts):
    out = []
    for h in hosts:
        h = h.strip()
        if not h:
            continue
        try:
            ipaddress.ip_address(h)
            out.append(h)
        except ValueError:
            out.append(h)
    return out

def parse_args(argv=None):
    p = argparse.ArgumentParser(description='Firewall port tester (TCP + UDP). Python 3.6 compatible.')
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--targets', help='Comma separated hosts (IPs or hostnames)')
    g.add_argument('--targets-file', help='File with one host per line (comments with # allowed)')
    p.add_argument('--ports', required=True, help='Comma separated ports or ranges, e.g. 22,80,30000-30010')
    p.add_argument('--proto', choices=('tcp','udp','both'), default='tcp', help='Protocol to test')
    p.add_argument('--concurrency', type=int, default=200, help='Parallel connection attempts')
    p.add_argument('--timeout', type=float, default=3.0, help='Timeout seconds per port attempt')
    p.add_argument('--output', '-o', help='Output file (CSV or JSON by --format)')
    p.add_argument('--format', choices=('csv','json'), default='csv', help='Output format')
    p.add_argument('--bind', help='Source IP to bind for outgoing connections (forces NIC selection)')
    p.add_argument('--verbose', '-v', action='store_true', help='Verbose progress print')
    return p.parse_args(argv)

def main(argv=None):
    args = parse_args(argv)
    if args.targets:
        hosts = [h.strip() for h in args.targets.split(',') if h.strip()]

    else:
        hosts = expand_targets_from_file(args.targets_file)
    hosts = validate_hosts(hosts)
    ports = parse_ports(args.ports)
    if args.verbose:
        print('Target hosts: {0}'.format(hosts), file=sys.stderr)
        print('Ports parsed: {0} ports (first 10): {1}'.format(len(ports), ports[:10]), file=sys.stderr)
        print('Proto: {0}, concurrency: {1}, timeout: {2}, bind: {3}'.format(args.proto, args.concurrency, args.timeout, args.bind), file=sys.stderr)

    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(run_checks(hosts, ports, args.proto, args.concurrency, args.timeout, bind_ip=args.bind))
    write_output(results, args.output, args.format)

if __name__ == '__main__':
    main()
