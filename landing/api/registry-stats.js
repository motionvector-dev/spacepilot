// Serverless endpoint that reads the committed registry snapshot so the
// landing footer stat is generated from the same file SpacePilot serves,
// not hand-written. Updated by the CI hook whenever the registry moves.
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
let cached = null;

function load() {
  if (!cached) {
    cached = JSON.parse(
      readFileSync(join(HERE, '..', 'public', 'registry-snapshot.json'), 'utf8'),
    );
  }
  return cached;
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Cache-Control', 'public, max-age=3600');
  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'GET') return res.status(405).json({ error: 'GET only' });
  try {
    const d = load();
    const variants = d.models.reduce((n, m) => n + (m.variants?.length || 0), 0);
    const flown = d.models.reduce(
      (n, m) => n + (m.variants || []).filter((v) => (v.speed || []).length).length,
      0,
    );
    return res.status(200).json({
      generated: d.generated,
      models: d.models.length,
      variants,
      flown,
    });
  } catch (e) {
    return res.status(500).json({ error: 'registry snapshot missing' });
  }
}
