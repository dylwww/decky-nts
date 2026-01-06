import os
import json
import time
import signal
import asyncio
import socket as pysocket
import subprocess
from shutil import which
from urllib.request import Request, urlopen

import decky_plugin

# --- Streams ---
NTS_1 = "https://stream-relay-geo.ntslive.net/stream?client=direct"
NTS_2 = "https://stream-relay-geo.ntslive.net/stream2?client=direct"

# --- Metadata (Now/Next) ---
NTS_LIVE_API = "https://www.nts.live/api/v2/live"


def _flatpak_exists(app_id: str) -> bool:
    """Returns True if the flatpak app id exists on the system."""
    if not which("flatpak"):
        return False
    try:
        subprocess.check_output(["flatpak", "info", app_id], stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def _pick_player():
    """
    Prefer mpv, but also support Flatpak MPV/VLC so this can work even if you didn't install a CLI player.
    Returns dict with:
      kind: "mpv" | "mpv_flatpak" | "vlc_flatpak"
      cmd_prefix: list[str]
      supports_ipc: bool
    """
    if which("mpv"):
        return {"kind": "mpv", "cmd_prefix": ["mpv"], "supports_ipc": True}
    if _flatpak_exists("io.mpv.Mpv"):
        return {"kind": "mpv_flatpak", "cmd_prefix": ["flatpak", "run", "io.mpv.Mpv"], "supports_ipc": True}
    if _flatpak_exists("org.videolan.VLC"):
        return {"kind": "vlc_flatpak", "cmd_prefix": ["flatpak", "run", "org.videolan.VLC"], "supports_ipc": False}
    return None


def _safe_unlink(path: str):
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    except Exception:
        pass


def _fetch_json(url: str, timeout=5):
    req = Request(url, headers={"User-Agent": "decky-nts/1.0"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


class Plugin:
    def __init__(self):
        self._player = _pick_player()

        self._proc: subprocess.Popen | None = None
        self._current_url: str | None = None
        self._current_channel: int | None = None

        self._volume = 70  # 0-100
        self._autoconnect = True

        # mpv IPC socket (for setting volume without restarting playback)
        self._ipc_path = os.path.join(decky_plugin.DECKY_PLUGIN_RUNTIME_DIR, "mpv-nts.sock")

        self._watchdog_task: asyncio.Task | None = None
        self._metadata_task: asyncio.Task | None = None

        self._last_meta = {"ch1": None, "ch2": None, "fetched_at": None}

    async def _main(self):
        decky_plugin.logger.info("[NTS] loaded")
        if not self._player:
            decky_plugin.logger.warning("[NTS] No player found (mpv or Flatpak MPV/VLC).")

        self._watchdog_task = asyncio.create_task(self._watchdog_loop())
        self._metadata_task = asyncio.create_task(self._metadata_loop())

    async def _unload(self):
        if self._watchdog_task:
            self._watchdog_task.cancel()
        if self._metadata_task:
            self._metadata_task.cancel()
        await self.stop()

    # ---------- Methods called by the frontend ----------

    async def get_status(self):
        playing = self._proc is not None and self._proc.poll() is None
        return {
            "available": self._player is not None,
            "playing": playing,
            "channel": self._current_channel if playing else None,
            "player": (self._player["kind"] if self._player else None),
            "volume": self._volume,
            "autoconnect": self._autoconnect,
        }

    async def set_volume(self, volume: int):
        v = max(0, min(100, int(volume)))
        self._volume = v

        # If mpv IPC is available and we're playing, apply live.
        await self._mpv_ipc_set_volume(v)
        return await self.get_status()

    async def set_autoconnect(self, enabled: bool):
        self._autoconnect = bool(enabled)
        return await self.get_status()

    async def play(self, channel: int):
        if not self._player:
            raise RuntimeError(
                "No player found. Install MPV or VLC in Desktop Mode (Discover), then reopen the plugin."
            )

        ch = 1 if int(channel) == 1 else 2
        url = NTS_1 if ch == 1 else NTS_2

        # If already playing this channel, do nothing.
        if self._proc is not None and self._proc.poll() is None and self._current_channel == ch:
            return await self.get_status()

        await self.stop()
        await self._start_player(url, ch)
        return await self.get_status()

    async def stop(self):
        await self._kill_player()
        self._current_url = None
        self._current_channel = None
        return await self.get_status()

    async def get_now_playing(self):
        return self._last_meta

    # ---------- Internal helpers ----------

    async def _start_player(self, url: str, channel: int):
        prefix = self._player["cmd_prefix"]
        _safe_unlink(self._ipc_path)

        if self._player["supports_ipc"]:
            cmd = prefix + [
                "--no-video",
                "--keep-open=no",
                "--really-quiet",
                "--title=NTS Radio",
                f"--volume={self._volume}",
                f"--input-ipc-server={self._ipc_path}",
                url,
            ]
        else:
            # VLC flatpak route (headless)
            cmd = prefix + [
                "--intf", "dummy",
                "--no-video",
                "--quiet",
                url,
            ]

        decky_plugin.logger.info(f"[NTS] starting: {cmd}")

        # Detach into its own process group so it survives UI/menu closing.
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
        )
        self._current_url = url
        self._current_channel = channel

    async def _kill_player(self):
        if not self._proc:
            _safe_unlink(self._ipc_path)
            return

        if self._proc.poll() is None:
            try:
                os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
            except Exception as e:
                decky_plugin.logger.error(f"[NTS] kill error: {e}")

        self._proc = None
        _safe_unlink(self._ipc_path)

    async def _watchdog_loop(self):
        while True:
            try:
                await asyncio.sleep(2)

                if not self._autoconnect:
                    continue
                if self._current_url is None or self._current_channel is None:
                    continue

                # If process died unexpectedly, restart it.
                if self._proc is None or self._proc.poll() is not None:
                    decky_plugin.logger.info("[NTS] player died; restarting (autoconnect)")
                    await self._start_player(self._current_url, self._current_channel)

            except asyncio.CancelledError:
                return
            except Exception as e:
                decky_plugin.logger.error(f"[NTS] watchdog error: {e}")

    async def _metadata_loop(self):
        while True:
            try:
                await asyncio.sleep(15)
                data = _fetch_json(NTS_LIVE_API, timeout=5)

                def extract(channel_key: str):
                    ch = (data.get("results") or {}).get(channel_key) or {}
                    now = ch.get("now") or {}
                    nxt = ch.get("next") or {}

                    def get_image(obj):
                        embeds = obj.get("embeds") or {}
                        details = embeds.get("details") or {}
                        media = details.get("media") or {}
                        return media.get("background_large") or media.get("background") or None

                    return {
                        "now_title": now.get("broadcast_title") or now.get("title"),
                        "now_image": get_image(now),
                        "next_title": nxt.get("broadcast_title") or nxt.get("title"),
                        "next_image": get_image(nxt),
                    }

                self._last_meta = {
                    "ch1": extract("channel1"),
                    "ch2": extract("channel2"),
                    "fetched_at": int(time.time()),
                }

            except asyncio.CancelledError:
                return
            except Exception:
                # stay quiet if offline / API hiccups
                pass

    async def _mpv_ipc_set_volume(self, volume: int) -> bool:
        if not self._player or not self._player["supports_ipc"]:
            return False
        if not self._proc or self._proc.poll() is not None:
            return False
        if not os.path.exists(self._ipc_path):
            return False

        msg = json.dumps({"command": ["set_property", "volume", int(volume)]}) + "\n"
        try:
            s = pysocket.socket(pysocket.AF_UNIX, pysocket.SOCK_STREAM)
            s.settimeout(0.25)
            s.connect(self._ipc_path)
            s.sendall(msg.encode("utf-8"))
            s.close()
            return True
        except Exception:
            return False
