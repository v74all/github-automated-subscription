import argparse
import base64
import json
import sys
import urllib.request
from urllib.parse import parse_qs, unquote, urlparse

CLR_RESET = "\033[0m"
CLR_CYAN = "\033[38;2;0;245;212m"
CLR_GREEN = "\033[38;2;40;201;64m"
CLR_YELLOW = "\033[38;2;254;188;46m"
CLR_RED = "\033[38;2;255;95;87m"
CLR_BLUE = "\033[38;2;80;160;255m"
CLR_GRAY = "\033[38;2;120;140;160m"
CLR_BOLD = "\033[1m"

def parse_vless_uri(uri):
    if not uri.startswith("vless://"):
        return None
    parsed = urlparse(uri)
    uuid = parsed.username
    ip = parsed.hostname
    port = parsed.port or 443
    params = parse_qs(parsed.query)
    tag = unquote(parsed.fragment) if parsed.fragment else f"Node-{ip}"
    return {
        "tag": tag,
        "ip": ip,
        "port": port,
        "uuid": uuid,
        "security": params.get("security", ["none"])[0],
        "sni": params.get("sni", [""])[0],
        "type": params.get("type", ["tcp"])[0],
        "pbk": params.get("pbk", [""])[0],
        "sid": params.get("sid", [""])[0],
        "flow": params.get("flow", [""])[0]
    }

def fetch_subscription(source):
    if source.startswith("http://") or source.startswith("https://"):
        req = urllib.request.Request(source, headers={"User-Agent": "v2rayNG/1.8.12"})
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            content = resp.read().decode("utf-8", errors="ignore").strip()
    else:
        with open(source, "r") as f:
            content = f.read().strip()

    try:
        decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
    except Exception:
        decoded = content

    nodes = []
    for line in decoded.splitlines():
        line = line.strip()
        if line.startswith("vless://"):
            node = parse_vless_uri(line)
            if node:
                nodes.append(node)
    return nodes

def generate_singbox_profile(nodes, out_path="singbox_subscribed.json"):
    outbounds = []
    tags = []
    for n in nodes:
        tag = n["tag"]
        tags.append(tag)
        ob = {
            "type": "vless",
            "tag": tag,
            "server": n["ip"],
            "server_port": n["port"],
            "uuid": n["uuid"]
        }
        if n["flow"]:
            ob["flow"] = n["flow"]
        tls_obj = {
            "enabled": True,
            "server_name": n["sni"],
            "utls": {"enabled": True, "fingerprint": "chrome"}
        }
        if n["security"] == "reality":
            tls_obj["reality"] = {
                "enabled": True,
                "public_key": n["pbk"],
                "short_id": n["sid"]
            }
        ob["tls"] = tls_obj
        if n["type"] == "ws":
            ob["transport"] = {"type": "ws", "path": "/vless", "headers": {"Host": n["sni"]}}
        outbounds.append(ob)

    profile = {
        "log": {"level": "info", "timestamp": True},
        "inbounds": [
            {"type": "mixed", "tag": "mixed-in", "listen": "127.0.0.1", "listen_port": 2080, "sniff": True}
        ],
        "outbounds": outbounds + [{"type": "direct", "tag": "direct"}, {"type": "block", "tag": "block"}],
        "route": {
            "rules": [
                {"geoip": "ir", "outbound": "direct"},
                {"geosite": "category-ir", "outbound": "direct"}
            ],
            "final": tags[0] if tags else "direct",
            "auto_detect_interface": True
        }
    }
    with open(out_path, "w") as f:
        json.dump(profile, f, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="V7LTHRONYX Dynamic Subscription Sync & Sing-box Config Converter"
    )
    parser.add_argument("-s", "--source", default="sub_base64.txt", help="Subscription URL or local base64 file (default: sub_base64.txt)")
    parser.add_argument("-o", "--output", default="singbox_subscribed.json", help="Generated Sing-box client JSON (default: singbox_subscribed.json)")
    args = parser.parse_args()

    print(f"\n{CLR_CYAN}{CLR_BOLD}═══════════════════════════════════════════════════════════════════════════════{CLR_RESET}")
    print(f"{CLR_CYAN}{CLR_BOLD}  V7LTHRONYX CLIENT SUBSCRIPTION DECODER & SYNC TOOL v1.0.0{CLR_RESET}")
    print(f"{CLR_CYAN}{CLR_BOLD}  Carrier Routing Intake | Sing-box Automated Exporter{CLR_RESET}")
    print(f"{CLR_CYAN}{CLR_BOLD}═══════════════════════════════════════════════════════════════════════════════{CLR_RESET}\n")

    nodes = fetch_subscription(args.source)
    print(f"{CLR_BOLD}Subscription Source:{CLR_RESET}  {args.source}")
    print(f"{CLR_BOLD}Discovered Nodes:{CLR_RESET}     {len(nodes)} valid configurations\n")

    print(f"{'NODE TAG':<30}{'SERVER':<18}{'PORT':<8}{'SECURITY':<14}{'TRANSPORT'}")
    print("─" * 79)
    for n in nodes:
        print(f"{n['tag']:<30}{n['ip']:<18}{n['port']:<8}{n['security']:<14}{n['type']}")
    print("─" * 79)

    generate_singbox_profile(nodes, args.output)
    print(f"\n{CLR_GREEN}{CLR_BOLD}[+] Sing-box Client Profile Updated:{CLR_RESET} {args.output}\n")

if __name__ == "__main__":
    main()
