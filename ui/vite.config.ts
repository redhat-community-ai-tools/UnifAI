import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import themePlugin from "@replit/vite-plugin-shadcn-theme-json";
import path from "path";
import runtimeErrorOverlay from "@replit/vite-plugin-runtime-error-modal";
import { visualizer } from 'rollup-plugin-visualizer'; // Import the build analyzer plugin

export default defineConfig({
  plugins: [
    react(),
    runtimeErrorOverlay(),
    themePlugin(),
    ...(process.env.NODE_ENV !== "production" &&
    process.env.REPL_ID !== undefined
      ? [
          await import("@replit/vite-plugin-cartographer").then((m) =>
            m.cartographer(),
          ),
        ]
      : []),
      process.env.NODE_ENV !== "production" && visualizer({
        open: true, // Automatically opens the report in your browser after build
        filename: 'bundle-report.html', // Name of the generated report file
        gzipSize: true, // Show sizes after gzip compression
        brotliSize: true, // Show sizes after brotli compression (if available)
    }),
  ],
  server: {
    port: 5173, // Or whatever port Vite is running on by default
    proxy: {
      // Proxy for api1
      '/api1': {
        target: process.env.DATAPIPELINEHUB_HOST,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api1/, '/api'), // This rewrites /api1 to /api
        secure: false, // Set to true for production if target is HTTPS and has valid cert.
                       // Set to false for dev if you're getting SSL errors with self-signed or invalid certs.
      },
      // Proxy for api2 (assuming this is still local or another service)
      '/api2': {
        target: process.env.MULTIAGENT_HOST,//'http://127.0.0.1:13457', // Your second backend
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api2/, '/api'), // This rewrites /api2 to nothing
        // secure: false, // Only needed if this target is HTTPS and you have SSL issues
      },
      // You can add more proxies here if needed
    }
  },

  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "client", "src"),
      "@shared": path.resolve(import.meta.dirname, "shared"),
      "@assets": path.resolve(import.meta.dirname, "attached_assets"),
    },
  },
  root: path.resolve(import.meta.dirname, "client"),
  build: {
    outDir: path.resolve(import.meta.dirname, "build"),
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules') && id.includes('react')) {
            return 'react-vendor'; // Separate React/ReactDOM
          }
          if (id.includes('node_modules')) {
            return 'vendor'; // Other node_modules
          }
        },
      },
    },
  },
});