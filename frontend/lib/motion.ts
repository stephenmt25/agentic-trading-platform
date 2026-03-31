/**
 * Motion tokens for the Praxis Trading Platform.
 *
 * Easing curves, durations, and reusable framer-motion variants adapted from
 * the drift design system. Import these instead of hard-coding animation values.
 */

import type { Variants, Transition } from "framer-motion";

// ---- Easing curves (framer-motion tuple format) ----

export const easing = {
  default: [0.25, 0.1, 0.25, 1.0] as const,   // smooth decelerate — most transitions
  enter: [0.0, 0.0, 0.2, 1.0] as const,        // elements appearing
  exit: [0.4, 0.0, 1.0, 1.0] as const,          // elements leaving
  spring: [0.34, 1.56, 0.64, 1.0] as const,     // bouncy — celebrations, counters
};

// ---- Durations (seconds) ----

export const duration = {
  instant: 0.1,
  fast: 0.2,
  normal: 0.35,
  slow: 0.6,
  dramatic: 1.2,
};

// ---- Reusable animation variants ----

/** Full-page entrance: fade up from 24px below */
export const pageEnter: Variants = {
  initial: { opacity: 0, y: 24 },
  animate: {
    opacity: 1,
    y: 0,
    transition: { duration: duration.slow, ease: easing.enter },
  },
};

/** Container that staggers its children 60ms apart */
export const staggerContainer: Variants = {
  initial: {},
  animate: {
    transition: { staggerChildren: 0.06 },
  },
};

/** Child element: fade up from 16px below (use inside staggerContainer) */
export const fadeUpChild: Variants = {
  initial: { opacity: 0, y: 16 },
  animate: {
    opacity: 1,
    y: 0,
    transition: { duration: duration.normal, ease: easing.enter },
  },
};

// ---- Interaction presets (inline, not variants) ----

/** Subtle scale-down on click/tap */
export const tapScale = { scale: 0.97 };
export const tapTransition: Transition = { duration: duration.instant, ease: easing.spring };

/** Card hover lift */
export const hoverLift = { y: -2, boxShadow: "0 4px 16px rgba(0, 0, 0, 0.4)" };
export const hoverTransition: Transition = { duration: duration.fast, ease: easing.default };

/** Nav active indicator layout transition */
export const navIndicatorTransition: Transition = {
  duration: duration.normal,
  ease: easing.default,
};
