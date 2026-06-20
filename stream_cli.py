#!/usr/bin/env python3
"""
BatesAI — Real-time streaming (Yahoo WebSocket)

True push-based streaming quotes with no API key. Connects to Yahoo's public
streamer, subscribes to the given symbols, decodes the protobuf "PricingData"
frames, and emits one JSON line per tick on stdout (line-buffered) so a native
front-end can read a live stream:

    stream_cli.py AAPL NVDA BTC-USD
    -> {"ticker": "BTC-USD", "price": 102345.1, "change": 812.4, "changePercent": 0.8}

Stocks stream during market hours; crypto (e.g. BTC-USD) streams 24/7.
"""

from __future__ import annotations

import base64
import json
import ssl
import struct
import sys
import time

try:
    import websocket  # websocket-client
except Exception:  # pragma: no cover
    websocket = None


def _decode_pricing(data: bytes) -> dict:
    """Minimal protobuf decode of Yahoo's PricingData frame.

    Fields we use: 1=id(str), 2=price(f32), 8=changePercent(f32), 12=change(f32).
    All other fields are skipped by wire type so unknown fields never break us.
    """
    out: dict = {}
    i, n = 0, len(data)
    while i < n:
        tag = data[i]; i += 1
        field = tag >> 3
        wt = tag & 7
        if wt == 0:  # varint
            shift = 0
            while i < n:
                b = data[i]; i += 1
                if not (b & 0x80):
                    break
                shift += 7
        elif wt == 1:  # 64-bit
            i += 8
        elif wt == 2:  # length-delimited
            ln = data[i]; i += 1
            val = data[i:i + ln]; i += ln
            if field == 1:
                out["id"] = val.decode("utf-8", "ignore")
        elif wt == 5:  # 32-bit float
            if i + 4 <= n:
                f = struct.unpack("<f", data[i:i + 4])[0]
                i += 4
                if field == 2:
                    out["price"] = f
                elif field == 8:
                    out["changePercent"] = f
                elif field == 12:
                    out["change"] = f
            else:
                break
        else:
            break
    return out


def stream(symbols: list):
    if websocket is None:
        print(json.dumps({"error": "websocket-client unavailable"}), flush=True)
        return

    def on_open(ws):
        ws.send(json.dumps({"subscribe": symbols}))

    def on_message(ws, message):
        try:
            d = _decode_pricing(base64.b64decode(message))
            if d.get("id") and "price" in d:
                print(json.dumps({
                    "ticker": d["id"],
                    "price": round(float(d["price"]), 4),
                    "change": round(float(d.get("change", 0.0)), 4),
                    "changePercent": round(float(d.get("changePercent", 0.0)), 4),
                }), flush=True)
        except Exception:
            pass

    # Reconnect loop so the stream survives transient drops.
    while True:
        try:
            ws = websocket.WebSocketApp(
                "wss://streamer.finance.yahoo.com/",
                on_open=on_open, on_message=on_message)
            ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE},
                           ping_interval=20, ping_timeout=10)
        except Exception:
            pass
        time.sleep(3)  # backoff before reconnect


if __name__ == "__main__":
    syms = [s.upper() for s in sys.argv[1:]] or ["SPY", "BTC-USD"]
    stream(syms)
