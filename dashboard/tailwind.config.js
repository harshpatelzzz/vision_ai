/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Command-center palette
        void: "#04070d",
        abyss: "#070b16",
        navy: {
          900: "#070d1c",
          800: "#0a1228",
          700: "#0e1a38",
          600: "#13244a",
        },
        cyber: {
          DEFAULT: "#1e90ff",
          400: "#38bdf8",
          500: "#0ea5e9",
          600: "#0284c7",
        },
        cyan: {
          glow: "#22d3ee",
          electric: "#00f0ff",
        },
        signal: {
          green: "#22e3a0",
          amber: "#f5b73d",
          red: "#ff4d61",
          violet: "#a78bfa",
        },
      },
      fontFamily: {
        display: ['"Orbitron"', "system-ui", "sans-serif"],
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      boxShadow: {
        glow: "0 0 20px rgba(34,211,238,0.35)",
        "glow-sm": "0 0 10px rgba(34,211,238,0.25)",
        "glow-green": "0 0 18px rgba(34,227,160,0.4)",
        "glow-red": "0 0 18px rgba(255,77,97,0.45)",
        panel: "0 8px 40px rgba(0,0,0,0.55)",
      },
      backgroundImage: {
        grid: "linear-gradient(rgba(34,211,238,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(34,211,238,0.06) 1px, transparent 1px)",
        "radial-glow": "radial-gradient(circle at 50% 0%, rgba(30,144,255,0.18), transparent 60%)",
      },
      keyframes: {
        "pulse-glow": {
          "0%, 100%": { opacity: "1", filter: "drop-shadow(0 0 6px currentColor)" },
          "50%": { opacity: "0.55", filter: "drop-shadow(0 0 2px currentColor)" },
        },
        scanline: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" },
        },
        "spin-slow": { to: { transform: "rotate(360deg)" } },
        marquee: { "0%": { transform: "translateX(0)" }, "100%": { transform: "translateX(-50%)" } },
        flicker: { "0%,100%": { opacity: "1" }, "92%": { opacity: "1" }, "94%": { opacity: "0.4" }, "96%": { opacity: "1" } },
      },
      animation: {
        "pulse-glow": "pulse-glow 2.2s ease-in-out infinite",
        scanline: "scanline 6s linear infinite",
        "spin-slow": "spin-slow 28s linear infinite",
        marquee: "marquee 30s linear infinite",
        flicker: "flicker 4s linear infinite",
      },
    },
  },
  plugins: [],
};
