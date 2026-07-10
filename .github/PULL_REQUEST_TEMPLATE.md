## Summary

What does this pull request change, and why?

## How was it tested

- [ ] `pytest` passes locally
- [ ] Built the exe (`python -m PyInstaller packaging/tresor.spec --clean --noconfirm`) if the change affects packaging
- [ ] Ran the manual native smoke test (`python tests/e2e/native_smoke.py`) if the change affects the window or the JS bridge

## Checklist

- [ ] Code comments and docstrings are in English
- [ ] User-facing UI strings stay consistent with the existing language
- [ ] The security core in `vault.py` remains behavior-preserving (tests stay green)
- [ ] No personal data, secrets, or local paths were added
- [ ] By submitting this pull request, I agree that my contribution is licensed under the MIT License
