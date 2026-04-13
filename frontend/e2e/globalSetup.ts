import fs from "node:fs";
import path from "node:path";

/**
 * Remove the per-run data dir before Playwright launches the web servers.
 *
 * Without this, the test assertion "No projects yet" fails on the second
 * local run because the previous run's SQLite DB is still there.  In CI
 * each job is ephemeral so this is a belt-and-braces guard, but locally
 * it's what makes reruns deterministic.
 */
export default async function globalSetup(): Promise<void> {
  const dataDir = path.resolve(__dirname, "..", "e2e-data");
  if (fs.existsSync(dataDir)) {
    fs.rmSync(dataDir, { recursive: true, force: true });
  }
}
