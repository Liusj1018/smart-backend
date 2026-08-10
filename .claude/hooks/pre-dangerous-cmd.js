#!/usr/bin/env node
/**
 * PreToolUse Hook: Dangerous Command Check
 *
 * Scans Bash commands for destructive operations such as:
 * - rm -rf on critical directories (alembic/, app/, migrations/)
 * - DROP TABLE / DROP DATABASE SQL
 * - git push --force to main/master
 * - --no-verify to bypass hooks
 * - chmod 777
 * - curl | sh (pipe to shell)
 *
 * All output goes to stderr. Exit code 1 blocks, 0 allows.
 */

const fs = require("fs");

const DANGEROUS_PATTERNS = [
  {
    name: "Force delete migration files",
    regex: /rm\s+(-[a-z]*r[a-z]*f[a-z]*\s+|-\S*f\S*\s+)(alembic|migrations|app)\b/i,
  },
  {
    name: "Force delete project root",
    regex: /rm\s+(-[a-z]*r[a-z]*f[a-z]*\s+|-\S*f\S*\s+)(\.|\/|\*)/i,
  },
  {
    name: "DROP TABLE/DATABASE",
    regex: /DROP\s+(TABLE|DATABASE|SCHEMA)\s+/i,
  },
  {
    name: "Bypass git hooks with --no-verify",
    regex: /--no-verify/i,
  },
  {
    name: "Force push to main/master",
    regex: /git\s+push\s+(-f\s+|--force\s+).*\b(main|master)\b/i,
  },
  {
    name: "Insecure permissions chmod 777",
    regex: /chmod\s+(-R\s+)?777/i,
  },
  {
    name: "Pipe curl/wget to shell",
    regex: /(curl|wget)\s+[^|]*\|\s*(sh|bash|zsh)/i,
  },
  {
    name: "Delete all Docker volumes",
    regex: /docker\s+.*down\s+(-v\b|--volumes\b)/i,
  },
  {
    name: "Git reset --hard on remote branch",
    regex: /git\s+reset\s+--hard\s+(origin\/|upstream\/)/i,
  },
];

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

  const command = input.tool_input?.command || "";
  if (!command) process.exit(0);

  const findings = [];
  for (const pattern of DANGEROUS_PATTERNS) {
    if (pattern.regex.test(command)) {
      findings.push(`  [${pattern.name}]`);
    }
  }

  if (findings.length > 0) {
    console.error("");
    console.error("╔══════════════════════════════════════════════════╗");
    console.error("║  🚫 DANGEROUS COMMAND BLOCKED                     ║");
    console.error("╚══════════════════════════════════════════════════╝");
    console.error("");
    console.error("Command:");
    console.error(`  ${command}`);
    console.error("");
    console.error("Matched rules:");
    findings.forEach((f) => console.error(f));
    console.error("");
    console.error("This command has been blocked for safety.");
    console.error("If you are certain this is safe, run it manually in a terminal.");
    console.error("");
    process.exit(1);
  }

  process.exit(0);
}

main();