import { defineConfig } from 'vite';

export default defineConfig({
  build: {
    // The page is self-contained static HTML/CSS/inline JS — nothing to
    // bundle. Vite just processes index.html and copies public/ verbatim.
    assetsInlineLimit: 0,
  },
});
