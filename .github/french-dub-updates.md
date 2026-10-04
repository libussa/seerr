# French-dub release updates

The `French-dub upstream release PR` workflow runs on the fork's default branch,
`codex/french-dub-labels`, daily at 06:23 UTC. GitHub may delay scheduled runs. A fork cannot
subscribe directly to another repository's release event, so the workflow polls
the latest stable release of `seerr-team/seerr`. It can also be run from Actions.

When a newer stable release is available, it opens a PR against
`codex/french-dub-labels` changing only `docker-french-dub/upstream-ref`. The
release tag is resolved to a full commit SHA and checked against `package.json`.
Each PR includes release notes and a comparison link between the exact previous
and proposed upstream commits, including all upstream changes in the new image.
There is one branch/PR per version. Repeated checks do not create duplicates,
overwrite contributor edits, downgrade the pin, or reopen a declined PR.

The workflow builds the proposed image without registry credentials or publishing
it, and attaches the `seerr/french-dub-build` commit status to the PR. It also calls
the existing upstream `ci.yml`, `cypress.yml`, and `codeql.yml` as reusable
workflows. These check out the pinned upstream SHA and apply the exact PR's overlay
before running their original test steps: i18n consistency, lint, formatting,
production build, unit tests, Cypress, and CodeQL (Actions and JavaScript).
Their results appear as `seerr/upstream-ci`, `seerr/upstream-cypress`, and
`seerr/upstream-codeql` on the PR. Cypress recording is disabled in the fork so
tests do not require upstream's private dashboard key. Upstream's stock image
publishing and Discord notification jobs do not run in the fork.

The release checker calls these workflows directly rather than relying on
bot-created PRs to trigger CI. GitHub may require approval for other PR workflows
triggered by `GITHUB_TOKEN`.
Use the **revalidate** checkbox under **Run workflow** to retry an existing build;
editing a PR gives it a new commit which is validated on the next scheduled run.

Review the release notes and successful build status, then merge the PR. The
custom branch's existing publisher builds and publishes commit, version, and
`latest` image tags. Nothing auto-merges or deploys to the Docker server.

The repository must allow Actions to create PRs: **Settings → Actions → General
→ Workflow permissions → Allow GitHub Actions to create and approve pull
requests**. No PAT or additional secret is needed. The workflow uses scoped
permissions on the built-in `GITHUB_TOKEN` and never approves PRs.

Keep this workflow on the default branch: GitHub only runs schedules there.
GitHub can disable schedules in inactive public repositories after 60 days;
re-enable the workflow in Actions if this happens. If the default branch is
renamed, update the `push` filter and the updater script's target branch. The job
guard follows the repository's default-branch setting automatically.
