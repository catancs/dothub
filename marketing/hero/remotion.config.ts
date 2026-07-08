import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
// Crisp 16:9 output; keep the concurrency reasonable for a laptop render.
Config.setChromiumOpenGlRenderer("angle");
