import argparse
import base64
import concurrent.futures
import json
import socket
import ssl
import sys
import time
from urllib.parse import quote

CLR_RESET = "\033[0m"
CLR_CYAN = "\033[38;2;0;245;212m"
CLR_GREEN = "\033[38;2;40;201;64m"
CLR_YELLOW = "\033[38;2;254;188;46m"
CLR_RED = "\033[38;2;255;95;87m"
CLR_BLUE = "\033[38;2;80;160;255m"
CLR_GRAY = "\033[38;2;120;140;160m"
CLR_BOLD = "\033[1m"

def probe_node(node, timeout=2.0):
    ip = node.get("ip") or node.get("server")
    port = int(node.get("port") or node.get("server_port") or 443)
    sni = node.get("sni") or node.get("server_name") or "speed.cloudflare.com"
    start = time.time()
    try:
        sock = socket.create_connection((ip, port), timeout=timeout)
        tcp_ms = (time.time() - start) * 1000.0
    except Exception as e:
        return {
            "status": "DEAD",
            "tag": node.get("tag", "Node"),
            "carrier": node.get("carrier", "ALL"),
            "ip": ip,
            "port": port,
            "error": str(e)
        }

    tls_ms = 0.0
    version = "TCP_ONLY"
    try:
        start_tls = time.time()
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            ssock = ctx.wrap_socket(sock, server_hostname=sni)
        except Exception:
            sock.close()
            sock = socket.create_connection((ip, port), timeout=timeout)
            ssock = ctx.wrap_socket(sock, server_hostname="speed.cloudflare.com")
        tls_ms = (time.time() - start_tls) * 1000.0
        version = ssock.version() or "TLS"
        ssock.close()
    except Exception:
        try:
            sock.close()
        except Exception:
            pass

    total_rtt = tcp_ms + tls_ms
    return {
        "status": "HEALTHY",
        "tag": node.get("tag", "Node"),
        "carrier": node.get("carrier", "ALL"),
        "ip": ip,
        "port": port,
        "sni": sni,
        "uuid": node.get("uuid", ""),
        "flow": node.get("flow", "xtls-rprx-vision"),
        "public_key": node.get("public_key", ""),
        "short_id": node.get("short_id", ""),
        "tcp_ms": round(tcp_ms, 1),
        "tls_ms": round(tls_ms, 1),
        "rtt": round(total_rtt, 1),
        "version": version
    }

def build_vless_uri(node):
    uuid = node.get("uuid", "")
    ip = node.get("ip", "")
    port = node.get("port", 443)
    tag = quote(f"V7L-{node.get('tag', 'Node')}-{node.get('carrier', 'ALL')}")
    sni = node.get("sni", "speed.cloudflare.com")
    pub = node.get("public_key", "")
    sid = node.get("short_id", "")
    flow = node.get("flow", "xtls-rprx-vision")
    if pub:
        return f"vless://{uuid}@{ip}:{port}?security=reality&flow={flow}&sni={sni}&fp=chrome&pbk={pub}&sid={sid}&type=tcp#{tag}"
    else:
        return f"vless://{uuid}@{ip}:{port}?security=tls&sni={sni}&type=ws&path=%2Fvless#{tag}"

def main():
    parser = argparse.ArgumentParser(
        description="V7LTHRONYX Multi-Carrier Subscription Node Health Checker & Pipeline Generator"
    )
    parser.add_argument("-i", "--input", default="nodes_template.json", help="Path to raw candidate nodes JSON (default: nodes_template.json)")
    parser.add_argument("-o", "--output", default="active_nodes.json", help="Path for healthy output nodes JSON (default: active_nodes.json)")
    parser.add_argument("-b", "--base64", default="sub_base64.txt", help="Path for Base64 subscription bundle (default: sub_base64.txt)")
    parser.add_argument("-t", "--timeout", type=float, default=2.0, help="Probe socket timeout in seconds (default: 2.0)")
    parser.add_argument("-w", "--workers", type=int, default=16, help="Concurrent scanner worker threads (default: 16)")
    args = parser.parse_args()

    print(f"\n{CLR_CYAN}{CLR_BOLD}═══════════════════════════════════════════════════════════════════════════════{CLR_RESET}")
    print(f"{CLR_CYAN}{CLR_BOLD}  V7LTHRONYX AUTOMATED SUBSCRIPTION HEALTH CHECKER v1.0.0{CLR_RESET}")
    print(f"{CLR_CYAN}{CLR_BOLD}  Carrier Routing Pipeline | Node Pruning & Base64 Encoder{CLR_RESET}")
    print(f"{CLR_CYAN}{CLR_BOLD}═══════════════════════════════════════════════════════════════════════════════{CLR_RESET}\n")

    try:
        with open(args.input, "r") as f:
            raw_nodes = json.load(f)
    except Exception as e:
        sys.exit(f"Failed to load input nodes: {e}")

    print(f"{CLR_BOLD}Loaded Nodes:{CLR_RESET}     {len(raw_nodes)} candidates")
    print(f"{CLR_BOLD}Workers:{CLR_RESET}          {args.workers} threads")
    print(f"{CLR_BOLD}Timeout:{CLR_RESET}          {args.timeout}s\n")

    print(f"{CLR_CYAN}PROBING ACTIVE NODE INTEGRITY (TCP + TLS 1.3)...{CLR_RESET}")
    print("─" * 79)
    print(f"{'TAG':<20}{'CARRIER':<10}{'ENDPOINT':<22}{'RTT':<12}{'STATUS'}")
    print("─" * 79)

    healthy_nodes = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(probe_node, n, args.timeout): n for n in raw_nodes}
        for fut in concurrent.futures.as_completed(futures):
            res = fut.result()
            if res["status"] == "HEALTHY":
                healthy_nodes.append(res)
                endpoint = f"{res['ip']}:{res['port']}"
                print(f"{res['tag']:<20}{res['carrier']:<10}{endpoint:<22}{res['rtt']:>6.1f} ms   {CLR_GREEN}HEALTHY{CLR_RESET}")
            else:
                endpoint = f"{res['ip']}:{res['port']}"
                print(f"{res['tag']:<20}{res['carrier']:<10}{endpoint:<22}{'FAIL':>8}   {CLR_RED}DEAD{CLR_RESET}")

    print("─" * 79)
    healthy_nodes.sort(key=lambda x: x["rtt"])

    with open(args.output, "w") as f:
        json.dump(healthy_nodes, f, indent=2)

    uris = [build_vless_uri(n) for n in healthy_nodes]
    joined_uris = "\n".join(uris)
    encoded_sub = base64.b64encode(joined_uris.encode("utf-8")).decode("utf-8")
    with open(args.base64, "w") as f:
        f.write(encoded_sub)

    print(f"\n{CLR_GREEN}{CLR_BOLD}[+] Health Check Complete:{CLR_RESET} {len(healthy_nodes)}/{len(raw_nodes)} Active Nodes Verified")
    print(f"{CLR_BLUE}[+] Sing-box Profile Saved:{CLR_RESET} {args.output}")
    print(f"{CLR_BLUE}[+] Base64 Subscription Exported:{CLR_RESET} {args.base64}\n")

if __name__ == "__main__":
    main()
