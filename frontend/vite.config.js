import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,                 // listen on all interfaces
    port: 5173,
    allowedHosts: 'all'         // allow connections from Wi-Fi devices
  }
})
