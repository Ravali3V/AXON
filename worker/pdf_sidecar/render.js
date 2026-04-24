#!/usr/bin/env node
/**
 * AXON PDF sidecar — reads HTML from stdin, writes PDF to stdout.
 *
 * Why a Node sidecar: Puppeteer is Node-only. Spawning it from Python keeps the
 * rendering cleanly separated from the scraper's Playwright browser pool so PDFs
 * don't compete for the same Chromium instance.
 *
 * Usage (from the Python worker):
 *   echo "<html>...</html>" | node render.js > out.pdf
 */
const puppeteer = require("puppeteer");

async function readStdin() {
  return new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => (data += chunk));
    process.stdin.on("end", () => resolve(data));
    process.stdin.on("error", reject);
  });
}

(async () => {
  const html = await readStdin();
  if (!html || html.length < 10) {
    process.stderr.write("render.js: empty HTML on stdin\n");
    process.exit(1);
  }

  const browser = await puppeteer.launch({
    headless: "new",
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  try {
    const page = await browser.newPage();
    await page.setContent(html, { waitUntil: "domcontentloaded" });
    const pdf = await page.pdf({
      format: "Letter",
      printBackground: true,
      margin: { top: "0.6in", bottom: "0.6in", left: "0.5in", right: "0.5in" },
    });
    process.stdout.write(pdf);
  } finally {
    await browser.close();
  }
})().catch((err) => {
  process.stderr.write(`render.js failed: ${err && err.stack ? err.stack : err}\n`);
  process.exit(1);
});
