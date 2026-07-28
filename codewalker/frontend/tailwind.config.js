/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#000000",
        panel: "#0e0e11",
        panel2: "#151519",
        hairline: "#232228",
        hairlineSoft: "#19191d",
        paper: "#edeeea",
        slate: "#8d8d95",
        slateDim: "#5c5c62",
        signal: "#d6923a",
        signalBright: "#e8ab5c",
        err: "#c96a52",
      },
      fontFamily: {
        display: ["'Space Grotesk'", "sans-serif"],
        sans: ["'Inter'", "sans-serif"],
        mono: ["'IBM Plex Mono'", "monospace"],
      },
    },
  },
  plugins: [],
};
