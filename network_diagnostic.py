#!/usr/bin/env python3
import socket, sys, subprocess, time, os
from urllib.parse import urlparse
DEFAULT_HOST = "db.supabase.co"
DEFAULT_PORT = 6543
TIMEOUT = 5
COMMON_PORTS = [80, 443, 5432, 6543, 22, 53, 8080, 3306]

def p(t): print(f"\n{'='*60}\n {t}\n{'='*60}")
def info(t): print(f"  ℹ️  {t}")
def ok(t): print(f"  ✅ {t}")
def warn(t): print(f"  ⚠️  {t}")
def err(t): print(f"  ❌ {t}")

def resolve(host, port):
    p(f"1. Resolución DNS de {host}:{port}")
    try:
        addrs = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        ipv4, ipv6 = [], []
        for a in addrs:
            if a[0] == socket.AF_INET: ipv4.append(a[4][0])
            elif a[0] == socket.AF_INET6: ipv6.append(a[4][0])
        if ipv4: ok(f"IPv4: {', '.join(ipv4)}")
        else: warn("No IPv4")
        if ipv6: ok(f"IPv6: {', '.join(ipv6)}")
        else: warn("No IPv6")
        return ipv4 + ipv6
    except Exception as e:
        err(f"DNS error: {e}")
        return []

def test_tcp(host, port):
    p(f"2. Conexión TCP a {host}:{port}")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(TIMEOUT)
        s.connect((host, port))
        s.close()
        ok("Conexión exitosa")
        return True
    except socket.timeout: err("Timeout")
    except ConnectionRefusedError: err("Rechazada")
    except Exception as e: err(f"Error: {e}")
    return False

def traceroute(host):
    p(f"3. Traceroute hacia {host}")
    cmd = ["traceroute", "-n", "-m", "30", host] if not sys.platform.startswith("win") else ["tracert", "-d", "-h", "30", host]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode == 0: print(r.stdout)
        else: warn(f"Falló: {r.stderr}")
    except FileNotFoundError: err("traceroute no instalado")
    except Exception as e: err(f"Error: {e}")

def scan_local():
    p("4. Escaneo de puertos locales")
    open_ports = []
    for p in COMMON_PORTS:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            if s.connect_ex(('127.0.0.1', p)) == 0: open_ports.append(p)
            s.close()
        except: pass
    if open_ports: ok(f"Abiertos: {', '.join(map(str, open_ports))}")
    else: warn("Ningún puerto local abierto")
    warn("Supabase usa 6543. Si no está abierto, revisa firewall.")

def main():
    if len(sys.argv) > 1:
        parsed = urlparse(sys.argv[1])
        host = parsed.hostname or DEFAULT_HOST
        port = parsed.port or DEFAULT_PORT
    else:
        host, port = DEFAULT_HOST, DEFAULT_PORT
    p(f"🔍 Diagnóstico para {host}:{port}")
    ips = resolve(host, port)
    if not ips:
        err("No se pudo resolver. Revisa DNS.")
        sys.exit(1)
    target = ips[0]
    tcp_ok = test_tcp(target, port)
    traceroute(target)
    scan_local()
    if tcp_ok: ok("✅ Conexión TCP exitosa. Si falla la app, revisa credenciales.")
    else: err("❌ Conexión fallida. Revisa firewall corporativo o ISP.")

if __name__ == "__main__": main()
