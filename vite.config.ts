import { defineConfig } from 'vite'
import { copyFileSync, mkdirSync, readdirSync, statSync } from 'fs'
import { join } from 'path'

// Recursively copies src → dest after vite build
function copyDirPlugin(src: string, dest: string) {
  return {
    name: 'copy-static-dir',
    closeBundle() {
      function copyDir(s: string, d: string) {
        mkdirSync(d, { recursive: true })
        for (const f of readdirSync(s)) {
          const sp = join(s, f)
          const dp = join(d, f)
          if (statSync(sp).isDirectory()) copyDir(sp, dp)
          else copyFileSync(sp, dp)
        }
      }
      copyDir(src, dest)
    }
  }
}

export default defineConfig({
  base: './',
  publicDir: 'public',
  build: {
    outDir: 'dist',
  },
  plugins: [
    // Copy darkfo/js, darkfo/lib, darkfo/lut, darkfo/ui.css to dist/darkfo/
    copyDirPlugin('darkfo/js',  'dist/darkfo/js'),
    copyDirPlugin('darkfo/lib', 'dist/darkfo/lib'),
    copyDirPlugin('darkfo/lut', 'dist/darkfo/lut'),
    {
      name: 'copy-darkfo-css',
      closeBundle() {
        mkdirSync('dist/darkfo', { recursive: true })
        copyFileSync('darkfo/ui.css', 'dist/darkfo/ui.css')
      }
    }
  ]
})
