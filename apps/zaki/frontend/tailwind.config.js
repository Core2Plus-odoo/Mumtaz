/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        zaki: {
          bg:       '#08080f',
          surface:  '#0f0f1a',
          card:     '#13131f',
          border:   '#1e1e30',
          accent:   '#7c3aed',
          'accent-2': '#5ea3ff',
          muted:    '#6b7280',
          text:     '#e5e7eb',
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
