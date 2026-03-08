# Ralph Loop Configuration for Stromalytix

This directory contains prompts and configuration for autonomous overnight development using the Ralph Loop plugin.

## Quick Start

Launch the overnight implementation loop:

```bash
/ralph-loop "$(cat .ralph/overnight_implementation.md)" --max-iterations 20 --completion-promise "DONE: All overnight tests passing"
```

**What This Does**:
- Reads the detailed prompt from `overnight_implementation.md`
- Runs up to 20 iterations of development
- Stops when Claude outputs "DONE: All overnight tests passing"
- Preserves all file modifications and git history between iterations

## Monitoring Progress

Ralph Loop automatically preserves context between iterations. You can monitor progress by:

1. **Watch the test results**:
   ```bash
   uv run pytest tests/test_overnight.py -v --tb=short
   ```

2. **Check git history**:
   ```bash
   git log --oneline
   ```

3. **View baseline updates**:
   ```bash
   cat tests/BASELINE.md
   ```

## Expected Timeline

- **Iteration 1-3**: CC3D parameters KB creation (~50 PubMed records)
- **Iteration 4-6**: Confidence tagging implementation
- **Iteration 7-9**: Demo mode script creation
- **Iteration 10-15**: PDF export implementation
- **Iteration 16-20**: Debugging and refinement

Total estimated iterations: 10-15 (depending on API availability and complexity)

## Success Criteria

The loop completes successfully when all tests pass:

```
================= 17 passed in X.XXs ==================
```

- 0 SKIPPED
- 0 FAILED
- All features implemented
- Claude outputs: "DONE: All overnight tests passing"

## Cancellation

If you need to stop the loop early:

```bash
/cancel-ralph
```

This preserves all work completed up to that point.

## Troubleshooting

### Loop stuck on same test
- Check if external resources are needed (API keys, network access)
- Verify test expectations are clear in test_overnight.py
- Manually implement and commit to unblock

### Tests failing after passing
- Check for test interdependencies
- Verify no accidental file modifications
- Review git diff for regressions

### Max iterations reached without completion
- Review partial implementation in git history
- Identify bottleneck test
- Manually complete or adjust test expectations
- Re-launch Ralph Loop with remaining work

## Files Modified During Loop

Expected changes:
- `data/raw_abstracts/cc3d_parameters.json` (created)
- `scripts/generate_demo_data.py` (created)
- `core/rag.py` (modified - confidence tagging)
- `core/export.py` (created - PDF generation)
- `tests/BASELINE.md` (updated with results)
- `pyproject.toml` / `uv.lock` (if new dependencies added)

## Post-Loop Verification

After loop completes, verify manually:

1. **Run tests**: `uv run pytest tests/test_overnight.py -v`
2. **Test UI**: `uv run streamlit run app.py`
3. **Check git history**: `git log --oneline -20`
4. **Review changes**: `git diff HEAD~10 HEAD`

If all looks good, create a summary commit:

```bash
git add .
git commit -m "feat: overnight implementation complete - all tests passing"
```

## Prompt Customization

To modify the overnight work:

1. Edit `.ralph/overnight_implementation.md`
2. Adjust priorities, requirements, or completion criteria
3. Re-launch with updated prompt

Keep the completion promise consistent: "DONE: All overnight tests passing"
