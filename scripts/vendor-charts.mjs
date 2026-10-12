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
for (const [src,dst] of [
  ['fullcalendar/index.global.min.js','fullcalendar.js'],
  ['fullcalendar/LICENSE.md','LICENSE.fullcalendar'],
  ['@fullcalendar/core/locales/zh-cn.global.min.js','fullcalendar.zh-cn.js'],
  ['@fullcalendar/core/LICENSE.md','LICENSE.fullcalendar-core'],
]) {
  await copyFile(new URL('../node_modules/'+src,import.meta.url),new URL(dst,dir));
}
console.log('Lightweight Charts 5.2.1 and FullCalendar 6.1.21 vendored locally with licenses.');
