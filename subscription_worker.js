export default {
  async fetch(request, env) {
    const asn = request.cf?.asn || 0;
    let carrier = "ALL";
    if (asn === 197207) {
      carrier = "MCI";
    } else if (asn === 44244) {
      carrier = "MTN";
    } else if (asn === 58224) {
      carrier = "TCI";
    }

    const rawNodes = (env && env.SUB_KV && await env.SUB_KV.get("ACTIVE_NODES")) || "[]";
    let nodes = [];
    try {
      nodes = JSON.parse(rawNodes);
    } catch (_) {
      nodes = [];
    }

    const matchedNodes = nodes.filter(
      (n) => n.carrier === carrier || n.carrier === "ALL" || carrier === "ALL"
    );

    const userAgent = (request.headers.get("User-Agent") || "").toLowerCase();
    if (userAgent.includes("sing-box") || userAgent.includes("clash")) {
      return new Response(JSON.stringify(matchedNodes, null, 2), {
        headers: {
          "content-type": "application/json; charset=utf-8",
          "x-detected-carrier": carrier
        }
      });
    }

    const uris = matchedNodes.map((n) => {
      const tag = encodeURIComponent(`V7L-${n.tag || 'Node'}-${carrier}`);
      if (n.public_key) {
        return `vless://${n.uuid}@${n.ip}:${n.port}?security=reality&flow=${n.flow || 'xtls-rprx-vision'}&sni=${n.sni}&fp=chrome&pbk=${n.public_key}&sid=${n.short_id}&type=tcp#${tag}`;
      }
      return `vless://${n.uuid}@${n.ip}:${n.port}?security=tls&sni=${n.sni}&type=ws&path=%2Fvless#${tag}`;
    });

    const base64Body = btoa(uris.join("\n"));
    return new Response(base64Body, {
      headers: {
        "content-type": "text/plain; charset=utf-8",
        "subscription-userinfo": "upload=0; download=0; total=1073741824000; expire=0",
        "profile-update-interval": "6",
        "x-detected-carrier": carrier
      }
    });
  }
};
