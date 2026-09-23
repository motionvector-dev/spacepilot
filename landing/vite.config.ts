import { defineConfig } from 'vite';
import { readFileSync } from 'node:fs';

// Dev-mode stand-in for the /api/registry-stats serverless fn. Prod serves
// api/registry-stats.js directly on Vercel; dev has no runtime, so we read
// the same snapshot file here.
const registryStats = () => ({
  name: 'registry-stats-dev',
  configureServer(server) {
    server.middlewares.use('/api/registry-stats', (req, res) => {
      const snapshot = JSON.parse(
        readFileSync('public/registry-snapshot.json', 'utf8'),
      );
      const variants = snapshot.models.reduce((n, m) => n + (m.variants?.length || 0), 0);
      const flown = snapshot.models.reduce(
        (n, m) => n + (m.variants || []).filter((v) => (v.speed || []).length).length,
        0,
      );
      res.setHeader('Content-Type', 'application/json');
      res.setHeader('Access-Control-Allow-Origin', '*');
      res.end(JSON.stringify({
        generated: snapshot.generated, models: snapshot.models.length, variants, flown,
      }));
    });
  },
});

export default defineConfig({
  // The page is self-contained static HTML/CSS/inline JS — nothing to
  // bundle. Vite just processes index.html and copies public/ verbatim.
  assetsInlineLimit: 0,
  plugins: [registryStats()],
});
