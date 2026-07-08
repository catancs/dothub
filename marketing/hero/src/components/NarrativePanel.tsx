import React from "react";
import { Easing, interpolate } from "remotion";
import { COLORS } from "../theme";
import { FONTS } from "../fonts";
import { StepRail } from "./StepRail";

export type Copy = {
  eyebrow: string;
  lead: string;
  accent: string;
  tail?: string;
  sub: string;
};

type Props = {
  frame: number;
  progress: number;
  copy: Copy[];
  /** cumulative start frame for each scene */
  starts: number[];
  durations: number[];
};

const Headline: React.FC<{ c: Copy }> = ({ c }) => (
  <h1
    style={{
      fontFamily: FONTS.serif,
      fontWeight: 800,
      fontSize: 43,
      lineHeight: 0.99,
      letterSpacing: "-0.032em",
      color: COLORS.blue,
      margin: 0,
    }}
  >
    {c.lead}
    <span style={{ color: COLORS.amber }}>{c.accent}</span>
    {c.tail ?? ""}
  </h1>
);

export const NarrativePanel: React.FC<Props> = ({
  frame,
  progress,
  copy,
  starts,
  durations,
}) => {
  return (
    <div
      style={{
        width: 376,
        flex: "none",
        display: "flex",
        flexDirection: "column",
        height: "100%",
        justifyContent: "center",
        gap: 30,
      }}
    >
      {/* crossfading text block, fixed height to avoid layout shift */}
      <div style={{ position: "relative", height: 250 }}>
        {copy.map((c, i) => {
          const start = starts[i];
          const dur = durations[i];
          const local = frame - start;
          const isLast = i === copy.length - 1;
          // fade in at start of window; fade out near end (last scene stays up
          // so the loop seam is a clean whole-panel fade in HeroVideo)
          const fadeIn = interpolate(local, [0, 13], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.out(Easing.cubic),
          });
          const fadeOut = isLast
            ? 1
            : interpolate(local, [dur - 12, dur], [1, 0], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.in(Easing.cubic),
              });
          const opacity = Math.min(fadeIn, fadeOut);
          const rise = interpolate(fadeIn, [0, 1], [16, 0]);

          if (opacity <= 0.001) return null;

          return (
            <div
              key={i}
              style={{
                position: "absolute",
                inset: 0,
                opacity,
                transform: `translateY(${rise}px)`,
              }}
            >
              <div
                style={{
                  fontFamily: FONTS.sans,
                  fontWeight: 700,
                  fontSize: 13,
                  letterSpacing: "0.16em",
                  textTransform: "uppercase",
                  color: COLORS.amber,
                  marginBottom: 16,
                }}
              >
                {c.eyebrow}
              </div>
              <Headline c={c} />
              <p
                style={{
                  fontFamily: FONTS.sans,
                  fontSize: 16.5,
                  fontWeight: 500,
                  lineHeight: 1.5,
                  color: COLORS.ink2,
                  marginTop: 18,
                  maxWidth: "34ch",
                }}
              >
                {c.sub}
              </p>
            </div>
          );
        })}
      </div>

      <StepRail progress={progress} />
    </div>
  );
};
