import React from "react";

type IconProps = {
  size?: number;
  color?: string;
  strokeWidth?: number;
  style?: React.CSSProperties;
};

export const LockIcon: React.FC<IconProps> = ({
  size = 20,
  color = "currentColor",
  strokeWidth = 2.2,
}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <rect
      x="4.5"
      y="10.5"
      width="15"
      height="10.5"
      rx="2.4"
      stroke={color}
      strokeWidth={strokeWidth}
    />
    <path
      d="M7.75 10.5V7.75a4.25 4.25 0 0 1 8.5 0v2.75"
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
    />
    <circle cx="12" cy="15.4" r="1.5" fill={color} />
  </svg>
);

export const GlobeIcon: React.FC<IconProps> = ({
  size = 20,
  color = "currentColor",
  strokeWidth = 2.2,
}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <circle cx="12" cy="12" r="8.5" stroke={color} strokeWidth={strokeWidth} />
    <path
      d="M3.5 12h17M12 3.5c2.4 2.3 3.6 5.3 3.6 8.5S14.4 18.2 12 20.5c-2.4-2.3-3.6-5.3-3.6-8.5S9.6 5.8 12 3.5Z"
      stroke={color}
      strokeWidth={strokeWidth}
    />
  </svg>
);

export const CheckIcon: React.FC<IconProps> = ({
  size = 20,
  color = "currentColor",
  strokeWidth = 3,
}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <path
      d="M5 12.5l4.2 4.3L19 6.5"
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

export const ArrowIcon: React.FC<IconProps> = ({
  size = 20,
  color = "currentColor",
  strokeWidth = 2.4,
}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <path
      d="M4 12h15m0 0-6-6m6 6-6 6"
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

export const SearchIcon: React.FC<IconProps> = ({
  size = 16,
  color = "currentColor",
  strokeWidth = 2,
}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <circle cx="11" cy="11" r="7" stroke={color} strokeWidth={strokeWidth} />
    <path
      d="m21 21-4.3-4.3"
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
    />
  </svg>
);

export const DownloadIcon: React.FC<IconProps> = ({
  size = 16,
  color = "currentColor",
  strokeWidth = 2.2,
}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <path
      d="M12 3.5v11m0 0 4-4m-4 4-4-4M4.5 18.5h15"
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

// small file-kind glyph used in the setup card rows
export const FileGlyph: React.FC<IconProps> = ({
  size = 15,
  color = "currentColor",
  strokeWidth = 2,
}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <path
      d="M6 3.5h8l4 4V20a.5.5 0 0 1-.5.5h-11A.5.5 0 0 1 6 20V4a.5.5 0 0 1 .5-.5Z"
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinejoin="round"
    />
    <path
      d="M13.5 3.5V8h4.5"
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinejoin="round"
    />
  </svg>
);
