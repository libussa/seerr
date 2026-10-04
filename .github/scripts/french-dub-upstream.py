#!/usr/bin/env python3
"""Open a release-pin PR and select its commit for an unpublished image build."""

import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = "libussa/seerr"
UPSTREAM = "seerr-team/seerr"
BASE = "codex/french-dub-labels"
PIN = "docker-french-dub/upstream-ref"
STATUS = "seerr/french-dub-build"
VALIDATION_STATUSES = (STATUS, "seerr/upstream-ci", "seerr/upstream-cypress", "seerr/upstream-codeql")


def api(path, data=None, method=None):
    print(f"{method or ('POST' if data is not None else 'GET')} {path}", flush=True)
    request = urllib.request.Request(
        f"https://api.github.com/{path}",
        data=json.dumps(data).encode() if data is not None else None,
        method=method,
        headers={
            "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "seerr-french-dub-release-updater",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        message = error.read().decode(errors="replace")
        raise RuntimeError(f"GitHub API {error.code} for {path}: {message}") from error


def content(repo, path, ref):
    result = api(f"repos/{repo}/contents/{path}?ref={urllib.parse.quote(ref, safe='')}")
    return base64.b64decode(result["content"]).decode()


def version(value):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        raise ValueError(f"Expected a stable release version, got {value!r}")
    return tuple(int(part) for part in match.groups())


def summary(text):
    print(text, flush=True)
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as stream:
        stream.write(text + "\n\n")


def output(name, value):
    with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
        stream.write(f"{name}={value}\n")


def main():
    output("validate", "false")
    release = api(f"repos/{UPSTREAM}/releases/latest")
    tag = release["tag_name"]
    if release["draft"] or release["prerelease"]:
        raise ValueError("Latest release endpoint returned a draft or prerelease")
    target_version = version(tag)
    upstream = api(f"repos/{UPSTREAM}/commits/{urllib.parse.quote(tag, safe='')}")["sha"]
    target_package = json.loads(content(UPSTREAM, "package.json", upstream))
    if version(target_package["version"]) != target_version:
        raise ValueError("Upstream release tag and package.json disagree")

    base = api(f"repos/{REPO}/git/ref/heads/{BASE}")["object"]["sha"]
    current = content(REPO, PIN, base).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", current):
        raise ValueError("Current upstream pin is not a full commit SHA")
    current_package = json.loads(content(UPSTREAM, "package.json", current))
    summary(f"Current: {current_package['version']} (`{current}`). Latest: [{tag}]({release['html_url']}) (`{upstream}`).")
    if version(current_package["version"]) >= target_version:
        summary("The custom branch is already at this release or newer. No PR needed.")
        return

    branch = f"automation/french-dub-v{'.'.join(map(str, target_version))}"
    query = urllib.parse.urlencode({"state": "all", "base": BASE, "head": f"libussa:{branch}", "per_page": 100})
    prs = api(f"repos/{REPO}/pulls?{query}")
    if prs:
        pr = max(prs, key=lambda item: item["number"])
        if pr["state"] != "open":
            summary(f"The release PR was already closed or merged: {pr['html_url']}. Leaving that decision intact.")
            return
    else:
        # Use matching-refs so a missing branch is an ordinary empty result.
        refs = api(f"repos/{REPO}/git/matching-refs/heads/{branch}")
        existing = next((item for item in refs if item["ref"] == f"refs/heads/{branch}"), None)
        if existing:
            head = existing["object"]["sha"]
            if content(REPO, PIN, head).strip() != upstream:
                raise ValueError(f"Existing branch {branch} has an unexpected pin; refusing to overwrite it")
        else:
            base_commit = api(f"repos/{REPO}/git/commits/{base}")
            tree = api(f"repos/{REPO}/git/trees", {
                "base_tree": base_commit["tree"]["sha"],
                "tree": [{"path": PIN, "mode": "100644", "type": "blob", "content": upstream + "\n"}],
            })
            commit = api(f"repos/{REPO}/git/commits", {
                "message": f"Update French-dub image to Seerr {tag}",
                "tree": tree["sha"], "parents": [base],
            })
            head = commit["sha"]
            api(f"repos/{REPO}/git/refs", {"ref": f"refs/heads/{branch}", "sha": head})

        body = (
            f"Updates the pinned upstream Seerr release from {current_package['version']} to **{tag}**, "
            "preserving the French-dub overlay.\n\n"
            f"Release notes: {release['html_url']}\n\n"
            f"Upstream commit: `{upstream}`\n\n"
            "The release checker builds the custom image without publishing it and reports "
            f"the result as **{STATUS}** on this PR. The fork's upstream CI, Cypress, and CodeQL "
            "workflows also run against the pinned upstream source with the overlay applied. "
            "Their results appear as **seerr/upstream-ci**, **seerr/upstream-cypress**, and "
            "**seerr/upstream-codeql**. If the overlay no longer applies, "
            "the build fails and the patch needs updating before merge.\n\n"
            f"Merging into `{BASE}` triggers the existing image publisher, including `latest`. "
            "Server deployment remains manual.\n\n"
            "This PR is not auto-merged. Closing it declines this release; the checker will not reopen it."
        )
        try:
            pr = api(f"repos/{REPO}/pulls", {
                "title": f"Update French-dub image to Seerr {tag}",
                "head": branch, "base": BASE, "body": body,
            })
        except RuntimeError:
            summary(
                "If GitHub blocked PR creation, enable **Settings → Actions → General → "
                "Workflow permissions → Allow GitHub Actions to create and approve pull requests**, "
                "then run this workflow again. The prepared branch can be reused."
            )
            raise

    summary(f"Release PR: {pr['html_url']}")
    head = pr["head"]["sha"]
    statuses = api(f"repos/{REPO}/commits/{head}/status")["statuses"]
    previous = {item["context"]: item["state"] for item in statuses}
    if all(previous.get(name) in ("success", "failure", "error") for name in VALIDATION_STATUSES) and os.environ.get("REVALIDATE") != "true":
        summary("All validation workflows already finished for this commit. Use Run workflow with revalidate to retry them.")
        return
    pinned = content(REPO, PIN, head).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", pinned):
        raise ValueError("PR upstream pin is not a full commit SHA")
    run_url = f"https://github.com/{REPO}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    for name in VALIDATION_STATUSES:
        api(f"repos/{REPO}/statuses/{head}", {
            "state": "pending", "context": name,
            "description": "Validating pinned upstream with French overlay",
            "target_url": run_url,
        })
    output("sha", head)
    output("upstream_sha", pinned)
    output("overlay_ref", f"refs/heads/{pr['head']['ref']}")
    output("validate", "true")
    summary(f"Building PR commit `{head}` and reporting its status on the PR.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as error:
        # Put the API's reason in the public run annotations as well as the log.
        message = str(error).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error::{message}", flush=True)
        sys.exit(1)
