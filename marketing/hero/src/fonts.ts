// Load the three dothub brand fonts via @remotion/google-fonts.
// Each loadFont() registers a FontFace and hooks Remotion's delayRender/continueRender
// so the renderer waits for the woff2 files before capturing frames.
import { loadFont as loadBricolage } from "@remotion/google-fonts/BricolageGrotesque";
import { loadFont as loadFamiljen } from "@remotion/google-fonts/FamiljenGrotesk";
import { loadFont as loadSometype } from "@remotion/google-fonts/SometypeMono";

const bricolage = loadBricolage("normal", {
  weights: ["400", "600", "700", "800"],
});
const familjen = loadFamiljen("normal", {
  weights: ["400", "500", "600", "700"],
});
const sometype = loadSometype("normal", { weights: ["400", "500", "700"] });

export const FONTS = {
  // display headlines
  serif: `${bricolage.fontFamily}, "Familjen Grotesk", sans-serif`,
  // body / UI
  sans: `${familjen.fontFamily}, -apple-system, sans-serif`,
  // technical / mono
  mono: `${sometype.fontFamily}, ui-monospace, monospace`,
} as const;
