// dothub brand tokens, mirrored from app/static/app.css so the hero reads as the real product.

export const COLORS = {
  ink: "#181510",
  ink2: "#413b30",
  ink3: "#6a6456",
  paper: "#f3efe4",
  surface: "#fbf8f0",
  surface2: "#efe7d7",
  raise: "#fdfbf4",
  line: "#ddd4c1",
  line2: "#e7dfcd",
  blue: "#2536c9",
  blue700: "#1a279e",
  blueTint: "#e2e5f8",
  amber: "#ff5230",
  amberTint: "#ffe1d9",
  // private / public status pills (from detail.html)
  privBg: "#fdeecd",
  privInk: "#8a5a00",
  pubBg: "#e6f4ea",
  pubInk: "#137333",
  // the source Claude icon tile
  agentBg: "#0b0a09",
  agentCreature: "#c8734f",
} as const;

export const RADIUS = {
  lg: 16,
  md: 11,
  sm: 10,
} as const;

// hard riso offset shadows
export const SHADOW = {
  card: `6px 6px 0 ${COLORS.amber}`,
  cardHover: `9px 9px 0 ${COLORS.amber}`,
  btn: `3px 3px 0 ${COLORS.amber}`,
  soft: `3px 3px 0 rgba(37,54,201,.10)`,
  blue: `6px 6px 0 rgba(37,54,201,.14)`,
} as const;

// halftone dot background (matches body background-image in app.css, scaled up for video)
export const DOT_BG = {
  backgroundColor: COLORS.paper,
  backgroundImage: `radial-gradient(rgba(37,54,201,.13) 1px, transparent 1.6px)`,
  backgroundSize: "13px 13px",
} as const;

export const VIDEO = {
  width: 1280,
  height: 720,
  fps: 30,
} as const;

// per-scene durations in frames (30fps). Total = 264 frames ≈ 8.8s.
export const SCENES = {
  publish: 66,
  private: 60,
  choose: 72,
  live: 66,
} as const;

export const TOTAL_FRAMES =
  SCENES.publish + SCENES.private + SCENES.choose + SCENES.live;
