/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        'risk-normal': '#FFFFFF',
        'risk-waspada': '#FFFF00',
        'risk-siaga': '#FF69B4',
        'risk-krisis': '#FF0000',
        'bi-blue-dark': '#003366',
        'bi-blue-mid': '#336699',
        'bi-blue-light': '#4A90D9',
      },
      fontFamily: {
        sans: ["'IBM Plex Sans'", "'Segoe UI'", 'sans-serif'],
        mono: ["'IBM Plex Mono'", 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
};
