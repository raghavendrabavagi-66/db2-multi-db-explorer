/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#faf8ff",
        surface: "#faf8ff",
        primary: "#004ac6",
        "primary-container": "#2563eb",
        "on-primary": "#ffffff",
        "on-surface": "#131b2e",
        secondary: "#505f76",
        outline: "#737686",
        "outline-variant": "#c3c6d7",
        "surface-container": "#eaedff",
        "surface-container-low": "#f2f3ff",
        "surface-container-lowest": "#ffffff",
        "error-container": "#ffdad6",
        "on-error-container": "#93000a",
      },
      fontFamily: {
        sans: ["Fira Sans", "system-ui", "sans-serif"],
        mono: ["Fira Code", "monospace"],
      },
    },
  },
  plugins: [],
};
