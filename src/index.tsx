import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
  SliderField,
  ToggleField,
  staticClasses,
} from "@decky/ui";
import { definePlugin, ServerAPI } from "@decky/ui";
import { toaster } from "@decky/api";
import { useEffect, useState } from "react";

type Status = {
  available: boolean;
  playing: boolean;
  channel: 1 | 2 | null;
  player: string | null;
  volume: number;
  autoconnect: boolean;
};

type NowPlaying = {
  ch1: any;
  ch2: any;
  fetched_at: number | null;
};

async function call<T>(
  api: ServerAPI,
  method: string,
  args: any = {}
): Promise<T> {
  const res = await api.callPluginMethod(method, args);
  return res.result as T;
}

function toast(title: string, body?: string) {
  try {
    toaster.toast({ title, body });
  } catch {}
}

function Content({ serverAPI }: { serverAPI: ServerAPI }) {
  const [status, setStatus] = useState<Status>({
    available: true,
    playing: false,
    channel: null,
    player: null,
    volume: 70,
    autoconnect: true,
  });

  const [nowPlaying, setNowPlaying] = useState<NowPlaying>({
    ch1: null,
    ch2: null,
    fetched_at: null,
  });

  useEffect(() => {
    let alive = true;

    const tick = async () => {
      try {
        const s = await call<Status>(serverAPI, "get_status");
        const n = await call<NowPlaying>(serverAPI, "get_now_playing");
        if (!alive) return;
        setStatus(s);
        setNowPlaying(n);
      } catch {}
    };

    tick();
    const id = setInterval(tick, 2000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [serverAPI]);

  async function play(channel: 1 | 2) {
    toast("NTS Radio", `Starting NTS ${channel}…`);
    const s = await call<Status>(serverAPI, "play", { channel });
    setStatus(s);
    toast("NTS Radio", `Now playing NTS ${channel}`);
  }

  async function stop() {
    await call(serverAPI, "stop");
    toast("NTS Radio", "Playback stopped");
    setStatus((s) => ({ ...s, playing: false, channel: null }));
  }

  return (
    <PanelSection title="NTS Radio">
      <PanelSectionRow>
        <div style={{ display: "flex", gap: 8 }}>
          <ButtonItem
            onClick={() => play(1)}
            disabled={!status.available}
          >
            Play NTS 1
          </ButtonItem>

          <ButtonItem
            onClick={() => play(2)}
            disabled={!status.available}
          >
            Play NTS 2
          </ButtonItem>

          <ButtonItem
            onClick={stop}
            disabled={!status.playing}
          >
            Stop
          </ButtonItem>
        </div>
      </PanelSectionRow>

      <PanelSectionRow>
        <SliderField
          label={`Volume (${status.volume})`}
          min={0}
          max={100}
          step={1}
          value={status.volume}
          disabled={!status.available}
          onChange={async (v: number) => {
            setStatus((s) => ({ ...s, volume: v }));
            await call(serverAPI, "set_volume", { volume: v });
          }}
        />
      </PanelSectionRow>

      <PanelSectionRow>
        <ToggleField
          label="Auto-reconnect"
          checked={status.autoconnect}
          disabled={!status.available}
          onChange={async (v: boolean) => {
            const s = await call<Status>(serverAPI, "set_autoconnect", {
              enabled: v,
            });
            setStatus(s);
          }}
        />
      </PanelSectionRow>

      <PanelSectionRow>
        <div style={{ fontSize: 12, opacity: 0.75 }}>
          {status.playing && status.channel
            ? `Playing: NTS ${status.channel}`
            : "Not playing"}
          <br />
          Player: {status.player ?? "none"}
        </div>
      </PanelSectionRow>
    </PanelSection>
  );
}

export default definePlugin((serverAPI: ServerAPI) => {
  return {
    title: <div className={staticClasses.Title}>NTS Radio</div>,
    content: <Content serverAPI={serverAPI} />,
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24">
        <path d="M8 5v14l11-7z" fill="currentColor" />
      </svg>
    ),
  };
});
