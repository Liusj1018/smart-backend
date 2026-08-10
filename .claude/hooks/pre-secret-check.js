#!/usr/bin/env node
/**
 * PreToolUse Hook: Secret/Key Hardcoding Check
 *
 * Reads tool input from stdin, scans file content or command text for
 * hardcoded secrets (API keys, AWS keys, GitHub tokens, generic secrets).
 * Blocks the operation if any match is found.
 *
 * All output goes to stderr (console.error) to avoid polluting the
 * MCP stdio protocol. Exit code 1 blocks, 0 allows.
 */

const fs = require("fs");

// Secret patterns to detect
const SECRET_PATTERNS = [
  { name: "OpenAI/API Key", regex: /sk-[a-zA-Z0-9]{20,}/g },
  { name: "AWS Access Key", regex: /AKIA[A-Z0-9]{16}/g },
  { name: "GitHub Token", regex: /ghp_[a-zA-Z0-9]{36}/g },
  { name: "Generic api_key assignment", regex: /api_key\s*=\s*["'][^"']+["']/gi },
  { name: "Generic secret assignment", regex: /secret\s*=\s*["'][^"']+["']/gi },
  { name: "Generic password assignment", regex: /password\s*=\s*["'][^"']+["']/gi },
  { name: "Bearer token hardcoded", regex: /Bearer\s+[a-zA-Z0-9\-._~+/]+=*/g },
];

function readStdin() {
  try {
    return fs.readFileSync(0, "utf-8");
  } catch {
    return "";
  }
}

function isTestFile(filePath) {
  // Test files, seed scripts, and fixtures legitimately contain
  // fake passwords/tokens like password="testpass123" or Bearer test-token.
  // These are not real secrets and should not be blocked.
  return /(test|seed|demo|fixture|conftest|scripts[\\/])/i.test(filePath);
}

function extractText(input) {
  // input is the JSON object Claude Code passes via stdin
  // It contains tool_name and tool_input
  const parts = [];
  const filePath = input.tool_input?.path || "";

  // Skip secret scanning entirely for test/seed/fixture files
  if (filePath && isTestFile(filePath)) {
    return "";
  }

  if (input.tool_input) {
    // For Write: full file content
    if (typeof input.tool_input.content === "string") {
      parts.push(input.tool_input.content);
    }
    // For Edit/replace: ONLY scan new_str (the code being ADDED).
    // Do NOT scan old_str — when fixing a hardcoded secret by replacing it
    // with an environment variable, old_str contains the secret being removed.
    // Scanning old_str would block the fix itself, causing repeated failures.
    if (typeof input.tool_input.new_str === "string") {
      parts.push(input.tool_input.new_str);
    }
    // For Bash: command
    if (typeof input.tool_input.command === "string") {
      parts.push(input.tool_input.command);
    }
    // For diff content (replace_in_file SEARCH/REPLACE blocks).
    // Format:
    //   ------- SEARCH
    //   [old content]
    //   =======
    //   [new content]
    //   +++++++ REPLACE
    // Only scan the REPLACE/new content, not SEARCH/old content.
    if (typeof input.tool_input.diff === "string") {
      const blocks = input.tool_input.diff.split(/-{5,}\s*SEARCH/i);
      for (const block of blocks.slice(1)) {
        const afterEquals = block.split(/={5,}/i)[1];
        if (afterEquals) {
          const newContent = afterEquals.split(/\+{5,}\s*REPLACE/i)[0];
          if (newContent) parts.push(newContent);
        }
      }
    }
  }

  return parts.join("\n");
}

function main() {
  const raw = readStdin();
  if (!raw) {
    process.exit(0);
  }

  let input;
  try {
    input = JSON.parse(raw);
  } catch {
    // If not valid JSON, scan raw text anyway
    input = { tool_input: { content: raw } };
  }

  const text = extractText(input);
  if (!text) {
    process.exit(0);
  }

  const findings = [];

  for (const pattern of SECRET_PATTERNS) {
    pattern.regex.lastIndex = 0;
    let match;
    while ((match = pattern.regex.exec(text)) !== null) {
      // Mask the secret in output
      const found = match[0];
      const masked =
        found.length > 8
          ? found.substring(0, 4) + "****" + found.substring(found.length - 4)
          : "****";
      findings.push(`  [${pattern.name}] ${masked}`);
    }
  }

  if (findings.length > 0) {
    console.error("");
    console.error("╔══════════════════════════════════════════════════╗");
    console.error("║  🚫 SECRET CHECK FAILED — HARDCODED KEY DETECTED  ║");
    console.error("╚══════════════════════════════════════════════════╝");
    console.error("");
    console.error("The following potential secrets were found:");
    findings.forEach((f) => console.error(f));
    console.error("");
    console.error("Action blocked. Move secrets to environment variables or .env file.");
    console.error("Do NOT commit secrets to version control.");
    console.error("");
    process.exit(1);
  }

  process.exit(0);
}

main();