# Luke Vision

A self-hosted, cable-TV-style site that plays synchronized 24/7 channels of video from the Internet Archive. It's plain HTML/JS plus a standard-library Python script.

## 1. Build the catalog

```
python3 build_catalog.py
```

(On Windows, use `python` or `py` instead of `python3`.) This queries archive.org and writes `catalog.json`. It takes several minutes, because it pauses politely between requests. To change the lineup, edit `CHANNELS` at the top of the script, and check that each collection exists at `https://archive.org/details/<collection>`.

The `catalog.json` that ships with the project is a **placeholder** for testing the player. Running the script overwrites it.

The guide shows each item's cover image (loaded from archive.org) and a short description taken from its metadata. Catalogs built before descriptions were added still show covers; re-run the script to get descriptions too.

## 2. Serve it

Run this from this folder:

```
python3 serve.py
```

This serves only the page and `catalog.json` on port 8080, not the rest of the folder. Opening `index.html` directly as a file won't work, because the page has to fetch `catalog.json`.

## 3. Watch on the Xbox

1. Find your computer's local IP address (`ipconfig` on Windows, for example `192.168.1.20`).
2. On the Xbox, open Edge and go to `http://<computer-ip>:8080`.
3. Press **A** to tune in. If your PC's firewall asks, allow Python on private networks.

Channels are scheduled from the wall clock, so every screen shows the same thing at the same moment.

## 4. Watch away from home

```
python3 tunnel.py
```

Use this instead of `serve.py`, not alongside it. It starts the site and a Cloudflare quick tunnel, then prints a link like `https://some-random-words.trycloudflare.com`. Open that link on any device, anywhere. It needs `cloudflared` (`winget install --id Cloudflare.cloudflared`) but no Cloudflare account.

- The link changes every time you start the tunnel, and it works only while `tunnel.py` is running on your PC. Press Ctrl+C to stop.
- Anyone with the link can watch, so don't post it publicly.
- Only the page goes through your PC. The videos stream straight from archive.org to whatever device you're watching on.
- The Xbox at home can still use `http://<computer-ip>:8080` while the tunnel runs.

## Phones and tablets

Open the same link (the tunnel link, or `http://<computer-ip>:8080` at home) and tap to tune in.

- **Tap** the picture to show the channel info with **CH ▼ / GUIDE / CH ▲** buttons, and a **FULL** button where the browser supports full screen. Tap again to hide them.
- **Swipe up / down** on the picture to change channels.
- In the guide, **tap a show** to see its details and **tap it again** (or **WATCH**) to tune in. Tap a channel name to tune straight to it. Scroll the list up and down; **swipe sideways** or use **EARLIER / LATER** to look ahead.
- iPhones can't make a web page full screen. For a full-screen TV feel, use Safari's Share → **Add to Home Screen**, then open Luke Vision from the home-screen icon. Turn the phone sideways for a bigger picture.

## Controls

| Action | Controller | Keyboard / mouse |
|---|---|---|
| Channel up / down (guide: move selection) | D-pad ▲▼, RB / LB, left stick | ↑ ↓, PgUp / PgDn |
| Guide: look later / earlier | D-pad ◀▶, left stick | ← → |
| Open guide / tune to selection | A | Enter, Space; click a show or channel |
| On-screen buttons | | Click or tap the picture |
| Close guide / hide info | B | Esc, Backspace |
| Show info (OSD) | X | I |
| Toggle guide | Y | G |

If the browser starts the video muted, the next button press turns the sound on. Some browser versions only give pages raw controller access over HTTPS, which the tunnel link provides. If the buttons don't respond, Edge's built-in controller cursor still works: press A to click the picture for on-screen buttons, or click shows in the guide.

## Licensing

Internet Archive items carry different licenses, and many are not public domain. The MonsterVision channel in particular is fan-uploaded recordings of TNT broadcasts, which are still under copyright. This setup is fine for personal viewing at home. **Before you ever publish it publicly, filter by license.** For example, add `AND licenseurl:*publicdomain*` to the queries, or check each item's `licenseurl` metadata.
