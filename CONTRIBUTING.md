# Contributing

1. Fork the repository and create a branch: `git checkout -b feature/my-change`.
2. Install the dependencies: `python -m pip install -r requirements.txt -r requirements-dev.txt`.
3. Make your change and add or update tests in `tests/`.
4. Run `python -m pytest`. It must pass on Windows.
5. Open a pull request that describes the change and how you tested it.

## Releasing (maintainers)

1. Bump `APP_VERSION` in `config.py` and add a section to `CHANGELOG.md`.
2. Write the release notes in `docs/releases/vX.Y.Z.md`.
3. Tag and push the release:
   ```bash
   git tag -a vX.Y.Z -m "Folder Sync vX.Y.Z"
   git push origin main vX.Y.Z
   ```
   The **Release** workflow builds `FolderSync.exe`, runs the tests and publishes the GitHub release.
