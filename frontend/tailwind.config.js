/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', "-apple-system", "BlinkMacSystemFont", "sans-serif"],
      },
      colors: {
        kc: {
          bg: "#F8F7F4",
          surface: "#FFFFFF",
          surfaceAlt: "#F2F1EE",
          border: "#E5E3DE",
          borderLight: "#EEEDEA",
          text: "#1A1F36",
          textSec: "#6B7280",
          textTri: "#9CA3AF",
          textInv: "#FFFFFF",
          brand: "#1A1F36",
          accent: "#0D9488",
          accentHover: "#0F766E",
          accentLight: "#F0FDFA",
          accentMid: "#CCFBF1",
          danger: "#DC2626",
          dangerBg: "#FEF2F2",
        },
        member: {
          maria: "#E84393",
          thomas: "#3B82F6",
          luisa: "#F59E0B",
          felix: "#10B981",
        },
      },
      borderRadius: {
        sm: "8px",
        md: "12px",
        lg: "16px",
        xl: "20px",
        "2xl": "24px",
      },
      boxShadow: {
        sm: "0 1px 3px rgba(0,0,0,0.04)",
        md: "0 2px 8px rgba(0,0,0,0.06)",
        lg: "0 4px 16px rgba(0,0,0,0.08)",
        card: "0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.02)",
      },
      keyframes: {
        kcPop: {
          "0%": { transform: "scale(0.5)" },
          "70%": { transform: "scale(1.1)" },
          "100%": { transform: "scale(1)" },
        },
        kcPulse: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
        kcSpin: {
          from: { transform: "rotate(0deg)" },
          to: { transform: "rotate(360deg)" },
        },
        kcFadeUp: {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        kcPop: "kcPop 400ms ease forwards",
        kcPulse: "kcPulse 1.5s ease-in-out infinite",
        kcSpin: "kcSpin 800ms linear infinite",
        kcFadeUp: "kcFadeUp 350ms ease forwards",
      },
    },
  },
  plugins: [],
};
