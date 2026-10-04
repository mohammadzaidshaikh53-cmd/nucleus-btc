# Publish this project to GitHub

Published repository: [nucleus-btc](https://github.com/mohammadzaidshaikh53-cmd/nucleus-btc).
The local `main` branch tracks `origin/main`. Source, documentation, test
results and example configuration are tracked. Native build outputs, local
pool credentials, environment files and SQLite state are ignored.

To publish another copy in a new repository:

1. Open https://github.com/new while signed into your account.
2. Name the repository `nucleus-btc` and choose Private unless you want the
   project visible publicly.
3. Leave README, .gitignore and license initialization disabled. The project
   already contains those files.
4. Click Create repository and copy its HTTPS URL.
5. From PowerShell in this project directory, run:

```powershell
git remote add origin https://github.com/YOUR_USERNAME/nucleus-btc.git
git push -u origin main
```

Git Credential Manager may open a browser to authenticate. Sign into GitHub
there; do not put an account password or token in the remote URL.

If origin already exists, inspect it with `git remote -v` and use
`git remote set-url origin YOUR_REPOSITORY_URL` only when changing destinations.
If a repository was accidentally initialized with a README, use a fresh empty
repository or reconcile its history; do not force-push over someone else's work.

After the first push, GitHub Actions builds and tests the CPU core on Windows and
Linux. Hosted runners do not validate this AMD GPU or HIP backend; local hardware
tests remain required for those paths. Check the
[Actions page](https://github.com/mohammadzaidshaikh53-cmd/nucleus-btc/actions)
for each commit's Windows and Linux results.

For later local updates:

```powershell
git add .
git commit -m "Describe the completed change"
git push
```

Official instructions:

- https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository
- https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github
