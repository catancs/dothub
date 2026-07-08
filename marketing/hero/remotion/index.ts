// Entry point (per the brief): remotion/index.ts calling registerRoot.
// src/index.ts is the CLI-autodetected entry and does the same; only whichever
// file is used as the bundle entry actually runs, so this never double-registers.
import { registerRoot } from "remotion";
import { RemotionRoot } from "../src/Root";

registerRoot(RemotionRoot);
