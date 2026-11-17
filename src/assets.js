// Vite owns every UI asset URL so changed bytes receive a new immutable name.
const urls = import.meta.glob('/src/assets/*', { eager: true, query: '?url', import: 'default' });
export function asset(name) {
  const url = urls[`/src/assets/${name}`];
  if (!url) throw new Error(`Unknown UI asset: ${name}`);
  return url;
}
