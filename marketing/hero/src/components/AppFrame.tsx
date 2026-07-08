import React from "react";
import { COLORS, DOT_BG } from "../theme";
import { FONTS } from "../fonts";

type Props = {
  url?: string;
  activeNav?: string;
  width: number;
  height: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
};

const NAV = ["Discover", "Publish", "FAQ"];

// A browser window drawing dothub's chrome so the stage reads as the real product.
export const AppFrame: React.FC<Props> = ({
  url = "dothub.dev",
  activeNav = "Discover",
  width,
  height,
  children,
  style,
}) => {
  return (
    <div
      style={{
        width,
        height,
        flex: "none",
        borderRadius: 20,
        background: COLORS.surface,
        border: `2px solid ${COLORS.blue}`,
        boxShadow: `12px 12px 0 rgba(37,54,201,0.13)`,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        ...style,
      }}
    >
      {/* browser chrome bar */}
      <div
        style={{
          height: 44,
          flex: "none",
          display: "flex",
          alignItems: "center",
          gap: 14,
          padding: "0 18px",
          background: COLORS.surface2,
          borderBottom: `2px solid ${COLORS.line}`,
        }}
      >
        <div style={{ display: "flex", gap: 8 }}>
          {[COLORS.amber, "#f2c14e", "#3ec46d"].map((c) => (
            <div
              key={c}
              style={{
                width: 12,
                height: 12,
                borderRadius: "50%",
                background: c,
                border: `1.5px solid rgba(0,0,0,0.12)`,
              }}
            />
          ))}
        </div>
        <div
          style={{
            flex: 1,
            height: 26,
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "0 14px",
            borderRadius: 9,
            background: COLORS.raise,
            border: `1.5px solid ${COLORS.line}`,
            fontFamily: FONTS.mono,
            fontSize: 12.5,
            color: COLORS.ink3,
            maxWidth: 360,
            margin: "0 auto",
          }}
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: 2,
              background: COLORS.blue,
            }}
          />
          {url}
        </div>
        <div style={{ width: 44 }} />
      </div>

      {/* dothub nav strip */}
      <div
        style={{
          height: 52,
          flex: "none",
          display: "flex",
          alignItems: "center",
          gap: 22,
          padding: "0 22px",
          background: "rgba(243,239,228,0.92)",
          borderBottom: `2px solid ${COLORS.blue}`,
        }}
      >
        <div
          style={{
            fontFamily: FONTS.serif,
            fontWeight: 800,
            fontSize: 19,
            letterSpacing: "-0.03em",
            display: "flex",
            alignItems: "center",
            gap: 8,
            color: COLORS.blue,
          }}
        >
          <span
            style={{
              width: 10,
              height: 10,
              borderRadius: "50%",
              background: COLORS.amber,
            }}
          />
          dothub
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          {NAV.map((n) => {
            const on = n === activeNav;
            return (
              <span
                key={n}
                style={{
                  fontFamily: FONTS.sans,
                  fontSize: 13,
                  fontWeight: 600,
                  color: on ? COLORS.blue : COLORS.ink3,
                  padding: "6px 11px",
                  borderBottom: `2px solid ${on ? COLORS.amber : "transparent"}`,
                }}
              >
                {n}
              </span>
            );
          })}
        </div>
        <div
          style={{
            marginLeft: "auto",
            width: 30,
            height: 30,
            borderRadius: "50%",
            display: "grid",
            placeItems: "center",
            fontFamily: FONTS.mono,
            fontWeight: 700,
            fontSize: 11,
            color: "#fff",
            background: COLORS.blue,
          }}
        >
          EL
        </div>
      </div>

      {/* stage */}
      <div
        style={{
          position: "relative",
          flex: 1,
          overflow: "hidden",
          ...DOT_BG,
        }}
      >
        {children}
      </div>
    </div>
  );
};
