/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        solar: {
          50: '#fffbe6',
          100: '#fff3b3',
          200: '#ffe880',
          300: '#ffd94d',
          400: '#ffca1a',
          500: '#f59e0b',
          600: '#d97706',
          700: '#b45309',
          800: '#92400e',
          900: '#78350f',
        },
        surface: {
          1: '#f1f5f9',
          2: '#ffffff',
          3: '#f8fafc',
        },
        accent: {
          DEFAULT: '#6366f1',
          light: '#818cf8',
          muted: '#4f46e5',
        },
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      borderRadius: {
        xl: '12px',
        '2xl': '16px',
      },
      animation: {
        'ping-slow': 'ping 2s cubic-bezier(0, 0, 0.2, 1) infinite',
        'fade-slide-up': 'fadeSlideUp 0.3s ease forwards',
      },
    },
  },
  plugins: [],
};
