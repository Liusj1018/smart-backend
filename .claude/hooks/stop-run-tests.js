#!/usr/bin/env node
/**
 * Stop Hook: Force Run Tests
 *
 * When the AI session ends, runs pytest with --tb=short -q.
 * If tests fail, blocks with exit code 1 and shows failure summary.
 *
 * Tests must complete within 30 seconds. Slow tests should be
 * marked with @pytest.mark.slow and excluded via -m "not slow".
 *
 * All output goes to stderr.
 */

const { execSync } = require("child_process");

const TEST_TIMEOUT_MS = 30000;

function main() {
  console.error("");
  console.error("╔══════════════════════════════════════════════════╗");
  console.error("║  🧪 Stop Hook: Running Test Suite                ║");
  console.error("╚══════════════════════════════════════════════════╝");
  console.error("");

  let stdout = "";
  let stderr = "";
  let exitCode = 0;

  try {
    // Use --no-cov to skip coverage during Stop hook.
    // Coverage threshold (--cov-fail-under=70 in pyproject.toml) is enforced
    // in CI/pre-commit, not on every session stop. Running coverage on every
    // stop causes failures during active development when tests are incomplete,
    // which blocks Cline from completing and triggers "repeated tool call failures".
    const result = execSync(
      'python -m pytest tests/ --tb=short -q -m "not slow" --no-header --no-cov -p no:cacheprovider 2>&1',
      {
        timeout: TEST_TIMEOUT_MS,
        encoding: "utf-8",
        maxBuffer: 5 * 1024 * 1024,
      }
    );
    stdout = result;
  } catch (e) {
    stdout = e.stdout?.toString() || "";
    stderr = e.stderr?.toString() || "";
    exitCode = e.status || 1;

    // Handle timeout
    if (e.killed || e.signal === "SIGTERM") {
      console.error("  ⏱️  Test suite timed out (>" + TEST_TIMEOUT_MS / 1000 + "s)");
      console.error("  Mark slow tests with @pytest.mark.slow");
      console.error("");
      process.exit(1);
    }
  }

  // Print last 20 lines of output for summary
  const lines = (stdout + stderr).split("\n").filter((l) => l.trim());
  const tail = lines.slice(-20);

  if (exitCode === 0) {
    console.error("  ✅ All tests passed!");
    // Show the summary line (usually last line with passed/failed count)
    const summaryLine = lines.find((l) => /passed/.test(l));
    if (summaryLine) {
      console.error(`  ${summaryLine.trim()}`);
    }
  } else {
    console.error("  ❌ Tests FAILED:");
    console.error("");
    tail.forEach((line) => {
      console.error(`  ${line}`);
    });
    console.error("");
    console.error("  Fix failing tests before ending the session.");
  }

  console.error("");
  process.exit(exitCode);
}

main();