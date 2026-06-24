import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Dark, minimal surfaces (Opus / devxlabs vibe).
        base: "#08090c",
        surface: "#0e1016",
        elevated: "#14171f",
        brand: {
          DEFAULT: "#2dd4bf", // teal-400 — glows on dark
          dark: "#14b8a6",
          50: "#f0fdfa",
          100: "#ccfbf1",
          200: "#99f6e4",
          500: "#14b8a6",
          600: "#0d9488",
          700: "#0f766e",
        },
        ink: "#0f172a",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "'Plus Jakarta Sans'", "Inter", "sans-serif"],
      },
      boxShadow: {
        soft: "0 0 0 1px rgba(45,212,191,0.18), 0 18px 50px -18px rgba(45,212,191,0.35)",
        card: "0 1px 0 0 rgba(255,255,255,0.04) inset, 0 20px 40px -24px rgba(0,0,0,0.8)",
        glow: "0 0 60px -10px rgba(45,212,191,0.25)",
      },
      backgroundImage: {
        "hero-glow":
          "radial-gradient(50% 50% at 50% 0%, rgba(45,212,191,0.18) 0%, rgba(45,212,191,0) 70%)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: { "fade-up": "fade-up 0.6s ease-out both" },
    },
  },
  plugins: [],
} satisfies Config;
