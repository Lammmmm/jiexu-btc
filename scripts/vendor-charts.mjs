import { mkdir, copyFile, access } from 'node:fs/promises';
const dir = new URL('../frontend/vendor/', import.meta.url);
await mkdir(dir,{recursive:true});
for (const [src,dst] of [
  ['dist/lightweight-charts.standalone.production.js','lightweight-charts.js'],
  ['LICENSE','LICENSE.lightweight-charts'],
]) {
  await copyFile(new URL('../node_modules/lightweight-charts/'+src,import.meta.url),new URL(dst,dir));
}
// Official v5.2.1 NOTICE is committed locally (npm distribution omits it).
await access(new URL('NOTICE.lightweight-charts',dir));
console.log('Lightweight Charts 5.2.1 vendored locally, with license and notice.');
