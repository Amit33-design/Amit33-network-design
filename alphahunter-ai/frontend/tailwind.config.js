/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0b3d2e",
        alpha: "#1b7f4b",
        dip: "#1f5fa6",
      },
    },
  },
  plugins: [],
};
