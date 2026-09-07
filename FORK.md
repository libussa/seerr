# doublage français Docker image

The maintained customization lives in `docker-french-dub/`. Seerr source files
are unchanged. The build fetches the exact upstream commit in `upstream-ref`,
relabels a fresh temporary checkout, and uses that checkout's Dockerfile.
Changes in this fork's application source are not used by the image build.

## Build locally

Requires Docker with BuildKit, Git, and Python 3:

```sh
./docker-french-dub/build.sh
```

This builds for the Docker host's architecture. The GitHub workflow builds
Linux amd64. Images are built locally; the script never publishes them.
The default tag comes from upstream's package version, currently
`seerr-french-dub:3.4.1`. Pass an image name as the first argument to override it.

For an existing Compose deployment, replace its image with the built image
and keep the existing environment, port, and `/app/config` volume settings.
Remove any `build:` entry so Compose uses the image. For a local-only image,
use `pull_policy: never` on the same Docker host. For deployment elsewhere,
use the registry image produced by the workflow instead.

## Publish with GitHub Actions

Pushing changes to `docker-french-dub/` or the image workflow on branch
`codex/french-dub-labels` builds and publishes:

```text
ghcr.io/libussa/seerr-french-dub:<full-fork-commit-sha>
ghcr.io/libussa/seerr-french-dub:3.4.1
```

The workflow uses the repository's `GITHUB_TOKEN`; no Docker Hub secret is
needed. Keep the GHCR package private and authenticate the deployment host,
or make the package public in GitHub's package settings. The image tag is
reported in the workflow summary. Retain the previous tag for rollback.
The version tag follows the pinned upstream package version automatically.
Rebuilding a modified overlay for the same release updates that version tag;
use the commit tag or image digest when you need to pin an exact build.

## Update upstream without rebasing

1. Choose an upstream release and resolve its full commit SHA, for example:
   `git fetch upstream tag vX.Y.Z` followed by
   `git rev-parse 'vX.Y.Z^{commit}'`.
2. Put that SHA in `docker-french-dub/upstream-ref`.
3. Run the build and check request buttons, badges, and notifications.
4. Commit the pin change and push it to trigger the image workflow.

There is no need to merge or rebase upstream into this fork. Only the pin
and the small build overlay are maintained. The current pin is stable release
[v3.4.1](https://github.com/seerr-team/seerr/releases/tag/v3.4.1), commit
`69f73a6f1486fdb51b8ddae9a94a8dfb629f461c`.

The overlay fails when expected files or labels disappear. This catches
some upstream changes; it cannot detect every new UI surface or semantic
change, so updates still need review. If upstream changes its build process,
update the wrapper as needed.

## Behavior

English and French messages, request badges, and notification text use
**doublage français**. Other translations retain upstream wording.
Configure the dedicated French Radarr and Sonarr instances as defaults for
the secondary category. Internally this remains `is4k`: request history,
permissions, API fields, and database records stay compatible.

This does not add audio-language detection or independent editions.
Media-server scanning still follows upstream resolution rules, which can
conflict with using the secondary category for dubbed content.
