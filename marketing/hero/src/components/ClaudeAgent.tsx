import React from "react";
import { Img, staticFile, useCurrentFrame } from "remotion";
import { COLORS } from "../theme";
import { FONTS } from "../fonts";

type Props = {
  size?: number;
  /** extra vertical offset applied on top of the idle bob */
  offsetY?: number;
  label?: string;
};

// The Claude Code icon as a living character: a dark app-icon tile with the
// amber pixel creature, an idle bob + breathing, and a soft amber halo.
export const ClaudeAgent: React.FC<Props> = ({
  size = 132,
  offsetY = 0,
  label = "Claude Code",
}) => {
  const frame = useCurrentFrame();
  const bob = Math.sin(frame / 13) * 5;
  const breathe = 1 + Math.sin(frame / 17) * 0.018;
  const haloPulse = 0.35 + (Math.sin(frame / 15) + 1) * 0.16;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 12,
        transform: `translateY(${bob + offsetY}px)`,
      }}
    >
      <div
        style={{
          position: "relative",
          width: size,
          height: size,
          transform: `scale(${breathe})`,
        }}
      >
        {/* amber halo */}
        <div
          style={{
            position: "absolute",
            inset: -14,
            borderRadius: size * 0.34,
            background: COLORS.amber,
            filter: "blur(22px)",
            opacity: haloPulse * 0.5,
          }}
        />
        {/* tile */}
        <div
          style={{
            position: "relative",
            width: size,
            height: size,
            borderRadius: size * 0.26,
            overflow: "hidden",
            background: COLORS.agentBg,
            border: `2px solid ${COLORS.ink}`,
            boxShadow: `5px 5px 0 ${COLORS.amber}`,
          }}
        >
          <Img
            src={staticFile("claudecode.webp")}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              imageRendering: "pixelated",
            }}
          />
        </div>
        {/* online status pip */}
        <div
          style={{
            position: "absolute",
            right: -3,
            top: -3,
            width: 20,
            height: 20,
            borderRadius: "50%",
            background: "#3ec46d",
            border: `3px solid ${COLORS.paper}`,
          }}
        />
      </div>
      {label ? (
        <div
          style={{
            fontFamily: FONTS.mono,
            fontSize: 12.5,
            fontWeight: 500,
            color: COLORS.ink3,
            letterSpacing: "0.02em",
          }}
        >
          {label}
        </div>
      ) : null}
    </div>
  );
};
