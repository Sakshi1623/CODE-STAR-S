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
          bg: '#0F172A',
          sidebar: '#1E293B',
          card: '#1E293B',
          cardSubtle: '#182234',
          accent: '#5B8C9E',
          accentLight: '#7BA6B6',
          accentDark: '#446A78',
          border: '#334155',
          borderSubtle: '#283548',
          success: '#0D9488',
          successBg: 'rgba(13, 148, 136, 0.15)',
          warning: '#F59E0B',
          warningBg: 'rgba(245, 158, 11, 0.15)',
          error: '#EF4444',
          errorBg: 'rgba(239, 68, 68, 0.15)',
          text: '#F8FAFC',
          textMuted: '#94A3B8',
          textSubtle: '#64748B',
        }
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
