# Upstream

This is a fork of [cs50/compare50](https://github.com/cs50/compare50), based on upstream version 1.2.15 (commit `88622bd`).

## Changes from upstream

- **lib50 removed.** lib50 imports `termios`, which does not exist on Windows.
  - `compare50/_api.py`: new `files()` (with `_expand()`) replaces `lib50.files`. It uses stdlib `glob` with the same semantics: `*` patterns are implicitly recursive, directories expand to their files, hidden files are skipped by default, and include/exclude patterns apply in order.
  - `compare50/__main__.py`: uses `_api.files` and `(tag, pattern)` tuples instead of `lib50.config.TaggedValue`; the `lib50.Error` clause in `excepthook` is dropped.
  - `setup.py`: `lib50` removed.
- **Removed the PyPI version check (no network access at run time).** `check_version()` ran on every invocation and called PyPI.
- **Hashes are stable across processes.** `Index.hashes()` in `compare50/comparators/_winnowing.py` uses `blake2b` (64-bit) instead of `hash()`. `hash()` is seeded per process, and the process pool spawns workers with new seeds on Windows and macOS, so no k-grams matched there. Every fingerprint value therefore differs from stock 1.2.15, so scores should be spot-checked before the MOSS benchmark.
- **No embedded webfonts.** `static/fonts.css` (440 KB of base64 Proxima Nova/Consolas) is deleted and no longer inlined into every page, so a report page shrinks from ~0.6-0.9 MB to ~0.2-0.4 MB. The CSS already falls back to `sans-serif`/`monospace`.
- **Syntax colours on match pages.** `_renderer.highlight()` wraps Pygments tokens (keywords, strings, comments, preprocessor, numbers, builtins, function names) in `<span class="tk-*">`; styles in `match.css`. The text is unchanged, so match offsets and line numbers are exact. Adds ~10% to a match page.
- **Redesigned report pages, no Bootstrap.** `static/base.css` (design tokens, light and dark via `prefers-color-scheme`, toolbar and buttons) replaces the 160 KB `bootstrap.min.css` that was inlined into every page. Index: summary bar, pair table with score bars and group dots, keyboard-openable rows, cluster panel with a labelled score slider; usernames are inserted as text, not HTML. Match page: top toolbar (back, pair nav, pass tabs, match nav) instead of the sidebar; a sticky name/percentage header inside each pane so it follows the splitter; line numbers restart per file (the right pane used to continue the left pane's count); ligatures off so `<=` is shown as typed; `select_view` finds panes by id (it used to read the splitter gutter as the right pane). A match page is ~55% smaller.
- **Optional LLM verdicts.** `compare50/_llm.py`: when `COMPARE50_LLM_URL`, `COMPARE50_LLM_KEY` and `COMPARE50_LLM_MODEL` are set, the top `--llm-pairs` pairs (default 5) scoring at least `--llm-min-score` (default 5, relative 0-10) are sent, with reasons in `--llm-language` (default `$COMPARE50_LLM_LANGUAGE`, else English), to an OpenAI-compatible `/chat/completions` endpoint (stdlib `urllib`, 4 at a time, 90 s timeout, 12k chars per submission). Only the code goes out, labelled A and B, never submission names. The verdict (likely copied / shared template / independent / unclear), confidence and up to 3 reasons are shown as an "AI review" column on the index and a strip above the code on the match page, and written to `llm.json`. A failed call is recorded as `"error"` and never fails the run. Without the variables nothing touches the network.
- **`results.json` and `--archive-only`.** Every report also writes `results.json` next to `index.html`: `pairs` with `match` (the `match_<n>.html` number), `a`/`b` (submission paths), `archive_a`/`archive_b`, `score` (0-10 relative to the top pair, as in `llm.json`) and `pct_a`/`pct_b` (absolute match percentages from the ranking pass). `--archive-only` keeps only pairs with an archive submission on one side, and of those the best one per regular submission.
- **Tests:** `tests/cli_tests.py` (end-to-end ranking, escaping, lib50-free import, hash stability). Test harnesses in `tests/api_tests.py`, `tests/main_tests.py`, and `tests/winnowing_tests.py` now `chdir` back before deleting the temp directory (needed on Windows). `test_permission_error` is skipped on Windows, where `chmod` cannot revoke read access.

## Known differences from lib50.files

- No check that patterns stay inside the current directory (lib50 raised an error).
- No file-count limit and no `require` tag support (compare50 never used either).
