import { resolve } from 'path'
import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    port: 5173,
  },
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        login: resolve(__dirname, 'login.html'),
        library: resolve(__dirname, 'library.html'),
        record: resolve(__dirname, 'record.html'),
        recipeDetail: resolve(__dirname, 'recipe-detail.html'),
        cookMode: resolve(__dirname, 'cook-mode.html'),
        profile: resolve(__dirname, 'profile.html'),
      },
    },
  },
})
