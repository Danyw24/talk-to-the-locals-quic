#!/usr/bin/env python3
import socket
import sys

MAGIC = b"give me the flag bro"

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", 6767))
print("[dumper] escuchando 127.0.0.1:6767/udp ...", flush=True)

while True:
    data, addr = sock.recvfrom(2048)
    hexdump = data.hex(" ", 2)
    first_line = data.split(b"\n")[0]
    won = first_line.rstrip(b"\n") == MAGIC
    print(f"\n[dumper] {len(data)} bytes desde {addr}", flush=True)
    for i in range(0, min(len(data), 96), 16):
        chunk = data[i : i + 16]
        hexs = " ".join(f"{b:02x}" for b in chunk)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print(f"  {i:04x}  {hexs:<47}  |{asc}|", flush=True)
    print(f"[dumper] primera línea: {first_line!r}", flush=True)
    if won:
        print("[dumper] *** WON *** la línea es EXACTA", flush=True)
