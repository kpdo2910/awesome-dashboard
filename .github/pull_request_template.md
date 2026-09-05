## What this changes

<!-- A line or two. Rationale belongs in a comment next to the code, where it stays findable. -->

## Checklist

- [ ] `CHANGELOG.md` has an entry, if a user can see the change
- [ ] `manifest.json` `human_version` is bumped, if any file that ships in the zip changed
- [ ] The sweep passes locally:
      `python3 tools/check_locales.py && find tools -name 'test_*.py' -print0 | xargs -0 -n1 python3`
- [ ] A new config key is in all three of `core/conf.py`, `config.json` and `config.md`
- [ ] New strings exist in every `i18n/*.json`
- [ ] Screenshots below, for anything visual

<!-- Merging this to main tags v<human_version> and publishes a release, so the
     version has to be right before the merge, not after. -->
