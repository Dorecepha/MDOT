/**
 * Re-encode extracted PNG assets to WebP at sane display sizes.
 *
 * The sheet embeds portraits at 500x500 and gift icons at 120x120+ regardless
 * of how small they render, which is the bulk of the 226 MB problem. Each
 * category is capped at roughly 2x its on-page size for retina, then encoded
 * to WebP. The source PNG is removed once a WebP exists.
 *
 * Usage: node tools/optimise.mjs <site_dir>
 */
import { readdir, stat, unlink } from 'node:fs/promises';
import path from 'node:path';
import sharp from 'sharp';

// on-page size -> cap at 2x for retina
const CAPS = {
  identities: 400, // cards render ~236px wide
  gifts: 128,      // chips render 46px
  avatars: 128,    // footage avatars render 44px
  banners: 480,
  status: 96,
};

const siteDir = process.argv[2] ?? 'site';
const assetsDir = path.join(siteDir, 'assets');

async function dirSize(dir) {
  let total = 0;
  for (const entry of await readdir(dir, { withFileTypes: true, recursive: true })) {
    if (entry.isFile()) {
      total += (await stat(path.join(entry.parentPath ?? entry.path, entry.name))).size;
    }
  }
  return total;
}

const before = await dirSize(assetsDir);
let converted = 0;
let skipped = 0;

for (const category of await readdir(assetsDir)) {
  const dir = path.join(assetsDir, category);
  if (!(await stat(dir)).isDirectory()) continue;
  const cap = CAPS[category] ?? 256;

  for (const file of await readdir(dir)) {
    if (!file.endsWith('.png')) continue;
    const src = path.join(dir, file);
    const dest = src.replace(/\.png$/, '.webp');
    try {
      await sharp(src)
        .resize({ width: cap, height: cap, fit: 'inside', withoutEnlargement: true })
        .webp({ quality: 82, effort: 5 })
        .toFile(dest);
      await unlink(src);
      converted++;
    } catch (err) {
      console.warn(`  skip ${category}/${file}: ${err.message}`);
      skipped++;
    }
  }
}

const after = await dirSize(assetsDir);
const mb = (n) => (n / 1e6).toFixed(1);
console.log(`converted ${converted} files (${skipped} skipped)`);
console.log(`assets: ${mb(before)} MB -> ${mb(after)} MB  (${(100 * (1 - after / before)).toFixed(1)}% smaller)`);
