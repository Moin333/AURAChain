/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
        heading: ['DM Sans', 'sans-serif'],
      },
      colors: {
        primary: {
          DEFAULT: '#4A90E2',
          50: '#EFF6FF',
          100: '#DBEAFE',
          200: '#BFDBFE',
          300: '#93C5FD',
          400: '#60A5FA',
          500: '#4A90E2',
          600: '#3B73B8',
          700: '#2C568A',
          800: '#1D395C',
          900: '#0E1C2E',
        },
        accent: {
          teal: '#14B8A6',
          amber: '#F59E0B',
          coral: '#EF4444',
          slate: '#64748B',
        },
        // Professional Light Mode Colors
        light: {
          bg: '#FAFAFA',
          surface: '#F5F5F5',
          elevated: '#FFFFFF',
          border: '#E5E5E5',
          text: {
            primary: '#18181B',
            secondary: '#52525B',
            tertiary: '#A1A1AA',
          }
        },
        // Professional Dark Mode Colors (NOT pure black)
        dark: {
          bg: '#0A0A0A',        // Main background
          surface: '#121212',    // Elevated surfaces
          elevated: '#1A1A1A',   // Cards, modals
          panel: '#1F1F1F',      // Side panels
          border: '#27272A',     // Borders (zinc-800)
          text: {
            primary: '#FAFAFA',  // Main text
            secondary: '#A1A1AA', // Secondary text
            tertiary: '#71717A', // Muted text
          }
        },
      },
      boxShadow: {
        'sm-light': '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        'sm-dark': '0 1px 2px 0 rgba(0, 0, 0, 0.5)',
        'md-light': '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
        'md-dark': '0 4px 6px -1px rgba(0, 0, 0, 0.6)',
        'lg-light': '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
        'lg-dark': '0 10px 15px -3px rgba(0, 0, 0, 0.7)',
        'xl-light': '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
        'xl-dark': '0 20px 25px -5px rgba(0, 0, 0, 0.8)',
      },
      animation: {
        'slide-in': 'slideIn 300ms cubic-bezier(0.4, 0, 0.2, 1)',
        'rotate-alternate': 'rotateAlternate 2s cubic-bezier(0.4, 0, 0.2, 1) infinite',
        'fade-in': 'fadeIn 0.3s ease-out',
        'fade-in-up': 'fadeInUp 0.3s ease-out',
      },
      keyframes: {
        slideIn: {
          '0%': { transform: 'translateX(100%)' },
          '100%': { transform: 'translateX(0)' },
        },
        rotateAlternate: {
          '0%': { transform: 'rotate(0deg) scale(1)' },
          '25%': { transform: 'rotate(180deg) scale(1.05)' },
          '50%': { transform: 'rotate(180deg) scale(1)' },
          '75%': { transform: 'rotate(0deg) scale(1.05)' },
          '100%': { transform: 'rotate(0deg) scale(1)' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' }
        },
        fadeInUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' }
        }
      }
    },
  },
  plugins: [],
}