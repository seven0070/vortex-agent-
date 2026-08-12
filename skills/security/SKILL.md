---
name: security
description: Steganography encode/decode and conlang obfuscation
tags: stego, crypto, obfuscation
source: bundled
---

# Security skill

## Hide a secret
- Tool: `steganography` with `action=encode`
- Extract payload from quotes when present (`'secret'` / `"secret"`)
- Cover text defaults to a benign sentence if omitted
- Prefer `method=marker` unless asked otherwise

## Reveal a secret
- Tool: `steganography` with `action=decode`
- Pass stego text, or rely on last encoded payload in session kv

## Obfuscate / conlang
- Tool: `glossopetrae` with the source text
