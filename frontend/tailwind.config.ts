import type { Config } from "tailwindcss";

/**
 * STRICT NEO-BRUTALISM ENFORCER
 * - Palet di-override total (bukan extend): hanya warna mandat PRD yang ada.
 * - borderRadius hanya "none" & "full" (full khusus titik lampu status).
 * - boxShadow hanya blok solid tanpa blur.
 * - backdrop-blur / backdrop-filter dimatikan di level core plugin.
 */
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  corePlugins: {
    backdropBlur: false,
    backdropFilter: false,
  },
  theme: {
    colors: {
      transparent: "transparent",
      current: "currentColor",
      ink: "#000000",
      white: "#FFFFFF",
      canvas: "#F4F0EA",
      concrete: "#E5E5E0",
      acid: "#FFE600",
      hazard: "#FF4D00",
      radar: "#00FF66",
      magenta: "#FF007A",
      crimson: "#FF0033",
      emerald: "#00CC66",
    },
    borderRadius: {
      none: "0px",
      full: "9999px",
    },
    boxShadow: {
      none: "none",
      "brutal-sm": "4px 4px 0px 0px #000000",
      brutal: "8px 8px 0px 0px #000000",
    },
    extend: {
      fontFamily: {
        display: ["var(--font-display)", "Arial Black", "Impact", "sans-serif"],
        mono: ["var(--font-mono)", "Consolas", "Courier New", "monospace"],
      },
      keyframes: {
        stripes: {
          "0%": { backgroundPosition: "0 0" },
          "100%": { backgroundPosition: "34px 0" },
        },
      },
      animation: {
        stripes: "stripes 0.8s linear infinite",
      },
    },
  },
  plugins: [],
};

export default config;
