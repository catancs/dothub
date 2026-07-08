import React from "react";
import { COLORS, RADIUS, SHADOW } from "../theme";
import { FONTS } from "../fonts";
import { FileGlyph, LockIcon, GlobeIcon } from "./icons";

export type SetupFile = { label: string; note?: string };

type Props = {
  title: string;
  author: string;
  slug: string;
  files?: SetupFile[];
  status?: "none" | "private" | "public";
  pulls?: number;
  runsCode?: boolean;
  width?: number;
  shadow?: string;
  borderColor?: string;
  style?: React.CSSProperties;
};

const StatusPill: React.FC<{ status: "private" | "public" }> = ({ status }) => {
  const isPriv = status === "private";
  return (
    <span
      style={{
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
        background: isPriv ? COLORS.privBg : COLORS.pubBg,
        color: isPriv ? COLORS.privInk : COLORS.pubInk,
      }}
    >
      {isPriv ? (
        <LockIcon size={13} color={COLORS.privInk} strokeWidth={2.4} />
      ) : (
        <GlobeIcon size={13} color={COLORS.pubInk} strokeWidth={2.4} />
      )}
      {isPriv ? "Private" : "Public"}
    </span>
  );
};

export const SetupCard: React.FC<Props> = ({
  title,
  author,
  slug,
  files,
  status = "none",
  pulls,
  runsCode = false,
  width = 420,
  shadow = SHADOW.card,
  borderColor = COLORS.blue,
  style,
}) => {
  return (
    <div
      style={{
        width,
        background: COLORS.surface,
        border: `2px solid ${borderColor}`,
        borderRadius: RADIUS.lg,
        boxShadow: shadow,
        padding: 22,
        ...style,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        <div>
          <div
            style={{
              fontFamily: FONTS.serif,
              fontWeight: 800,
              fontSize: 24,
              letterSpacing: "-0.02em",
              lineHeight: 1.02,
              color: COLORS.ink,
            }}
          >
            {title}
          </div>
          <div
            style={{
              fontFamily: FONTS.mono,
              fontSize: 12.5,
              color: COLORS.ink3,
              marginTop: 6,
            }}
          >
            <b style={{ color: COLORS.blue, fontWeight: 500 }}>{author}</b>/
            {slug}
          </div>
        </div>
        {status !== "none" ? <StatusPill status={status} /> : null}
      </div>

      {files && files.length > 0 ? (
        <div
          style={{
            marginTop: 16,
            display: "flex",
            flexDirection: "column",
            gap: 7,
          }}
        >
          {files.map((f) => (
            <div
              key={f.label}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                background: COLORS.raise,
                border: `2px solid ${COLORS.line}`,
                borderRadius: RADIUS.md,
                padding: "9px 13px",
                fontFamily: FONTS.mono,
                fontSize: 13.5,
                color: COLORS.ink,
              }}
            >
              <FileGlyph size={15} color={COLORS.blue} />
              <span style={{ fontWeight: 500 }}>{f.label}</span>
              {f.note ? (
                <span
                  style={{
                    marginLeft: "auto",
                    color: COLORS.ink3,
                    fontSize: 11.5,
                  }}
                >
                  {f.note}
                </span>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          paddingTop: 15,
          marginTop: 16,
          borderTop: `2px solid ${COLORS.line}`,
        }}
      >
        <span
          style={{
            display: "flex",
            alignItems: "center",
            gap: 9,
            fontSize: 13,
            color: COLORS.ink2,
            fontWeight: 600,
          }}
        >
          <span
            style={{
              width: 26,
              height: 26,
              borderRadius: "50%",
              display: "grid",
              placeItems: "center",
              fontFamily: FONTS.mono,
              fontSize: 10.5,
              fontWeight: 700,
              color: "#fff",
              background: COLORS.blue,
            }}
          >
            {author.slice(0, 2).toUpperCase()}
          </span>
          {author}
        </span>

        {typeof pulls === "number" ? (
          <span
            style={{
              fontFamily: FONTS.mono,
              fontSize: 12.5,
              color: COLORS.ink3,
            }}
          >
            {pulls} pulls
          </span>
        ) : null}

        <span
          style={{
            marginLeft: "auto",
            fontFamily: FONTS.sans,
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: "0.03em",
            textTransform: "uppercase",
            padding: "5px 11px",
            borderRadius: 999,
            color: "#fff",
            background: runsCode ? COLORS.amber : COLORS.blue,
          }}
        >
          {runsCode ? "runs code" : "no code"}
        </span>
      </div>
    </div>
  );
};
