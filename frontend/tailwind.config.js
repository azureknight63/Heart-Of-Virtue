/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f0fdf4',
          100: '#dcfce7',
          500: '#22c55e',
          600: '#16a34a',
          700: '#15803d',
          800: '#166534',
          900: '#145231',
        },
        dark: {
          900: '#0a0a0a',
          800: '#1a1a2e',
          700: '#16213e',
          600: '#0f3460',
        },
        accent: {
          orange: '#ff6600',
          cyan: '#00ccff',
          lime: '#00ff88',
        }
      },
      fontFamily: {
        mono: ['Courier New', 'monospace', 'Noto Color Emoji'],
        serif: ['EB Garamond', 'serif'],
      }
    },
  },
  plugins: [],
}
