// Geometry shared across scenes. The AppFrame content area ("stage") sits below
// the browser chrome (44) + dothub nav (52) inside a 728x560 window (2px borders).
export const APP_W = 728;
export const APP_H = 560;
export const STAGE_W = APP_W - 4; // 724
export const STAGE_H = APP_H - 4 - 44 - 52; // 460

export const CENTER_X = STAGE_W / 2; // 362
