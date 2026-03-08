#!/bin/bash
# Development Loop - Manual Alternative to Ralph Loop
# Runs tests repeatedly and provides feedback for manual implementation

MAX_ITERATIONS=20
ITERATION=0
LOG_FILE="logs/dev_loop_$(date +%Y%m%d_%H%M%S).log"

mkdir -p logs

echo "=== Stromalytix Development Loop ===" | tee -a "$LOG_FILE"
echo "Max iterations: $MAX_ITERATIONS" | tee -a "$LOG_FILE"
echo "Started at: $(date)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

while [ $ITERATION -lt $MAX_ITERATIONS ]; do
    ITERATION=$((ITERATION + 1))

    echo "========================================" | tee -a "$LOG_FILE"
    echo "ITERATION $ITERATION / $MAX_ITERATIONS" | tee -a "$LOG_FILE"
    echo "========================================" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"

    # Run tests
    echo "Running tests..." | tee -a "$LOG_FILE"
    uv run pytest tests/test_overnight.py -v --tb=short 2>&1 | tee -a "$LOG_FILE"

    # Check exit code
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        # All tests passed
        PASSED=$(grep "passed" "$LOG_FILE" | tail -1)
        if echo "$PASSED" | grep -q "17 passed"; then
            echo "" | tee -a "$LOG_FILE"
            echo "✅ SUCCESS: All 17 tests passing!" | tee -a "$LOG_FILE"
            echo "DONE: All overnight tests passing" | tee -a "$LOG_FILE"
            echo "Completed at: $(date)" | tee -a "$LOG_FILE"
            exit 0
        fi
    fi

    echo "" | tee -a "$LOG_FILE"
    echo "⏸️  Tests still have failures/skips" | tee -a "$LOG_FILE"
    echo "   Review output above and implement fixes" | tee -a "$LOG_FILE"
    echo "   Press Enter to run next iteration (or Ctrl+C to stop)..." | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"

    read -p "Continue? "
done

echo "" | tee -a "$LOG_FILE"
echo "⚠️  Max iterations reached without completion" | tee -a "$LOG_FILE"
echo "Review $LOG_FILE for details" | tee -a "$LOG_FILE"
