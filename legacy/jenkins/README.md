# Legacy Jenkins pipeline

`Jenkinsfile` is the declarative pipeline for a fictional `orders-api` Go service, written the way a
mid-sized org's pipelines usually end up: a shared library (`vars/`, `src/`), Docker-in-Docker agent,
credential bindings, parallel test stages, a manual approval gate, a lock around production deploys
and Slack/email notifications on completion.

It is deliberately *not* minimal. The point is that every construct in it has a different answer in
GitHub Actions, and `tools/migration-analyzer` produces the checklist of those answers.

| Jenkins construct | Where it appears |
|---|---|
| `@Library` shared library | top of file, `vars/deployHelm.groovy`, `vars/smokeTest.groovy` |
| `agent { docker { ... } }` with the docker socket mounted | `agent` block |
| `credentials()` in `environment` and `withCredentials` | `environment`, `Image` stage, `deployHelm` |
| `parallel` stages | `Test` stage |
| `input` manual gate with `submitter` | `Approve production` |
| `lock` + `milestone` | `Deploy production` |
| `stash` / `archiveArtifacts` / `junit` | `Checkout`, `Build`, `Unit` |
| `cron` / `pollSCM` triggers | `triggers` block |
| `post { success / failure / unstable }` with `slackSend` and `emailext` | `post` block |
| `withSonarQubeEnv` plugin wrapper | `SAST` stage |

Nothing here is meant to run; there is no Jenkins in this repo.
