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
- **Tests:** `tests/cli_tests.py` (end-to-end ranking, escaping, lib50-free import, hash stability). Test harnesses in `tests/api_tests.py`, `tests/main_tests.py`, and `tests/winnowing_tests.py` now `chdir` back before deleting the temp directory (needed on Windows). `test_permission_error` is skipped on Windows, where `chmod` cannot revoke read access.

## Known differences from lib50.files

- No check that patterns stay inside the current directory (lib50 raised an error).
- No file-count limit and no `require` tag support (compare50 never used either).
