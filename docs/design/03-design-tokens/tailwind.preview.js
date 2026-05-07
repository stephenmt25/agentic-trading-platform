/**
 * Praxis — Tailwind v4 config preview.
 *
 * This is a REFERENCE file. Drop the relevant sections into the actual
 * tailwind.config.{ts,js} in frontend/. We're using it here as a single
 * place where the token system shows up in Tailwind grammar so the
 * coding harness sees the mapping.
 *
 * NOTE: Tailwind v4 prefers @theme in CSS. This object form is provided
 * because the harness may target either. If using v4 + @theme, derive
 * directly from tokens.css; if using v3, use this object.
 */

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{ts,tsx,js,jsx,mdx}"],
  darkMode: ["class", '[data-mode="hot"]', '[data-mode="cool"]', '[data-mode="calm"]'],
  theme: {
    extend: {
      colors: {
        // Reference the CSS vars, NOT raw hex — keeps the token surface single-source.
        neutral: {
          0: "var(--color-neutral-0)",
          50: "var(--color-neutral-50)",
          100: "var(--color-neutral-100)",
          200: "var(--color-neutral-200)",
          300: "var(--color-neutral-300)",
          400: "var(--color-neutral-400)",
          500: "var(--color-neutral-500)",
          600: "var(--color-neutral-600)",
          700: "var(--color-neutral-700)",
          800: "var(--color-neutral-800)",
          900: "var(--color-neutral-900)",
          950: "var(--color-neutral-950)",
          1000: "var(--color-neutral-1000)",
        },
        bid: {
          50: "var(--color-bid-50)",
          100: "var(--color-bid-100)",
          200: "var(--color-bid-200)",
          300: "var(--color-bid-300)",
          400: "var(--color-bid-400)",
          500: "var(--color-bid-500)",
          600: "var(--color-bid-600)",
          700: "var(--color-bid-700)",
          800: "var(--color-bid-800)",
          900: "var(--color-bid-900)",
          tick: "var(--color-bid-tick-flash)",
        },
        ask: {
          50: "var(--color-ask-50)",
          100: "var(--color-ask-100)",
          200: "var(--color-ask-200)",
          300: "var(--color-ask-300)",
          400: "var(--color-ask-400)",
          500: "var(--color-ask-500)",
          600: "var(--color-ask-600)",
          700: "var(--color-ask-700)",
          800: "var(--color-ask-800)",
          900: "var(--color-ask-900)",
          tick: "var(--color-ask-tick-flash)",
        },
        accent: {
          50: "var(--color-accent-50)",
          100: "var(--color-accent-100)",
          200: "var(--color-accent-200)",
          300: "var(--color-accent-300)",
          400: "var(--color-accent-400)",
          500: "var(--color-accent-500)",
          600: "var(--color-accent-600)",
          700: "var(--color-accent-700)",
          800: "var(--color-accent-800)",
          900: "var(--color-accent-900)",
        },
        warn: {
          400: "var(--color-warn-400)",
          500: "var(--color-warn-500)",
          600: "var(--color-warn-600)",
          700: "var(--color-warn-700)",
        },
        danger: {
          500: "var(--color-danger-500)",
          600: "var(--color-danger-600)",
          700: "var(--color-danger-700)",
          armed: "var(--color-danger-armed-bg)",
        },
        agent: {
          ta: "var(--color-agent-ta)",
          regime: "var(--color-agent-regime)",
          sentiment: "var(--color-agent-sentiment)",
          slm: "var(--color-agent-slm)",
          debate: "var(--color-agent-debate)",
          analyst: "var(--color-agent-analyst)",
        },
        // Semantic aliases (mode-scoped via CSS vars)
        bg: {
          canvas: "var(--bg-canvas)",
          panel: "var(--bg-panel)",
          raised: "var(--bg-raised)",
          rowhover: "var(--bg-row-hover)",
        },
        fg: {
          DEFAULT: "var(--fg-primary)",
          secondary: "var(--fg-secondary)",
          muted: "var(--fg-muted)",
          disabled: "var(--fg-disabled)",
        },
        border: {
          subtle: "var(--border-subtle)",
          strong: "var(--border-strong)",
        },
      },
      fontFamily: {
        sans: "var(--font-sans)",
        mono: "var(--font-mono)",
        tabular: "var(--font-tabular)",
      },
      fontSize: {
        10: "10px",
        11: "11px",
        12: "12px",
        13: "13px",
        14: "14px",
        15: "15px",
        16: "16px",
        18: "18px",
        20: "20px",
        24: "24px",
        30: "30px",
        36: "36px",
        48: "48px",
      },
      spacing: {
        0.5: "2px",
        1.5: "6px",
        // The rest is Tailwind default 4px-based scale, which already matches.
      },
      borderRadius: {
        xs: "2px",
        // sm/md/lg/xl already align with Tailwind defaults at 4/6/8/12.
      },
      boxShadow: {
        sm: "var(--shadow-sm)",
        DEFAULT: "var(--shadow-md)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
        popover: "var(--shadow-popover)",
      },
      transitionDuration: {
        tick: "120ms",
        snap: "180ms",
        ease: "220ms",
        slow: "320ms",
      },
      transitionTimingFunction: {
        "ease-out-expo": "cubic-bezier(0.16, 1, 0.3, 1)",
      },
      zIndex: {
        rise: "10",
        drawer: "20",
        popover: "40",
        modal: "50",
        toast: "60",
        "kill-overlay": "100",
      },
    },
  },
  plugins: [
    // Recommended: a small plugin that adds .num-tabular utility:
    //   .num-tabular { font-variant-numeric: tabular-nums; font-feature-settings: 'tnum' 1, 'cv11' 1; }
    // The harness should add this when generating components that display numbers.
  ],
};
