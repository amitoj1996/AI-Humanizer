import { expect, test } from "@playwright/test";

/**
 * Happy path — project → document → type → detect → humanize → verify.
 *
 * Runs against the FakeRegistry-backed test server, so no real models
 * or Ollama instance are required.  The fakes return deterministic
 * shapes:
 *   - text containing "Moreover"/"Furthermore"   → 80% AI
 *   - otherwise                                  → 20% AI
 *   - rewrite strips those markers
 * which is enough to exercise all the UI branches.
 */

const AI_TEXT =
  "Artificial intelligence has fundamentally transformed the landscape of " +
  "modern technology. Moreover, it is important to note that AI systems " +
  "facilitate unprecedented efficiency. Furthermore, machine learning " +
  "algorithms have enhanced complex data-driven analysis.";

test("create project, create doc, detect AI text, humanize", async ({ page }) => {
  // Headlessly accept the native confirm() dialogs the app uses for
  // destructive actions — none of the happy path hits them, but being
  // defensive prevents test hangs if something changes.
  page.on("dialog", (d) => d.accept());

  await page.goto("/");

  // ----- Project creation -----
  // Confirm the empty state before the user creates anything
  await expect(page.getByText("No projects yet")).toBeVisible();

  await page.getByRole("button", { name: /\+ New$/ }).first().click();
  const projectInput = page.getByPlaceholder("Project name");
  await projectInput.fill("E2E Project");
  await projectInput.press("Enter");
  await expect(page.getByText("E2E Project")).toBeVisible();

  // ----- Document creation -----
  // The document "+ New" opens a native prompt(); Playwright handles it
  // via the dialog handler.
  page.once("dialog", (d) => d.accept("E2E Doc"));
  await page
    .getByRole("button", { name: /\+ New$/ })
    .last()
    .click();
  await expect(page.getByRole("heading", { name: "E2E Doc" })).toBeVisible();

  // ----- Type into editor -----
  const editor = page.getByPlaceholder("Paste your text here...");
  await editor.click();
  await editor.fill(AI_TEXT);
  await expect(page.getByText(/\d+ words/)).toBeVisible();

  // ----- Detection -----
  await page.getByRole("button", { name: "Detect AI Content" }).click();
  await expect(page.getByText(/AI-generated|Likely AI-generated/)).toBeVisible({
    timeout: 30_000,
  });

  // ----- Humanize -----
  await page.getByRole("button", { name: "Humanize" }).click();
  await expect(page.getByRole("button", { name: /Humanize Text/ })).toBeVisible();
  await page.getByRole("button", { name: "Humanize Text" }).click();

  // Result card appears with Before/After scores — the fake rewriter
  // strips "Moreover"/"Furthermore" so the after-text differs from input.
  await expect(page.getByText("Humanized Text")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/\d+% meaning preserved/)).toBeVisible();

  // Final Output should not contain the original AI markers
  const output = page.locator("text=Final Output").locator("..").locator("div").last();
  await expect(output).not.toContainText("Moreover,");
});


test("writing report modal opens and shows chain integrity", async ({ page }) => {
  page.on("dialog", (d) => d.accept());
  await page.goto("/");

  // Set up project + document
  await page.getByRole("button", { name: /\+ New$/ }).first().click();
  const nameInput = page.getByPlaceholder("Project name");
  await nameInput.fill("Report Project");
  await nameInput.press("Enter");

  page.once("dialog", (d) => d.accept("Report Doc"));
  await page.getByRole("button", { name: /\+ New$/ }).last().click();
  await expect(page.getByRole("heading", { name: "Report Doc" })).toBeVisible();

  // Type something so provenance has events to report on
  const editor = page.getByPlaceholder("Paste your text here...");
  await editor.fill("This is some typed content for the provenance report.");
  // Give the recorder its flush interval
  await page.waitForTimeout(2500);

  // Open Writing Report
  await page.getByRole("button", { name: /Writing Report/ }).click();
  await expect(page.getByText("Writing Process Report")).toBeVisible();
  await expect(page.getByText(/Chain verified|Chain broken/)).toBeVisible();
});
