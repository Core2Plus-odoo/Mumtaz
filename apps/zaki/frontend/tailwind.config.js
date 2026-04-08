/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        zaki: {
          bg:      'var(--zaki-bg)',
          surface: 'var(--zaki-surface)',
          card:    'var(--zaki-card)',
          border:  'var(--zaki-border)',
          text:    'var(--zaki-text)',
          muted:   'var(--zaki-muted)',
          accent:  '#7c3aed',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
