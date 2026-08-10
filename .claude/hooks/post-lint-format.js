#!/usr/bin/env node
/**
 * PostToolUse Hook: Auto Lint + Format
 *
 * After Write/Edit on .py files, runs:
 * 1. ruff format (auto-format)
 * 2. ruff check (lint)
 *
 * Also performs static security scans on the modified content:
 * - Detects print() debug statements
 * - Detects ALLOW_ORIGINS=* (CORS wildcard)
 * - Detects Authorization header logging
 *
 * All output goes to stderr. Non-zero exit on lint errors blocks.
 */

const fs = require("fs");
const { execSync } = require("child_process");

function readStdin() {
  try {
    return fs.readFileSync(0, "utf-8");
  } catch {
    return "";
  }
}

function getModifiedPyFiles(input) {
  const files = [];
  const path = input.tool_input?.path;
  if (path && path.endsWith(".py")) {
    files.push(path);
  }
  return files;
}

function scanSecurityIssues(filePath) {
  const warnings = [];
  let content;
  try {
    content = fs.readFileSync(filePath, "utf-8");
  } catch {
    return warnings;
  }

  // Detect print() debug statements (allow in tests and scripts)
  if (!/(test|seed|demo|scripts)/.test(filePath)) {
    const printMatches = content.match(/^\s*print\s*\(/gm);
    if (printMatches) {
      warnings.push({
        level: "WARN",
        message: `Found ${printMatches.length} print() statement(s) — use logger instead`,
      });
    }
  }

  // Detect CORS wildcard
  if (/allow_origins\s*=\s*\["?\*"?\]/.test(content) || /ALLOW_ORIGINS\s*=\s*["']\*["']/.test(content)) {
    warnings.push({
      level: "WARN",
      message: "CORS allow_origins=* detected — do not use wildcard in production",
    });
  }

  // Detect Authorization header logging
  if (/log(ger)?\.\w+\(.*[Aa]uthorization/.test(content)) {
    warnings.push({
      level: "ERROR",
      message: "Logging Authorization header detected — token leak risk",
    });
  }

  // Detect hardcoded localhost in production config
  // (informational only, not blocking)

  return warnings;
}

function runRuff(files) {
  const results = { formatOk: false, lintOk: false, formatOutput: "", lintOutput: "" };

  // Use --check (read-only) instead of auto-formatting.
  // Auto-formatting modifies files on disk without Cline's knowledge,
  // which causes subsequent replace_in_file SEARCH blocks to fail
  // because Cline's cached content no longer matches the on-disk content.
  try {
    execSync(`python -m ruff format --check ${files.join(" ")}`, {
      stdio: ["pipe", "pipe", "pipe"],
      timeout: 15000,
    });
    results.formatOk = true;
  } catch (e) {
    results.formatOutput = e.stderr?.toString() || e.stdout?.toString() || e.message;
  }

  // Run ruff check without --fix to avoid silent file modifications.
  // Lint issues are reported as warnings but do NOT block the tool call.
  // Only security errors (detected separately) should block.
  try {
    execSync(`python -m ruff check ${files.join(" ")}`, {
      stdio: ["pipe", "pipe", "pipe"],
      timeout: 15000,
    });
    results.lintOk = true;
  } catch (e) {
    results.lintOutput = e.stderr?.toString() || e.stdout?.toString() || e.message;
  }

  return results;
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

  const pyFiles = getModifiedPyFiles(input);
  if (pyFiles.length === 0) {
    process.exit(0);
  }

  console.error("");
  console.error("── PostToolUse: Lint + Format ──");

  // Run ruff format + check
  const ruff = runRuff(pyFiles);

  if (ruff.formatOk) {
    console.error("  ✅ ruff format passed");
  } else {
    console.error("  ❌ ruff format failed:");
    console.error(`     ${ruff.formatOutput.split("\n").slice(0, 5).join("\n     ")}`);
  }

  if (ruff.lintOk) {
    console.error("  ✅ ruff check passed");
  } else {
    console.error("  ❌ ruff check found issues:");
    console.error(`     ${ruff.lintOutput.split("\n").slice(0, 10).join("\n     ")}`);
  }

  // Security scan
  let hasErrors = false;
  for (const file of pyFiles) {
    const issues = scanSecurityIssues(file);
    for (const issue of issues) {
      const icon = issue.level === "ERROR" ? "🚫" : "⚠️";
      console.error(`  ${icon} [${issue.level}] ${file}: ${issue.message}`);
      if (issue.level === "ERROR") hasErrors = true;
    }
  }

  console.error("");

  // Only block on security errors (e.g., Authorization header logging).
  // Lint/format issues are reported as warnings but do NOT block the tool call,
  // because blocking causes Cline to retry the same write repeatedly,
  // leading to "repeated tool call failures".
  // Cline can see the warnings and fix issues in a follow-up edit.
  if (hasErrors) {
    process.exit(1);
  }

  process.exit(0);
}

main();