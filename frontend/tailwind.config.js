/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ops: {
          950: "#070b12",
          900: "#0b1220",
          850: "#0e1726",
          800: "#121c2e",
          700: "#1a2740",
          600: "#243352",
          400: "#7d8da8",
          300: "#a8b4c7",
        },
        cyan: {
          signal: "#3ec7ff",
        },
      },
      fontFamily: {
        sans: ["IBM Plex Sans", "Segoe UI", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "Consolas", "monospace"],
      },
      boxShadow: {
        panel: "0 8px 28px rgba(0, 0, 0, 0.45)",
      },
    },
  },
  plugins: [],
};
