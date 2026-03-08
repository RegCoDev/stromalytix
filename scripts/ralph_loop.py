#!/usr/bin/env python3
"""
Ralph Loop - Autonomous Iterative Development

Repeatedly invokes Claude Code with the same prompt until:
- Completion promise is detected in output
- Max iterations reached
- User cancels

Preserves all file modifications and git history between iterations.
"""

import subprocess
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

class RalphLoop:
    def __init__(
        self,
        prompt_file: str,
        max_iterations: int = 10,
        completion_promise: str = "DONE",
        log_dir: str = "logs/ralph_loop"
    ):
        self.prompt_file = Path(prompt_file)
        self.max_iterations = max_iterations
        self.completion_promise = completion_promise
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_log = self.log_dir / f"session_{self.session_id}.log"
        self.iterations_log = self.log_dir / f"iterations_{self.session_id}.jsonl"

    def log(self, message: str):
        """Log to console and file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        print(log_line)

        with open(self.session_log, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")

    def read_prompt(self) -> str:
        """Read the prompt from file."""
        if not self.prompt_file.exists():
            raise FileNotFoundError(f"Prompt file not found: {self.prompt_file}")

        return self.prompt_file.read_text(encoding="utf-8")

    def run_claude_code(self, prompt: str, iteration: int) -> tuple[str, int]:
        """
        Run Claude Code with the prompt.

        Returns: (output, exit_code)

        Note: This is a SIMULATION since we can't programmatically control
        Claude Code interactive sessions. In reality, you would:

        1. Use Claude API directly (anthropic Python SDK)
        2. Use Claude Code CLI if it has non-interactive mode
        3. Use a headless automation tool (selenium, playwright)
        """

        self.log(f"[ITERATION {iteration}] Starting Claude Code session...")

        # OPTION 1: Use Anthropic API directly (RECOMMENDED)
        return self._run_via_api(prompt, iteration)

        # OPTION 2: Use Claude Code CLI (if available)
        # return self._run_via_cli(prompt, iteration)

    def _run_via_api(self, prompt: str, iteration: int) -> tuple[str, int]:
        """
        Run using Anthropic API directly.

        This requires: pip install anthropic
        """
        try:
            import anthropic
            import os

            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                self.log("ERROR: ANTHROPIC_API_KEY not found in environment")
                return "", 1

            client = anthropic.Anthropic(api_key=api_key)

            # Build context-aware prompt
            full_prompt = self._build_context_prompt(prompt, iteration)

            self.log(f"[API] Sending to Claude Sonnet...")

            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8192,
                messages=[{
                    "role": "user",
                    "content": full_prompt
                }]
            )

            output = message.content[0].text

            self.log(f"[API] Received {len(output)} characters")

            return output, 0

        except ImportError:
            self.log("ERROR: anthropic package not installed")
            self.log("Install with: uv add anthropic")
            return "", 1
        except Exception as e:
            self.log(f"ERROR: {e}")
            return "", 1

    def _build_context_prompt(self, base_prompt: str, iteration: int) -> str:
        """Build context-aware prompt with git history and test results."""

        # Get recent git commits
        git_log = self._get_git_log(limit=5)

        # Get current test status
        test_results = self._run_tests()

        # Get list of modified files
        git_status = self._get_git_status()

        context_prompt = f"""# Ralph Loop - Iteration {iteration}/{self.max_iterations}

## Session Context

You are in an iterative development loop. Your goal is to make all tests pass.

**Iteration**: {iteration} of {max_iterations}
**Session ID**: {self.session_id}
**Completion Promise**: When all tests pass, output "{self.completion_promise}"

## Recent Work (Git History)

{git_log}

## Current Test Results

{test_results}

## Modified Files

{git_status}

## Your Task

{base_prompt}

---

**IMPORTANT**:
- When all tests pass, output: {self.completion_promise}
- Commit your changes with descriptive messages
- Read your own previous work to avoid repetition
- Focus on making skipped/failed tests pass
"""

        return context_prompt

    def _get_git_log(self, limit: int = 5) -> str:
        """Get recent git commits."""
        try:
            result = subprocess.run(
                ["git", "log", f"-{limit}", "--oneline"],
                capture_output=True,
                text=True,
                check=False
            )
            return result.stdout or "No git history"
        except Exception:
            return "Git not available"

    def _get_git_status(self) -> str:
        """Get git status."""
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True,
                text=True,
                check=False
            )
            return result.stdout or "No changes"
        except Exception:
            return "Git not available"

    def _run_tests(self) -> str:
        """Run pytest and return summary."""
        try:
            result = subprocess.run(
                ["uv", "run", "pytest", "tests/test_overnight.py", "-v", "--tb=short"],
                capture_output=True,
                text=True,
                check=False,
                timeout=120
            )

            # Extract summary line
            for line in result.stdout.split("\n"):
                if "passed" in line or "failed" in line or "skipped" in line:
                    return line

            return "Tests not run"
        except Exception as e:
            return f"Test error: {e}"

    def check_completion(self, output: str) -> bool:
        """Check if completion promise is in output."""
        return self.completion_promise in output

    def save_iteration_log(self, iteration: int, output: str, completed: bool):
        """Save iteration details to JSONL log."""
        log_entry = {
            "session_id": self.session_id,
            "iteration": iteration,
            "timestamp": datetime.now().isoformat(),
            "output_length": len(output),
            "completed": completed,
            "git_commit": self._get_latest_commit()
        }

        with open(self.iterations_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")

    def _get_latest_commit(self) -> Optional[str]:
        """Get latest git commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                check=False
            )
            return result.stdout.strip()
        except Exception:
            return None

    def run(self):
        """Run the Ralph Loop."""
        self.log("=" * 70)
        self.log("RALPH LOOP - Autonomous Iterative Development")
        self.log("=" * 70)
        self.log(f"Session ID: {self.session_id}")
        self.log(f"Max iterations: {self.max_iterations}")
        self.log(f"Completion promise: '{self.completion_promise}'")
        self.log(f"Prompt file: {self.prompt_file}")
        self.log("")

        prompt = self.read_prompt()
        self.log(f"Loaded prompt ({len(prompt)} characters)")
        self.log("")

        for iteration in range(1, self.max_iterations + 1):
            self.log("=" * 70)
            self.log(f"ITERATION {iteration}/{self.max_iterations}")
            self.log("=" * 70)

            # Run Claude Code
            output, exit_code = self.run_claude_code(prompt, iteration)

            if exit_code != 0:
                self.log(f"ERROR: Claude Code exited with code {exit_code}")
                self.log("Stopping Ralph Loop")
                return 1

            # Save output
            output_file = self.log_dir / f"iteration_{iteration:02d}_output.txt"
            output_file.write_text(output, encoding="utf-8")
            self.log(f"Output saved to: {output_file}")

            # Check for completion
            completed = self.check_completion(output)
            self.save_iteration_log(iteration, output, completed)

            if completed:
                self.log("")
                self.log("=" * 70)
                self.log("SUCCESS: Completion promise detected!")
                self.log(f"'{self.completion_promise}' found in output")
                self.log(f"Completed in {iteration} iterations")
                self.log("=" * 70)
                return 0

            self.log(f"Completion promise not found, continuing...")
            self.log("")

            # Brief pause between iterations
            time.sleep(2)

        self.log("")
        self.log("=" * 70)
        self.log("WARNING: Max iterations reached without completion")
        self.log(f"Review logs at: {self.log_dir}")
        self.log("=" * 70)
        return 1


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Ralph Loop - Autonomous iterative development with Claude"
    )
    parser.add_argument(
        "prompt_file",
        help="Path to prompt file (e.g., .ralph/overnight_implementation.md)"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum number of iterations (default: 10)"
    )
    parser.add_argument(
        "--completion-promise",
        default="DONE: All overnight tests passing",
        help="String to detect in output for completion"
    )
    parser.add_argument(
        "--log-dir",
        default="logs/ralph_loop",
        help="Directory for logs (default: logs/ralph_loop)"
    )

    args = parser.parse_args()

    loop = RalphLoop(
        prompt_file=args.prompt_file,
        max_iterations=args.max_iterations,
        completion_promise=args.completion_promise,
        log_dir=args.log_dir
    )

    try:
        sys.exit(loop.run())
    except KeyboardInterrupt:
        print("\n\nStopped by user (Ctrl+C)")
        sys.exit(1)


if __name__ == "__main__":
    main()
