# Upstream

This is a fork of [cs50/compare50](https://github.com/cs50/compare50), based on upstream version 1.2.15 (commit `88622bd`).

## Changes from upstream

- **lib50 removed.** lib50 imports `termios`, which does not exist on Windows.
  - `compare50/_api.py`: new `files()` (with `_expand()`) replaces `lib50.files`. It uses stdlib `glob` with the same semantics: `*` patterns are implicitly recursive, directories expand to their files, hidden files are skipped by default, and include/exclude patterns apply in order.
  - `compare50/__main__.py`: uses `_api.files` and `(tag, pattern)` tuples instead of `lib50.config.TaggedValue`; the `lib50.Error` clause in `excepthook` is dropped.
  - `setup.py`: `lib50` removed. `packaging` and `requests` are now declared directly, since `__main__.py` imports them and they came in only through lib50.
- **Hashes are stable across processes.** `Index.hashes()` in `compare50/comparators/_winnowing.py` uses `blake2b` (64-bit) instead of `hash()`. `hash()` is seeded per process, and the process pool spawns workers with new seeds on Windows and macOS, so no k-grams matched there.
- **Tests:** `tests/cli_tests.py` (end-to-end ranking, escaping, lib50-free import, hash stability). Test harnesses in `tests/api_tests.py`, `tests/main_tests.py`, and `tests/winnowing_tests.py` now `chdir` back before deleting the temp directory (needed on Windows). `test_permission_error` is skipped on Windows, where `chmod` cannot revoke read access.

## Known differences from lib50.files

- No check that patterns stay inside the current directory (lib50 raised an error).
- No file-count limit and no `require` tag support (compare50 never used either).
