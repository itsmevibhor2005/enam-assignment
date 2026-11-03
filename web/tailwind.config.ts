import type { Config } from "tailwindcss";

/**
 * Tokens mirror the CSS custom properties in globals.css so colour lives in
 * exactly one place. Nothing here is a Tailwind default palette entry: the
 * palette is specific to this product.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "var(--ink)",
        surface: "var(--surface)",
        raised: "var(--raised)",
        line: "var(--line)",
        text: "var(--text)",
        muted: "var(--muted)",
        faint: "var(--faint)",
        signal: "var(--signal)",
        up: "var(--up)",
        down: "var(--down)",
      },
      fontFamily: {
        serif: ["var(--font-serif)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
      fontSize: {
        micro: ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.01em" }],
      },
    },
  },
  plugins: [],
};
export default config;
