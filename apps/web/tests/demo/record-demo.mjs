// Records docs/demo/inbox-to-reply.mp4: one job from the inbox to an approved proposal to a client reply.
// Start the API (stand-in models) and the built web app first, then:  node tests/demo/record-demo.mjs /tmp/frames
// It saves a frame about five times a second; join them with:  ffmpeg -framerate 4.6 -i /tmp/frames/%05d.jpg -pix_fmt yuv420p out.mp4
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const dir = process.argv[2] ?? "/tmp/frames";
mkdirSync(dir, { recursive: true });
const browser = await chromium.launch({ channel: "chrome" });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
const page = await ctx.newPage();
let on = true, i = 0;
const loop = (async () => {
  while (on) {
    try { await page.screenshot({ path: `${dir}/${String(i++).padStart(5, "0")}.jpg`, type: "jpeg", quality: 72 }); } catch {}
    await new Promise((r) => setTimeout(r, 180));
  }
})();
const pause = (ms = 1400) => page.waitForTimeout(ms);
try {
  await page.goto("http://localhost:3000/login"); await pause();
  await page.getByLabel("User name").pressSequentially("reviewer", { delay: 60 });
  await page.getByLabel("Password").pressSequentially("reviewer", { delay: 60 });
  await page.getByTestId("submit-auth").click();
  await page.getByTestId("job-row").first().waitFor(); await pause(2000);
  await page.getByTestId("analyse-new").click();
  await page.getByTestId("open-studio").first().waitFor({ timeout: 20000 }); await pause(2500);
  await page.getByTestId("analyse-new").click(); await pause(3500);
  let replied = false;
  for (let round = 0; round < 5 && !replied; round++) {   // approve drafts until a simulated client replies
    await page.goto("http://localhost:3000/inbox");
    await page.getByTestId("open-studio").first().waitFor({ timeout: 10000 }); await pause(round ? 800 : 1500);
    if (round === 0) {
      const row = page.getByTestId("job-row").filter({ has: page.getByTestId("open-studio") }).first();
      await row.getByRole("link", { name: "Open", exact: true }).click();
      await page.getByRole("heading", { name: "Requirements and the evidence that proves them" }).waitFor(); await pause(2000);
      await page.mouse.wheel(0, 500); await pause(2500); await page.mouse.wheel(0, -500); await pause(800);
      await page.getByRole("link", { name: "Review draft" }).click();
    } else {
      await page.getByTestId("open-studio").first().click();
    }
    await page.getByTestId("draft-view").waitFor(); await pause(round ? 900 : 1500);
    await page.getByTestId("claim").first().hover(); await pause(round ? 1200 : 3000);
    await page.mouse.move(900, 600); await pause(600);
    await page.getByTestId("approve").scrollIntoViewIfNeeded(); await pause(900);
    await page.getByTestId("approve").click();
    await page.getByTestId("submitted-note").waitFor({ timeout: 20000 }); await pause(1800);
    await page.goto("http://localhost:3000/pipeline"); await page.getByTestId("pipeline-card").first().waitFor(); await pause(2200);
    await page.goto("http://localhost:3000/messages"); await pause(2000);
    replied = await page.getByTestId("suggest").first().isVisible();
  }
  if (replied) {
    await page.getByTestId("suggest").first().click(); await page.getByTestId("approve").first().waitFor({ timeout: 20000 }); await pause(3500);
    await page.getByTestId("approve").first().click(); await pause(4000);
    console.log("client reply approved");
  } else console.log("no client replied in this run");
  await page.goto("http://localhost:3000/analytics"); await pause(3000);
} catch (e) { console.log("ERR", String(e).slice(0, 400)); }
on = false; await loop; await ctx.close(); await browser.close();
console.log("frames", i);
