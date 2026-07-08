import React from "react";
import { Composition } from "remotion";
import { HeroVideo } from "./HeroVideo";
import { TOTAL_FRAMES, VIDEO } from "./theme";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Hero"
      component={HeroVideo}
      durationInFrames={TOTAL_FRAMES}
      fps={VIDEO.fps}
      width={VIDEO.width}
      height={VIDEO.height}
    />
  );
};
