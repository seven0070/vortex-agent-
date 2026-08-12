"""Steganography + conlang tools (Vortex heritage)."""
from __future__ import annotations

import hashlib
import random

from .registry import registry


def glossopetrae(text: str, seed: int = 42, render_svg: bool = True) -> dict:
    random.seed(int(seed or 42))
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    shuffled = list(alphabet)
    random.shuffle(shuffled)
    cipher = dict(zip(alphabet, shuffled))
    translated = "".join(cipher.get(c, c) for c in (text or "").lower())
    svg = ""
    if render_svg:
        safe = (
            translated.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="420" height="60">'
            '<rect width="420" height="60" fill="#0a0a0a"/>'
            f'<text x="12" y="36" font-family="monospace" font-size="16" '
            f'fill="#f97316">{safe}</text></svg>'
        )
    return {
        "status": "success",
        "message": f"Translated with seed {seed}.",
        "data": {"translated": translated, "seed": seed, "svg": svg},
    }


def steganography(
    action: str,
    cover: str = "",
    payload: str = "",
    stego: str = "",
    method: str = "marker",
    context: dict = None,
) -> dict:
    ctx = context or {}
    memory = ctx.get("memory")

    if action == "encode":
        if not payload:
            return {"status": "error", "error": "payload required", "data": {}}
        cover = cover or "The weather is quite pleasant today."
        if method == "marker":
            tag = hashlib.md5(payload.encode()).hexdigest()[:12]
            encoded = f"{cover}\n<!--STEGO:{tag}-->{payload}<!--/STEGO-->"
        else:
            bits = "".join(f"{ord(c):08b}" for c in payload)
            zw = "".join("\u200b" if b == "0" else "\u200c" for b in bits)
            encoded = f"{cover}{zw}"
        if memory is not None:
            try:
                memory.set_kv("last_stego", encoded)
            except Exception:
                pass
        return {
            "status": "success",
            "message": f"Payload hidden via {method}.",
            "data": {"encoded": encoded, "method": method},
        }

    if action == "decode":
        stego = stego or (memory.get_kv("last_stego") if memory else "") or ""
        if not stego:
            return {"status": "error", "error": "stego text required", "data": {}}
        if "<!--STEGO:" in stego:
            try:
                decoded = (
                    stego.split("<!--STEGO:")[1].split("-->")[1].split("<!--/STEGO-->")[0]
                )
                return {
                    "status": "success",
                    "message": "Payload extracted (marker).",
                    "data": {"decoded": decoded},
                }
            except IndexError:
                return {"status": "error", "error": "Malformed marker payload.", "data": {}}
        bits = "".join(
            "0" if c == "\u200b" else "1" if c == "\u200c" else "" for c in stego
        )
        if bits and len(bits) >= 8:
            chars = [chr(int(bits[i : i + 8], 2)) for i in range(0, len(bits) - 7, 8)]
            return {
                "status": "success",
                "message": "Payload extracted (unicode zw).",
                "data": {"decoded": "".join(chars)},
            }
        return {"status": "error", "error": "No hidden payload detected.", "data": {}}

    return {"status": "error", "error": f"Invalid action: {action}", "data": {}}


registry.register(
    "glossopetrae",
    "Translate text into a procedurally generated conlang (+ optional SVG).",
    {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "seed": {"type": "integer", "default": 42},
            "render_svg": {"type": "boolean", "default": True},
        },
        "required": ["text"],
    },
    glossopetrae,
    toolsets=["crypto", "security"],
)

registry.register(
    "steganography",
    "Encode/decode a secret payload inside cover text.",
    {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["encode", "decode"]},
            "cover": {"type": "string"},
            "payload": {"type": "string"},
            "stego": {"type": "string"},
            "method": {"type": "string", "enum": ["marker", "whitespace", "unicode"], "default": "marker"},
        },
        "required": ["action"],
    },
    steganography,
    toolsets=["crypto", "security"],
)
