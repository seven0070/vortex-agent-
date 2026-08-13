# assets

## blackhole.png — NOT YET ADDED

The root `README.md` embeds `assets/blackhole.png` as its banner, but **the image file
is not in this repo yet**. The banner will render as a broken image until you add it.

To fix:

```bash
cp /path/to/blackhole.png assets/blackhole.png
git add assets/blackhole.png
git commit -m "Add README banner image"
git push origin arena/019ffb85-vortex-agent
```

Expected: a wide (roughly 3:2) image — the banner renders full-width at the top of the README.

### A note on binaries in Git

Images are stored in history permanently and cannot be shrunk later without rewriting
history. One banner is fine. If this repo starts accumulating screenshots or large
media, prefer a release asset or external host and link to it instead.
