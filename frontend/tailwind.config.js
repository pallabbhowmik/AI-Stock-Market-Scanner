/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        buy: "#16a34a",
        sell: "#dc2626",
        hold: "#eab308",
        accent: "#3b82f6",
        surface: "#1e293b",
        background: "#0f172a",
      },
    },
  },
  plugins: [],
};
