import React from "react";
import { AbsoluteFill, Easing, interpolate, Series, useCurrentFrame } from "remotion";
import { COLORS, DOT_BG, SCENES, TOTAL_FRAMES } from "./theme";
import { FONTS } from "./fonts";
import { AppFrame } from "./components/AppFrame";
import { NarrativePanel, type Copy } from "./components/NarrativePanel";
import { Scene1Publish } from "./scenes/Scene1Publish";
import { Scene2Private } from "./scenes/Scene2Private";
import { Scene3Choose } from "./scenes/Scene3Choose";
import { Scene4Live } from "./scenes/Scene4Live";
import { APP_H, APP_W } from "./stage";

const COPY: Copy[] = [
  {
    eyebrow: "Step 1 · publish",
    lead: "Publish from ",
    accent: "your agent.",
    sub: "Tell Claude Code “publish my setup”. It gathers your CLAUDE.md, skills, hooks, and MCP config — no upload form.",
  },
  {
    eyebrow: "Step 2 · lands private",
    lead: "Lands ",
    accent: "private.",
    sub: "New setups land private. Hidden from the feed and search. Only you can see them.",
  },
  {
    eyebrow: "Step 3 · you decide",
    lead: "You choose to ",
    accent: "publish.",
    sub: "Flip the toggle when you’re ready. Private to public, instantly — with a satisfying snap.",
  },
  {
    eyebrow: "Step 4 · live",
    lead: "Live on the ",
    accent: "feed.",
    sub: "Your setup joins the public feed. Browse, read the effects, and install in one approval.",
  },
];

const DURATIONS = [SCENES.publish, SCENES.private, SCENES.choose, SCENES.live];
const STARTS = [
  0,
  SCENES.publish,
  SCENES.publish + SCENES.private,
  SCENES.publish + SCENES.private + SCENES.choose,
];

export const HeroVideo: React.FC = () => {
  const frame = useCurrentFrame();

  // seamless loop seam: fade the whole panel out at the very tail of the
  // video and fade it back in at the very head, so frame N-1 and frame 0 meet.
  const tailFade = interpolate(
    frame,
    [TOTAL_FRAMES - 8, TOTAL_FRAMES - 1],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.in(Easing.cubic) },
  );
  const headFade = interpolate(
    frame,
    [0, 7],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) },
  );
  const seamOpacity = Math.min(tailFade, headFade);

  // fractional scene index drives the StepRail
  const progress = (frame / TOTAL_FRAMES) * 4;

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.paper }}>
      <div style={{ ...frameWrap(), position: "relative", width: "100%", height: "100%" }}>
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 56,
            padding: "0 60px",
            opacity: seamOpacity,
          }}
        >
        <NarrativePanel
          frame={frame}
          progress={progress}
          copy={COPY}
          starts={STARTS}
          durations={DURATIONS}
        />

        <AppFrame width={APP_W} height={APP_H}>
          <Series>
            <Series.Sequence durationInFrames={SCENES.publish}>
              <Scene1Publish />
            </Series.Sequence>
            <Series.Sequence durationInFrames={SCENES.private}>
              <Scene2Private />
            </Series.Sequence>
            <Series.Sequence durationInFrames={SCENES.choose}>
              <Scene3Choose />
            </Series.Sequence>
            <Series.Sequence durationInFrames={SCENES.live}>
              <Scene4Live />
            </Series.Sequence>
          </Series>
        </AppFrame>
        </div>

      {/* brand footer chip */}
      <div
        style={{
          position: "absolute",
          bottom: 26,
          left: 0,
          right: 0,
          display: "flex",
          justifyContent: "center",
          opacity: interpolate(frame, [4, 14], [0, 0.9], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }) * seamOpacity,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 9,
            padding: "7px 16px",
            background: COLORS.surface,
            border: `2px solid ${COLORS.blue}`,
            borderRadius: 999,
            boxShadow: `3px 3px 0 ${COLORS.amber}`,
            fontFamily: FONTS.mono,
            fontSize: 12.5,
            fontWeight: 500,
            color: COLORS.ink2,
          }}
        >
          <span
            style={{
              width: 9,
              height: 9,
              borderRadius: "50%",
              background: COLORS.amber,
            }}
          />
          dothub — the agent setup hub
        </div>
      </div>
      </div>
    </AbsoluteFill>
  );
};

function frameWrap(): React.CSSProperties {
  return {
    ...DOT_BG,
    // keep the dothub paper dot texture but tint the background a hair warmer
    backgroundImage: `radial-gradient(rgba(37,54,201,.12) 1.2px, transparent 1.8px)`,
    backgroundSize: "16px 16px",
    backgroundColor: COLORS.paper,
  };
}
