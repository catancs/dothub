import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { COLORS, RADIUS, SHADOW } from "../theme";
import { FONTS } from "../fonts";
import { SetupCard } from "../components/SetupCard";
import { LockIcon, GlobeIcon, CheckIcon } from "../components/icons";
import { STAGE_H, STAGE_W } from "../stage";

const CARD_W = 300;
const CARD_LEFT = 52;
const CARD_TOP = 84;

const PANEL_LEFT = 392;
const PANEL_W = 300;

// mix two hex colors
const mix = (a: string, b: string, t: number) => {
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
  const pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
  const c = pa.map((v, i) => Math.round(v + (pb[i] - v) * t));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
};

const CONFETTI = Array.from({ length: 16 }, (_, i) => {
  const ang = (i / 16) * Math.PI * 2 + (i % 3);
  const dist = 60 + (i % 5) * 22;
  return {
    dx: Math.cos(ang) * dist,
    dy: Math.sin(ang) * dist * 0.8 - 10,
    color: i % 2 === 0 ? COLORS.amber : COLORS.blue,
    size: 7 + (i % 3) * 2,
    delay: (i % 4) * 1.2,
  };
});

export const Scene3Choose: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const inAll = spring({ frame, fps, config: { damping: 20, mass: 0.8 } });

  // button press around frame 16
  const press = interpolate(frame, [14, 18, 22], [0, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // the flip
  const flip = spring({
    frame: frame - 22,
    fps,
    config: { damping: 15, mass: 0.9, stiffness: 120 },
  });

  const trackColor = mix(COLORS.surface2, COLORS.blue, flip);
  const trackW = 96;
  const knobX = interpolate(flip, [0, 1], [4, trackW - 34 - 4]);
  const knobColor = mix(COLORS.amber, "#ffffff", flip);

  // burst trigger
  const burst = frame - 26;

  const privLabelOn = interpolate(flip, [0, 0.5], [1, 0.25], {
    extrapolateRight: "clamp",
  });
  const pubLabelOn = interpolate(flip, [0.5, 1], [0.25, 1], {
    extrapolateLeft: "clamp",
  });

  return (
    <AbsoluteFill style={{ opacity: inAll }}>
      {/* the setup card */}
      <div
        style={{
          position: "absolute",
          left: CARD_LEFT,
          top: CARD_TOP,
          width: CARD_W,
          transform: `translateY(${interpolate(inAll, [0, 1], [8, 0])}px)`,
        }}
      >
        <SetupCard
          title="agent-core"
          author="elio"
          slug="agent-core"
          width={CARD_W}
          shadow={SHADOW.card}
          borderColor={mix(COLORS.blue, COLORS.blue, 1)}
          files={[
            { label: "CLAUDE.md", note: "context" },
            { label: "skills/", note: "6 skills" },
            { label: "hooks/", note: "3 hooks" },
          ]}
        />
        {/* status pill flipping Private -> Public */}
        <div style={{ position: "absolute", right: 18, top: 18 }}>
          <div style={{ position: "relative", height: 24 }}>
            <span
              style={{
                position: "absolute",
                right: 0,
                top: 0,
                opacity: privLabelOn,
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                fontFamily: FONTS.mono,
                fontSize: 11,
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                fontWeight: 700,
                padding: "5px 11px",
                borderRadius: 999,
                background: COLORS.privBg,
                color: COLORS.privInk,
                whiteSpace: "nowrap",
              }}
            >
              <LockIcon size={12} color={COLORS.privInk} strokeWidth={2.6} />
              Private
            </span>
            <span
              style={{
                position: "absolute",
                right: 0,
                top: 0,
                opacity: pubLabelOn,
                transform: `scale(${interpolate(pubLabelOn, [0, 1], [0.8, 1])})`,
                transformOrigin: "right center",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                fontFamily: FONTS.mono,
                fontSize: 11,
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                fontWeight: 700,
                padding: "5px 11px",
                borderRadius: 999,
                background: COLORS.pubBg,
                color: COLORS.pubInk,
                whiteSpace: "nowrap",
              }}
            >
              <GlobeIcon size={12} color={COLORS.pubInk} strokeWidth={2.6} />
              Public
            </span>
          </div>
        </div>
      </div>

      {/* control panel */}
      <div
        style={{
          position: "absolute",
          left: PANEL_LEFT,
          top: 96,
          width: PANEL_W,
          transform: `translateX(${interpolate(inAll, [0, 1], [26, 0])}px)`,
          opacity: inAll,
          background: COLORS.surface,
          border: `2px solid ${COLORS.blue}`,
          borderRadius: RADIUS.lg,
          padding: 22,
          boxShadow: SHADOW.soft,
        }}
      >
        <div
          style={{
            fontFamily: FONTS.mono,
            fontSize: 11,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
            color: COLORS.amber,
            fontWeight: 700,
            marginBottom: 16,
          }}
        >
          Visibility
        </div>

        {/* toggle row */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            marginBottom: 20,
          }}
        >
          <span
            style={{
              fontFamily: FONTS.sans,
              fontSize: 13.5,
              fontWeight: 700,
              color: COLORS.privInk,
              opacity: privLabelOn,
            }}
          >
            Private
          </span>
          <div
            style={{
              position: "relative",
              width: trackW,
              height: 38,
              borderRadius: 999,
              background: trackColor,
              border: `2px solid ${mix(COLORS.amber, COLORS.blue, flip)}`,
              flex: "none",
            }}
          >
            <div
              style={{
                position: "absolute",
                top: 2,
                left: knobX,
                width: 30,
                height: 30,
                borderRadius: "50%",
                background: knobColor,
                boxShadow: "1px 1px 3px rgba(0,0,0,0.25)",
                display: "grid",
                placeItems: "center",
              }}
            >
              {flip > 0.5 ? (
                <GlobeIcon size={15} color={COLORS.blue} strokeWidth={2.6} />
              ) : (
                <LockIcon size={14} color="#fff" strokeWidth={2.6} />
              )}
            </div>
          </div>
          <span
            style={{
              fontFamily: FONTS.sans,
              fontSize: 13.5,
              fontWeight: 700,
              color: COLORS.pubInk,
              opacity: pubLabelOn,
            }}
          >
            Public
          </span>
        </div>

        {/* primary button */}
        <button
          style={{
            width: "100%",
            fontFamily: FONTS.sans,
            fontWeight: 700,
            fontSize: 14.5,
            padding: "12px 18px",
            borderRadius: RADIUS.md,
            border: "2px solid transparent",
            background: flip > 0.5 ? COLORS.pubInk : COLORS.blue,
            color: "#fff",
            boxShadow: flip > 0.5 ? "3px 3px 0 rgba(19,115,51,0.3)" : SHADOW.btn,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
            transform: `scale(${1 - press * 0.05})`,
          }}
        >
          {flip > 0.5 ? (
            <>
              <CheckIcon size={16} color="#fff" strokeWidth={3} />
              Published to everyone
            </>
          ) : (
            "Publish to everyone"
          )}
        </button>

        <div
          style={{
            fontFamily: FONTS.sans,
            fontSize: 12.5,
            color: COLORS.ink3,
            marginTop: 12,
            lineHeight: 1.4,
          }}
        >
          {flip > 0.5
            ? "Now discoverable by everyone."
            : "You decide when it goes live."}
        </div>

        {/* confetti burst from the button/toggle area */}
        {CONFETTI.map((c, i) => {
          const t = interpolate(burst - c.delay, [0, 22], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.out(Easing.cubic),
          });
          if (t <= 0 || t >= 1) return null;
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: PANEL_W / 2 - 6,
                top: 150,
                width: c.size,
                height: c.size,
                borderRadius: i % 3 === 0 ? 2 : "50%",
                background: c.color,
                opacity: interpolate(t, [0, 0.2, 1], [0, 1, 0]),
                transform: `translate(${c.dx * t}px, ${
                  c.dy * t + 40 * t * t
                }px) scale(${interpolate(t, [0, 1], [1, 0.5])})`,
              }}
            />
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
