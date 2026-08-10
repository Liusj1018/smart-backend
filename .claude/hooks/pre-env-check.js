#!/usr/bin/env node
/**
 * PreToolUse Hook: .env File Write Protection
 *
 * Prevents writing/editing .env files directly through AI tools.
 * .env files contain secrets and should never be created or modified
 * by automated tooling. Use .env.example as a template instead.
 *
 * All output goes to stderr. Exit code 1 blocks, 0 allows.
 */

const fs = require("fs");

function readStdin() {
  try {
    return fs.readFileSync(0, "utf-8");
  } catch {
    return "";
  }
}

function main() {
  const raw = readStdin();
  if (!raw) process.exit(0);

  let input;
  try {
    input = JSON.parse(raw);
  } catch {
    process.exit(0);
  }

  const filePath = input.tool_input?.path || "";

  // Normalize path separators for cross-platform
  const normalized = filePath.replace(/\\/g, "/");

  // Block .env files but allow .env.example, .env.template, .env.sample
  const isEnvFile = /(^|\/)\.env(\..+)?$/.test(normalized);
  const isEnvExample = /(^|\/)\.env\.(example|template|sample)$/.test(normalized);

  if (isEnvFile && !isEnvExample) {
    console.error("");
    console.error("╔══════════════════════════════════════════════════╗");
    console.error("║  🚫 .ENV FILE WRITE BLOCKED                       ║");
    console.error("╚══════════════════════════════════════════════════╝");
    console.error("");
    console.error(`Path: ${filePath}`);
    console.error("");
    console.error("Writing .env files directly is blocked because they");
    console.error("contain secrets that must not be committed to git.");
    console.error("");
    console.error("To set up environment variables:");
    console.error("  1. Copy .env.example to .env manually");
    console.error("  2. Edit .env with your actual secrets");
    console.error("  3. Ensure .env is in .gitignore");
    console.error("");
    process.exit(1);
  }

  process.exit(0);
}

main();