export const ANIMATION_DURATION = 200; // Duration of each card's animation in milliseconds
export const ANIMATION_DELAY = 50; // Delay between each card's animation in milliseconds
export const SWAP_DURATION = 300; // Duration for each card swap animation
export const SWAP_STAGGER = 200; // Delay between each swap starting
export const FADE_DURATION = 200; // Duration for cards fading out after swap
export const POP_DURATION = 300; // Duration for solved connection pop animation

export const BASE_URL = `${(import.meta.env.VITE_API_URL as string) ?? "http://localhost:5000"}/connections`;
