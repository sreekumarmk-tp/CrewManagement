import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        maritime: {
          50: "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          300: "#93c5fd",
          400: "#60a5fa",
          500: "#3b82f6",
          600: "#1d4ed8",
          700: "#1e40af",
          800: "#1e3a8a",
          900: "#0f1b4d",
          950: "#060d2e",
        },
        ocean: {
          DEFAULT: "#0a1628",
          card: "#0d1f3c",
          border: "#1e3a5f",
          accent: "#00d4ff",
          glow: "#0099cc",
        },
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "spin-slow": "spin 3s linear infinite",
        "ping-slow": "ping 2s cubic-bezier(0, 0, 0.2, 1) infinite",
        glow: "glow 2s ease-in-out infinite alternate",
        flow: "flow 3s ease-in-out infinite",
      },
      keyframes: {
        glow: {
          "0%": { boxShadow: "0 0 5px #00d4ff40" },
          "100%": { boxShadow: "0 0 20px #00d4ff80, 0 0 40px #00d4ff40" },
        },
        flow: {
          "0%, 100%": { opacity: "0.5" },
          "50%": { opacity: "1" },
        },
      },
      backgroundImage: {
        "ocean-gradient": "linear-gradient(135deg, #0a1628 0%, #0d1f3c 50%, #0a1628 100%)",
        "card-gradient": "linear-gradient(135deg, rgba(13,31,60,0.9) 0%, rgba(10,22,40,0.95) 100%)",
        "accent-gradient": "linear-gradient(135deg, #00d4ff 0%, #0099cc 100%)",
        "success-gradient": "linear-gradient(135deg, #22c55e 0%, #16a34a 100%)",
        "warning-gradient": "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)",
        "danger-gradient": "linear-gradient(135deg, #ef4444 0%, #dc2626 100%)",
      },
    },
  },
  plugins: [],
};
export default config;
