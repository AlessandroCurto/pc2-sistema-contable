/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// La app se publica en GitHub Pages bajo /<repositorio>/.
// BASE_URL se pasa desde el flujo de despliegue; en local queda en '/'.
export default defineConfig({
  plugins: [react()],
  base: process.env.BASE_URL ?? '/',
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.test.{ts,tsx}'],
  },
});
