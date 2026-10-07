import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const appRoot = fileURLToPath(new URL('..', import.meta.url));
const dist = path.join(appRoot, 'dist');
const origin = 'https://news.thetickbase.com';
const routes = ['events', 'topics', 'raw', 'about', 'status', 'support', 'app'];
const labels = {
  en: ['Events', 'Topics', 'Raw Source Feed', 'About', 'Status', 'Support', 'Mobile App'],
  'zh-Hant': ['事件', '主題', '原始資料源', '關於', '狀態', '支援', '行動 App'],
  ja: ['イベント', 'トピック', '元情報', '概要', '稼働状況', 'サポート', 'モバイルアプリ'],
  th: ['เหตุการณ์', 'หัวข้อ', 'แหล่งข้อมูล', 'เกี่ยวกับ', 'สถานะ', 'ช่วยเหลือ', 'แอปมือถือ'],
};
const descriptions = {
  en: 'Public-safe summaries of market-moving gold, macroeconomic, and geopolitical events.',
  'zh-Hant': '追蹤影響黃金市場的宏觀經濟與地緣政治事件，閱讀可公開的消息摘要。',
  ja: '金市場に影響するマクロ経済・地政学イベントの公開要約を確認できます。',
  th: 'สรุปเหตุการณ์เศรษฐกิจมหภาคและภูมิรัฐศาสตร์ที่อาจส่งผลต่อตลาดทองคำ',
};
const appDescriptions = {
  en: 'TheTickBase News mobile app: news, source references, reading preferences and News Pro daily digests. App Store and Google Play downloads coming soon.',
  'zh-Hant': 'TheTickBase News 行動 App：閱讀新聞、多方來源、閱讀偏好與 News Pro 每日摘要。App Store 與 Google Play 下載即將推出。',
  ja: 'TheTickBase News モバイルアプリ。ニュース、情報源、閲覧設定、News Pro デイリーダイジェスト。App Store と Google Play で近日公開。',
  th: 'แอป TheTickBase News สำหรับอ่านข่าว ตรวจสอบแหล่งข่าว ตั้งค่าการอ่าน และสรุปรายวัน News Pro เร็ว ๆ นี้บน App Store และ Google Play',
};
const escapeHtml = (value) => value.replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;');
const template = await readFile(path.join(dist, 'index.html'), 'utf8');
const sitemap = await readFile(path.join(appRoot, 'public/sitemap.xml'), 'utf8');

for (const [locale, names] of Object.entries(labels)) {
  for (const [index, route] of routes.entries()) {
    const url = `${origin}/${locale}/${route}`;
    if (!sitemap.includes(`<loc>${url}</loc>`)) throw new Error(`Missing sitemap URL: ${url}`);

    const title = `${names[index]} · TickBase News`;
    const description = route === 'app' ? appDescriptions[locale] : descriptions[locale];
    const alternates = Object.keys(labels)
      .map((lang) => `<link rel="alternate" hreflang="${lang}" href="${origin}/${lang}/${route}" />`)
      .join('');
    const head = `<link rel="canonical" href="${url}" />${alternates}<link rel="alternate" hreflang="x-default" href="${origin}/en/${route}" /><meta property="og:type" content="website" /><meta property="og:url" content="${url}" /><meta property="og:image" content="${origin}/og.png" /><meta property="og:image:alt" content="TickBase News market event radar" /><meta name="twitter:card" content="summary_large_image" /><meta name="twitter:image" content="${origin}/og.png" />`;
    const html = template
      .replace(/<html lang="[^"]*">/, `<html lang="${locale}">`)
      .replace(/<title>[^<]*<\/title>/, `<title>${escapeHtml(title)}</title>`)
      .replace(/<meta\s+name="description"\s+content="[^"]*"\s*\/>/, `<meta name="description" content="${escapeHtml(description)}" />`)
      .replace(/<meta\s+property="og:title"\s+content="[^"]*"\s*\/>/, `<meta property="og:title" content="${escapeHtml(title)}" />`)
      .replace(/<meta\s+property="og:description"\s+content="[^"]*"\s*\/>/, `<meta property="og:description" content="${escapeHtml(description)}" />`)
      .replace('</head>', `${head}</head>`);

    const directory = path.join(dist, locale);
    await mkdir(directory, { recursive: true });
    await writeFile(path.join(directory, `${route}.html`), html);
  }
}

await writeFile(
  path.join(dist, 'index.html'),
  template.replace('</head>', '<meta name="robots" content="noindex, nofollow" /></head>'),
);
