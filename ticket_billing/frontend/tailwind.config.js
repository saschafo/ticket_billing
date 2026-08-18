/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: 'var(--color-primary)',
          50:  'color-mix(in srgb, var(--color-primary) 8%, white)',
          100: 'color-mix(in srgb, var(--color-primary) 15%, white)',
          200: 'color-mix(in srgb, var(--color-primary) 30%, white)',
          300: 'color-mix(in srgb, var(--color-primary) 50%, white)',
          400: 'color-mix(in srgb, var(--color-primary) 70%, white)',
          500: 'color-mix(in srgb, var(--color-primary) 85%, white)',
          600: 'var(--color-primary)',
          700: 'color-mix(in srgb, var(--color-primary) 80%, black)',
          800: 'color-mix(in srgb, var(--color-primary) 60%, black)',
          900: 'color-mix(in srgb, var(--color-primary) 40%, black)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
