import React from "react";
import { interpolate } from "remotion";
import { COLORS } from "../theme";
import { FONTS } from "../fonts";
import { CheckIcon } from "./icons";

export const STEP_LABELS = [
  "Publish from your agent",
  "Lands private",
  "You go public",
  "Live on the feed",
];

type Props = {
  /** fractional active step, e.g. 1.4 means step 1 done, transitioning into 2 */
  progress: number;
};

export const StepRail: React.FC<Props> = ({ progress }) => {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {STEP_LABELS.map((label, i) => {
        const active = Math.floor(progress) === i;
        const done = progress > i + 0.55;
        const dotColor = done
          ? COLORS.blue
          : active
            ? COLORS.amber
            : "transparent";
        const textColor = active
          ? COLORS.ink
          : done
            ? COLORS.ink2
            : COLORS.ink3;
        const isLast = i === STEP_LABELS.length - 1;

        // pop the active row slightly
        const activeAmt = interpolate(
          Math.abs(progress - (i + 0.35)),
          [0, 0.65],
          [1, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        );

        return (
          <div
            key={label}
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 13,
              padding: "5px 0",
            }}
          >
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                alignSelf: "stretch",
              }}
            >
              <div
                style={{
                  width: 26,
                  height: 26,
                  borderRadius: "50%",
                  flex: "none",
                  display: "grid",
                  placeItems: "center",
                  background: dotColor,
                  border: `2px solid ${
                    done || active ? "transparent" : COLORS.line
                  }`,
                  color: "#fff",
                  fontFamily: FONTS.mono,
                  fontWeight: 700,
                  fontSize: 12,
                  transform: `scale(${1 + activeAmt * 0.08})`,
                  boxShadow: active ? `3px 3px 0 rgba(255,82,48,0.25)` : "none",
                }}
              >
                {done ? (
                  <CheckIcon size={14} color="#fff" strokeWidth={3.2} />
                ) : (
                  <span style={{ color: active ? "#fff" : COLORS.ink3 }}>
                    {i + 1}
                  </span>
                )}
              </div>
              {!isLast ? (
                <div
                  style={{
                    width: 2,
                    flex: 1,
                    minHeight: 14,
                    marginTop: 3,
                    background: done ? COLORS.blue : COLORS.line,
                  }}
                />
              ) : null}
            </div>
            <div
              style={{
                fontFamily: FONTS.sans,
                fontSize: 14.5,
                fontWeight: active ? 700 : 600,
                color: textColor,
                paddingTop: 2,
                letterSpacing: "-0.01em",
                opacity: active ? 1 : 0.85,
              }}
            >
              {label}
            </div>
          </div>
        );
      })}
    </div>
  );
};
