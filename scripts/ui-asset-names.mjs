import { createHash } from 'node:crypto';
import path from 'node:path';
export function fingerprint(name, bytes) {
  const parsed = path.parse(name);
  return `${parsed.name}-${createHash('sha256').update(bytes).digest('hex').slice(0, 16)}${parsed.ext}`;
}
export function assetFileNames(asset) {
  const name = asset.names?.[0] || asset.name;
  return name.endsWith('.css') ? 'assets/[name]-[hash][extname]' : `assets/${fingerprint(name, asset.source)}`;
}
