/**
 * Build-time script that copies documentation from the repo root docs/
 * directory into frontend/content/docs/ so Next.js can read them at
 * build time via the filesystem.
 *
 * Run automatically via the "predev" and "prebuild" npm scripts.
 */
import { cpSync, mkdirSync, rmSync, existsSync, readdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = resolve(__dirname, "..");
const REPO_ROOT = resolve(FRONTEND_ROOT, "..");

const SOURCE = resolve(REPO_ROOT, "docs");
const DEST = resolve(FRONTEND_ROOT, "content", "docs");

// Clean previous copy
if (existsSync(DEST)) {
  rmSync(DEST, { recursive: true, force: true });
}

mkdirSync(DEST, { recursive: true });

// Copy all docs
cpSync(SOURCE, DEST, { recursive: true });

function countFiles(dir) {
  let n = 0;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) n += countFiles(resolve(dir, entry.name));
    else n++;
  }
  return n;
}

console.log(`[copy-docs] Copied ${countFiles(DEST)} files from docs/ → frontend/content/docs/`);
