# NTS Radio (Decky Plugin)

🎧 **Listen to NTS Radio live on your Steam Deck.**

This is a Decky Loader plugin that lets you stream **NTS 1** and **NTS 2** directly from the Steam Deck sidebar, with live show metadata and artwork — no external players, no browser, no backend services.

Built for SteamOS using HTML5 audio for maximum stability.

<img src="https://i.imgur.com/NxQieDr.png" width="250">

---

## Features

- 📻 Live streams for **NTS 1** and **NTS 2**
- 🖼️ Current show artwork
- 📝 Live show titles & metadata
- 🎚️ Volume control
- ⛔ Kill button to instantly stop playback
- 🛡️ Watchdog to recover stalled streams
- ⚡ Lightweight, frontend-only (no Python backend)

---

## Installation

### Option 1: Install from Release (recommended)

1. Download the latest `decky-nts.zip` from the **Releases** page
2. Extract it to: /home/deck/homebrew/plugins/
3. Restart Decky Loader (or reboot your Deck)

The plugin will appear as **NTS Radio** in the Decky sidebar.

---

### Option 2: Build from source (developers)

bash
pnpm install
pnpm run build

---

Copy the resulting dist/ folder into:
/home/deck/homebrew/plugins/decky-nts/
Restart Decky Loader.

Usage
	•	Tap STREAM to start a channel
	•	Tap KILL to immediately stop playback
	•	Adjust volume using the slider
	•	Metadata refreshes automatically every minute

Streams continue playing even if you close the Decky sidebar.

⸻

Technical Notes
	•	Audio playback uses HTML5 Audio
	•	No external players (mpv, VLC, etc.)
	•	No background services or daemons
	•	Metadata fetched from: https://www.nts.live/api/v2/live
  If metadata fails, streaming still works.

Credits
	•	NTS Radio — all audio streams, artwork, and metadata belong to NTS
https://www.nts.live/
	•	Based on RadiYo! a previous Decky radio plugin but rewritten and refactored into a standalone NTS-focused plugin

This project is not affiliated with or endorsed by NTS.

