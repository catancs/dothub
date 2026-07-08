import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { COLORS, RADIUS, SHADOW } from "../theme";
import { FONTS } from "../fonts";
import { ClaudeAgent } from "../components/ClaudeAgent";
import { SetupCard } from "../components/SetupCard";
import { STAGE_H, STAGE_W } from "../stage";

const AGENT_X = 118;
const AGENT_Y = STAGE_H / 2 - 16;
const CARD_W = 296;
const RECEIVER_X = STAGE_W - 66;
const RECEIVER_Y = AGENT_Y;

const CMD = "publish my setup";

export const Scene1Publish: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // agent entrance
  const agentIn = spring({ frame, fps, config: { damping: 16, mass: 0.7 } });
  const agentScale = interpolate(agentIn, [0, 1], [0.7, 1]);

  // command typing
  const typed = Math.max(
    0,
    Math.min(CMD.length, Math.round(interpolate(frame, [8, 30], [0, CMD.length]))),
  );
  const caretOn = Math.floor(frame / 8) % 2 === 0;

  // card travel from agent toward the dothub receiver
  const travel = spring({
    frame: frame - 24,
    fps,
    config: { damping: 18, mass: 1.1, stiffness: 90 },
  });
  const cardStartX = AGENT_X + 18;
  const cardEndX = 250;
  const cardX = interpolate(travel, [0, 1], [cardStartX, cardEndX]);
  const cardY = AGENT_Y - 96;
  const cardAppear = interpolate(frame, [22, 34], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const cardScale = interpolate(travel, [0, 1], [0.86, 1]);
  const cardRot = interpolate(travel, [0, 0.5, 1], [-4, 1.5, 0]);

  // receiver reacts as the card nears it
  const receiverPulse = spring({
    frame: frame - 44,
    fps,
    config: { damping: 12, mass: 0.6 },
  });
  const receiverScale = 1 + Math.sin(frame / 14) * 0.03 + receiverPulse * 0.12;

  // flowing dashes on the path
  const dashOffset = -(frame * 1.4);

  return (
    <AbsoluteFill>
      {/* dashed motion path agent -> receiver */}
      <svg
        width={STAGE_W}
        height={STAGE_H}
        style={{ position: "absolute", inset: 0 }}
      >
        <path
          d={`M ${AGENT_X + 60} ${AGENT_Y - 40} C ${AGENT_X + 200} ${
            AGENT_Y - 150
          }, ${RECEIVER_X - 190} ${RECEIVER_Y - 120}, ${RECEIVER_X - 44} ${
            RECEIVER_Y - 14
          }`}
          fill="none"
          stroke={COLORS.blue}
          strokeWidth={2.5}
          strokeDasharray="2 9"
          strokeLinecap="round"
          strokeDashoffset={dashOffset}
          opacity={interpolate(frame, [10, 22], [0, 0.5], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          })}
        />
      </svg>

      {/* dothub receiver node */}
      <div
        style={{
          position: "absolute",
          left: RECEIVER_X - 46,
          top: RECEIVER_Y - 46,
          width: 92,
          height: 92,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
          transform: `scale(${receiverScale})`,
        }}
      >
        <div
          style={{
            width: 66,
            height: 66,
            borderRadius: "50%",
            background: COLORS.surface,
            border: `2.5px dashed ${COLORS.blue}`,
            display: "grid",
            placeItems: "center",
            boxShadow: SHADOW.soft,
          }}
        >
          <span
            style={{
              width: 16,
              height: 16,
              borderRadius: "50%",
              background: COLORS.amber,
            }}
          />
        </div>
        <span
          style={{
            fontFamily: FONTS.serif,
            fontWeight: 800,
            fontSize: 14,
            color: COLORS.blue,
            letterSpacing: "-0.02em",
          }}
        >
          dothub
        </span>
      </div>

      {/* agent + command chip */}
      <div
        style={{
          position: "absolute",
          left: AGENT_X - 70,
          top: AGENT_Y - 92,
          width: 140,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 14,
          transform: `scale(${agentScale})`,
          opacity: agentIn,
        }}
      >
        <ClaudeAgent size={112} label="" />
      </div>

      {/* command chip below agent */}
      <div
        style={{
          position: "absolute",
          left: AGENT_X - 96,
          top: AGENT_Y + 66,
          width: 232,
          opacity: interpolate(frame, [6, 16], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            background: COLORS.blue,
            color: "#f2f1ff",
            borderRadius: RADIUS.md,
            padding: "10px 13px",
            fontFamily: FONTS.mono,
            fontSize: 13,
            boxShadow: SHADOW.soft,
          }}
        >
          <span style={{ color: COLORS.amber, fontWeight: 700 }}>&rsaquo;</span>
          <span>
            {CMD.slice(0, typed)}
            <span
              style={{
                opacity: typed < CMD.length && caretOn ? 1 : 0,
                color: COLORS.amber,
              }}
            >
              |
            </span>
          </span>
        </div>
      </div>

      {/* the setup card in flight */}
      <div
        style={{
          position: "absolute",
          left: cardX,
          top: cardY,
          width: CARD_W,
          opacity: cardAppear,
          transform: `scale(${cardScale}) rotate(${cardRot}deg)`,
          transformOrigin: "center left",
        }}
      >
        <SetupCard
          title="agent-core"
          author="elio"
          slug="agent-core"
          width={CARD_W}
          shadow={SHADOW.card}
          files={[
            { label: "CLAUDE.md", note: "context" },
            { label: "skills/", note: "6 skills" },
            { label: "hooks/", note: "3 hooks" },
          ]}
        />
      </div>
    </AbsoluteFill>
  );
};
