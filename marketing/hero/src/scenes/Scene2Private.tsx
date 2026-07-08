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
import { LockIcon } from "../components/icons";
import { STAGE_H, STAGE_W } from "../stage";

const CARD_W = 336;
const CARD_LEFT = (STAGE_W - CARD_W) / 2;
const CARD_TOP = 34;

const GhostCard: React.FC<{ x: number; y: number; opacity: number }> = ({
  x,
  y,
  opacity,
}) => (
  <div
    style={{
      position: "absolute",
      left: x,
      top: y,
      width: 150,
      height: 92,
      borderRadius: RADIUS.md,
      background: COLORS.surface,
      border: `2px solid ${COLORS.line}`,
      opacity,
      padding: 12,
    }}
  >
    <div
      style={{
        width: "62%",
        height: 11,
        borderRadius: 4,
        background: COLORS.line,
        marginBottom: 9,
      }}
    />
    <div
      style={{
        width: "88%",
        height: 8,
        borderRadius: 4,
        background: COLORS.line2,
        marginBottom: 6,
      }}
    />
    <div
      style={{
        width: "72%",
        height: 8,
        borderRadius: 4,
        background: COLORS.line2,
      }}
    />
  </div>
);

export const Scene2Private: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const cardIn = spring({ frame, fps, config: { damping: 18, mass: 0.8 } });
  const cardScale = interpolate(cardIn, [0, 1], [0.94, 1]);

  // private pill stamps in with an overshoot
  const stamp = spring({
    frame: frame - 12,
    fps,
    config: { damping: 9, mass: 0.6, stiffness: 140 },
  });
  const stampScale = interpolate(stamp, [0, 1], [1.7, 1]);
  const stampOpacity = interpolate(frame, [12, 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // banner + caption
  const bannerIn = interpolate(frame, [22, 34], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  const ghostOpacity = interpolate(frame, [0, 18], [0.5, 0.28], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // spotlight glow behind card
  const glow = interpolate(cardIn, [0, 1], [0, 0.9]);

  return (
    <AbsoluteFill>
      {/* faded public feed behind — the setup is hidden from it */}
      <GhostCard x={30} y={40} opacity={ghostOpacity} />
      <GhostCard x={STAGE_W - 180} y={40} opacity={ghostOpacity} />
      <GhostCard x={30} y={STAGE_H - 132} opacity={ghostOpacity} />
      <GhostCard x={STAGE_W - 180} y={STAGE_H - 132} opacity={ghostOpacity} />

      {/* spotlight */}
      <div
        style={{
          position: "absolute",
          left: CARD_LEFT - 60,
          top: CARD_TOP - 40,
          width: CARD_W + 120,
          height: 320,
          borderRadius: "50%",
          background: `radial-gradient(closest-side, rgba(255,240,205,${
            0.85 * glow
          }), rgba(243,239,228,0))`,
        }}
      />

      {/* the arrived card */}
      <div
        style={{
          position: "absolute",
          left: CARD_LEFT,
          top: CARD_TOP,
          width: CARD_W,
          opacity: cardIn,
          transform: `scale(${cardScale})`,
          transformOrigin: "top center",
        }}
      >
        <SetupCard
          title="agent-core"
          author="elio"
          slug="agent-core"
          width={CARD_W}
          shadow={SHADOW.card}
          files={[
            { label: "CLAUDE.md", note: "context" },
            { label: "skills/", note: "6 skills" },
            { label: "hooks/", note: "3 hooks" },
          ]}
        />

        {/* animated Private pill stamped over the card's top-right */}
        <div
          style={{
            position: "absolute",
            right: 18,
            top: 18,
            transform: `scale(${stampScale}) rotate(-7deg)`,
            opacity: stampOpacity,
            transformOrigin: "center",
          }}
        >
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              fontFamily: FONTS.mono,
              fontSize: 11.5,
              letterSpacing: "0.07em",
              textTransform: "uppercase",
              fontWeight: 700,
              padding: "6px 12px",
              borderRadius: 999,
              background: COLORS.privBg,
              color: COLORS.privInk,
              border: `2px solid ${COLORS.privInk}`,
              boxShadow: `2px 2px 0 rgba(138,90,0,0.25)`,
            }}
          >
            <LockIcon size={13} color={COLORS.privInk} strokeWidth={2.6} />
            Private
          </span>
        </div>
      </div>

      {/* "only you can see this" banner */}
      <div
        style={{
          position: "absolute",
          left: CARD_LEFT - 4,
          top: CARD_TOP + 292,
          width: CARD_W + 8,
          opacity: bannerIn,
          transform: `translateY(${interpolate(bannerIn, [0, 1], [10, 0])}px)`,
          display: "flex",
          alignItems: "center",
          gap: 11,
          background: COLORS.privBg,
          border: `2px solid #e0a63c`,
          borderRadius: RADIUS.md,
          padding: "12px 15px",
        }}
      >
        <div
          style={{
            width: 30,
            height: 30,
            borderRadius: 8,
            flex: "none",
            display: "grid",
            placeItems: "center",
            background: "#e0a63c",
          }}
        >
          <LockIcon size={16} color="#fff" strokeWidth={2.6} />
        </div>
        <div
          style={{
            fontFamily: FONTS.sans,
            fontSize: 13.5,
            lineHeight: 1.35,
            color: COLORS.privInk,
          }}
        >
          <b style={{ fontWeight: 700 }}>Only you can see this.</b> Hidden from
          the feed &amp; search.
        </div>
      </div>
    </AbsoluteFill>
  );
};
