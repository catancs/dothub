import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { COLORS, RADIUS } from "../theme";
import { FONTS } from "../fonts";
import { SetupCard } from "../components/SetupCard";
import { SearchIcon, DownloadIcon, ArrowIcon } from "../components/icons";
import { STAGE_W } from "../stage";

type Item = {
  title: string;
  author: string;
  slug: string;
  tags: string[];
  pulls: number;
  runsCode: boolean;
  isOurs?: boolean;
  appearAt: number;
  from: { x: number; y: number };
};

const CARD_W = 214;
const COL_GAP = 18;
const ROW_GAP = 18;
const GRID_LEFT = 22;
const GRID_TOP = 64;

const GRID_W = 3 * CARD_W + 2 * COL_GAP;
const GRID_LEFT_CENTERED = (STAGE_W - GRID_W) / 2;

const COL_X = [
  GRID_LEFT_CENTERED,
  GRID_LEFT_CENTERED + CARD_W + COL_GAP,
  GRID_LEFT_CENTERED + 2 * (CARD_W + COL_GAP),
];
const ROW_Y = [GRID_TOP, GRID_TOP + 192 + ROW_GAP];

const ITEMS: Item[] = [
  {
    title: "rust-fast",
    author: "mara",
    slug: "rust-fast",
    tags: ["rust", "lint"],
    pulls: 312,
    runsCode: true,
    appearAt: 0,
    from: { x: -20, y: -10 },
  },
  {
    title: "db-tools",
    author: "noor",
    slug: "db-tools",
    tags: ["sql", "migrations"],
    pulls: 188,
    runsCode: false,
    appearAt: 2,
    from: { x: 20, y: -10 },
  },
  {
    title: "test-runner",
    author: "jules",
    slug: "test-runner",
    tags: ["pytest"],
    pulls: 240,
    runsCode: true,
    appearAt: 4,
    from: { x: 30, y: 10 },
  },
  {
    title: "docs-bot",
    author: "sana",
    slug: "docs-bot",
    tags: ["docs"],
    pulls: 97,
    runsCode: false,
    appearAt: 6,
    from: { x: -20, y: 10 },
  },
  {
    title: "deploy-kit",
    author: "owen",
    slug: "deploy-kit",
    tags: ["ci", "deploy"],
    pulls: 156,
    runsCode: true,
    appearAt: 8,
    from: { x: 20, y: -10 },
  },
  // ours lands in the bottom-right slot
  {
    title: "agent-core",
    author: "elio",
    slug: "agent-core",
    tags: ["agent"],
    pulls: 1,
    runsCode: true,
    isOurs: true,
    appearAt: 10,
    from: { x: 0, y: -120 },
  },
];

const MiniTag: React.FC<{ label: string }> = ({ label }) => (
  <span
    style={{
      fontFamily: FONTS.mono,
      fontSize: 9.5,
      fontWeight: 500,
      color: COLORS.blue,
      background: COLORS.blueTint,
      border: `1px solid ${COLORS.blue}`,
      padding: "1.5px 6px",
      borderRadius: 999,
      whiteSpace: "nowrap",
    }}
  >
    {label}
  </span>
);

const MiniCard: React.FC<{ item: Item; opacity: number; transform: string }> = ({
  item,
  opacity,
  transform,
}) => (
  <div style={{ width: CARD_W, opacity, transform }}>
    <div
      style={{
        background: item.isOurs ? COLORS.raise : COLORS.surface,
        border: `2px solid ${item.isOurs ? COLORS.amber : COLORS.blue}`,
        borderRadius: RADIUS.lg,
        boxShadow: item.isOurs
          ? `5px 5px 0 ${COLORS.blue}`
          : `5px 5px 0 ${COLORS.amber}`,
        padding: 16,
        position: "relative",
      }}
    >
      <div
        style={{
          fontFamily: FONTS.serif,
          fontWeight: 800,
          fontSize: 19,
          letterSpacing: "-0.02em",
          lineHeight: 1.02,
          color: COLORS.ink,
        }}
      >
        {item.title}
      </div>
      <div
        style={{
          fontFamily: FONTS.mono,
          fontSize: 11,
          color: COLORS.ink3,
          marginTop: 4,
        }}
      >
        <b style={{ color: COLORS.blue, fontWeight: 500 }}>{item.author}</b>/
        {item.slug}
      </div>
      <div
        style={{
          display: "flex",
          gap: 5,
          marginTop: 9,
          flexWrap: "wrap",
          minHeight: 18,
        }}
      >
        {item.tags.map((t) => (
          <MiniTag key={t} label={t} />
        ))}
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginTop: 12,
          paddingTop: 10,
          borderTop: `2px solid ${COLORS.line}`,
        }}
      >
        <span
          style={{
            width: 22,
            height: 22,
            borderRadius: "50%",
            display: "grid",
            placeItems: "center",
            fontFamily: FONTS.mono,
            fontSize: 9.5,
            fontWeight: 700,
            color: "#fff",
            background: COLORS.blue,
          }}
        >
          {item.author.slice(0, 2).toUpperCase()}
        </span>
        <span
          style={{
            fontFamily: FONTS.mono,
            fontSize: 11,
            color: COLORS.ink3,
          }}
        >
          {item.pulls} pulls
        </span>
        <span
          style={{
            marginLeft: "auto",
            fontFamily: FONTS.sans,
            fontSize: 9.5,
            fontWeight: 700,
            letterSpacing: "0.03em",
            textTransform: "uppercase",
            padding: "3px 8px",
            borderRadius: 999,
            color: "#fff",
            background: item.runsCode ? COLORS.amber : COLORS.blue,
          }}
        >
          {item.runsCode ? "runs code" : "no code"}
        </span>
      </div>
    </div>
  </div>
);

export const Scene4Live: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // toolbar + grid fade in
  const toolbarIn = interpolate(frame, [0, 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  // our card slides + settle + ring
  const ours = ITEMS.find((i) => i.isOurs)!;
  const oursIndex = ITEMS.indexOf(ours);
  const oursCol = oursIndex % 3;
  const oursRow = Math.floor(oursIndex / 3);
  const oursTargetX = COL_X[oursCol] + CARD_W / 2;
  const oursTargetY = ROW_Y[oursRow] + 80;
  const oursLocal = frame - ours.appearAt;
  const oursIn = spring({
    frame: oursLocal,
    fps,
    config: { damping: 14, mass: 0.9, stiffness: 90 },
  });
  const oursY = interpolate(oursIn, [0, 1], [-180, 0]);
  const oursOpacity = interpolate(oursLocal, [0, 6], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // settling impact ring + hatched focus line under the top row gap
  const ring = spring({
    frame: oursLocal - 10,
    fps,
    config: { damping: 11, mass: 0.5 },
  });
  const ringR = interpolate(ring, [0, 1], [70, 150]);
  const ringO = interpolate(ring, [0, 1], [0.7, 0]);

  // a "pull" arrow lands on our card partway through
  const pullArrive = interpolate(frame, [22, 28], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const pullOp = interpolate(frame, [38, 46], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // pull-count on our card: 1 -> 4 after the install lands
  const ourPulls = Math.round(
    interpolate(frame, [30, 42], [1, 4], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
  );

  // whole stage subtle fade-out at the tail for the seamless loop seam
  const stageOut = interpolate(frame, [58, 66], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ opacity: stageOut }}>
      {/* toolbar: pills + search */}
      <div
        style={{
          position: "absolute",
          top: 16,
          left: 22,
          right: 22,
          display: "flex",
          alignItems: "center",
          gap: 10,
          opacity: toolbarIn,
          transform: `translateY(${interpolate(toolbarIn, [0, 1], [-8, 0])}px)`,
        }}
      >
        <div
          style={{
            display: "inline-flex",
            background: COLORS.surface,
            border: `2px solid ${COLORS.blue}`,
            borderRadius: 11,
            padding: 3,
          }}
        >
          {["Discover", "Following"].map((t, i) => (
            <span
              key={t}
              style={{
                fontFamily: FONTS.sans,
                fontSize: 12,
                fontWeight: 700,
                color: i === 0 ? "#fff" : COLORS.blue,
                background: i === 0 ? COLORS.blue : "transparent",
                padding: "5px 11px",
                borderRadius: 8,
              }}
            >
              {t}
            </span>
          ))}
        </div>
        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            gap: 8,
            background: COLORS.surface,
            border: `2px solid ${COLORS.blue}`,
            borderRadius: 11,
            padding: "6px 13px",
            color: COLORS.blue,
          }}
        >
          <SearchIcon size={13} color={COLORS.blue} />
          <span
            style={{
              fontFamily: FONTS.sans,
              fontSize: 12,
              color: COLORS.ink3,
            }}
          >
            Search setups by title
          </span>
        </div>
      </div>

      {/* grid */}
      <div style={{ position: "absolute", inset: 0 }}>
        {ITEMS.filter((i) => !i.isOurs).map((item) => {
          const idx = ITEMS.indexOf(item);
          const col = idx % 3;
          const row = Math.floor(idx / 3);
          const x = COL_X[col];
          const y = ROW_Y[row];
          const local = frame - item.appearAt;
          const inSpring = spring({
            frame: local,
            fps,
            config: { damping: 16, mass: 0.7 },
          });
          const op = interpolate(local, [0, 6], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          const ox = interpolate(inSpring, [0, 1], [item.from.x, 0]);
          const oy = interpolate(inSpring, [0, 1], [item.from.y, 0]);
          return (
            <div
              key={item.slug}
              style={{ position: "absolute", left: x, top: y }}
            >
              <MiniCard
                item={item}
                opacity={op}
                transform={`translate(${ox}px, ${oy}px)`}
              />
            </div>
          );
        })}

        {/* our card flying in */}
        <div
          style={{
            position: "absolute",
            left: COL_X[oursCol],
            top: ROW_Y[oursRow],
            width: CARD_W,
            opacity: oursOpacity,
            transform: `translateY(${oursY}px)`,
          }}
        >
          {/* impact ring */}
          {ringO > 0.01 ? (
            <div
              style={{
                position: "absolute",
                left: oursTargetX - COL_X[oursCol],
                top: 80 - 150,
                width: 0,
                height: 0,
                pointerEvents: "none",
              }}
            >
              <div
                style={{
                  position: "absolute",
                  left: -ringR,
                  top: -ringR,
                  width: ringR * 2,
                  height: ringR * 2,
                  borderRadius: "50%",
                  border: `3px solid ${COLORS.amber}`,
                  opacity: ringO,
                }}
              />
            </div>
          ) : null}

          <MiniCard
            item={{ ...ours, pulls: ourPulls }}
            opacity={1}
            transform=""
          />

          {/* the new-badge: a "Just published" ribbon */}
          <div
            style={{
              position: "absolute",
              top: -12,
              left: -10,
              transform: `rotate(-6deg) scale(${interpolate(
                oursIn,
                [0, 1],
                [0.4, 1],
              )})`,
              fontFamily: FONTS.mono,
              fontSize: 10.5,
              fontWeight: 700,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              background: COLORS.amber,
              color: "#fff",
              padding: "4px 9px",
              borderRadius: 7,
              boxShadow: "2px 2px 0 rgba(0,0,0,0.18)",
            }}
          >
            Just published
          </div>

          {/* install arrow + label landing on the card */}
          {pullArrive > 0 ? (
            <div
              style={{
                position: "absolute",
                top: 70,
                left: -54,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 3,
                opacity: pullOp,
                transform: `translateX(${
                  interpolate(pullArrive, [0, 1], [-22, 0]) * 1
                }px)`,
              }}
            >
              <span
                style={{
                  fontFamily: FONTS.sans,
                  fontWeight: 700,
                  fontSize: 11,
                  color: COLORS.blue,
                  background: COLORS.surface,
                  border: `1.5px solid ${COLORS.blue}`,
                  borderRadius: 7,
                  padding: "2px 7px",
                  whiteSpace: "nowrap",
                }}
              >
                install
              </span>
              <ArrowIcon size={22} color={COLORS.blue} strokeWidth={2.6} />
              <DownloadIcon size={13} color={COLORS.blue} />
            </div>
          ) : null}
        </div>
      </div>
    </AbsoluteFill>
  );
};
