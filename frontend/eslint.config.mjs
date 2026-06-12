import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Static assets served verbatim — includes vendored minified bundles
    // (public/html2canvas.min.js alone produced ~213 lint problems). Vendored
    // third-party code is not ours to lint.
    "public/**",
  ]),
  {
    // Rule-level triage decisions from the 2026-06-12 lint-debt burn-down
    // (TECH-DEBT-REGISTRY row 53). The CI gate runs `eslint . --max-warnings 0`,
    // so every entry here is a deliberate, documented decision — not a mute.
    rules: {
      // Underscore prefix marks intentionally-discarded bindings: prop-narrowing
      // destructures (components/primitives/Pill.tsx, Avatar.tsx) and test
      // fixtures (lib/ws/client.test.ts). Mirrors the Python `_unused` convention
      // used across the backend.
      "@typescript-eslint/no-unused-vars": [
        "warn",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
          destructuredArrayIgnorePattern: "^_",
          ignoreRestSiblings: true,
        },
      ],
      // React-Compiler-adoption rules shipped in eslint-plugin-react-hooks v6.
      // The compiler is NOT enabled (no `reactCompiler` in next.config.ts), and
      // these rules flag long-standing intentional idioms in this codebase:
      // SSR-hydration guards (useMediaQuery, Kbd), reset-on-open dialogs
      // (KillSwitchModal, CommandPalette), flash-on-change timers (PnLBadge,
      // OrderBook), data-fetch effects (performance/* panels), and the
      // latest-ref pattern (useSlowMode). Re-enable both as a prerequisite of
      // any future React Compiler adoption — do not fix piecemeal before then.
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/refs": "off",
    },
  },
]);

export default eslintConfig;
