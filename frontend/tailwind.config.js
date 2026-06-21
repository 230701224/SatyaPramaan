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
        brand: {
          base: '#030712',
          surface: '#0b0f19',
          card: 'rgba(15, 23, 42, 0.65)',
          border: 'rgba(51, 65, 85, 0.5)',
          primary: '#8b5cf6',
          secondary: '#6366f1',
          success: '#10b981',
          warning: '#f97316',
          danger: '#ef4444',
          info: '#0ea5e9',
        }
      },
      backdropBlur: {
        xs: '2px',
      }
    },
  },
  plugins: [],
}
