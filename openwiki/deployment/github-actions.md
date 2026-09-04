---
type: documentation
title: CI/CD Workflows
description: Overview of the GitHub Actions workflows used for continuous integration, deployment, and documentation synchronization.
tags: [github-actions, ci-cd, automation, deployment]
verified:
  - by: openwiki/0.5.0
    at: 2026-09-04T12:25:44.572Z
sources:
  - id: openwiki-source-164e2da859b5277df81c7d94
    resource: repo://.github/workflows/ci.yml
  - id: openwiki-source-6766b7a0c14857435d2077c9
    resource: repo://.github/workflows/deploy.yml
  - id: openwiki-source-6d4b4e707b8d60b6ccfa3425
    resource: repo://.github/workflows/openwiki-update.yml
generated: { by: "openwiki/0.5.0", at: "2026-09-04T12:25:44.572Z" }
---

# CI/CD Workflows

The repository leverages GitHub Actions for automated CI/CD and documentation management. These workflows are defined in `.github/workflows/` and provide end-to-end automation for testing, quality assurance, infrastructure deployment, and wiki updates.

## Core Pipelines

### Continuous Integration (CI)
Defined in [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml), this workflow triggers on every push or pull request to the `main` or `master` branches (ignoring documentation-only changes). It ensures code quality and correctness through:
* **Environment Setup:** Uses `uv` for dependency management and Python installation.
* **Static Analysis:** Runs `ruff` for linting and formatting.
* **Type Checking:** Validates code using `pyright`.
* **Testing:** Executes the full suite of unit and integration tests via `pytest`.

### Deployment
Defined in [`.github/workflows/deploy.yml`](../../.github/workflows/deploy.yml), this workflow executes automatically following a successful CI run or can be triggered manually via `workflow_dispatch`. It handles:
* **Artifact Preparation:** Builds the necessary deployment artifacts (e.g., Lambda functions).
* **Infrastructure as Code (IaC):** Uses [Pulumi](https://www.pulumi.com/) to deploy and update cloud infrastructure.
* **Authentication:** Utilizes OIDC for secure AWS credential management and requires specific repository secrets for service configurations (Qdrant, etc.).

### Documentation Sync
Defined in [`.github/workflows/openwiki-update.yml`](../../.github/workflows/openwiki-update.yml), this workflow runs daily at 08:00 UTC to synchronize the OpenWiki documentation with the current repository state.
* **Mechanism:** It installs the OpenWiki CLI and executes an update run.
* **Intelligence:** Configured to use a LLM provider (Gemini) to generate or update documentation content.
* **Automation:** Automatically submits the updates via a Pull Request, maintaining a living documentation source.

## Configuration & Security
- **Secrets:** Sensitive credentials (API keys, deployment secrets) are stored in GitHub Secrets.
- **Roles:** The deployment pipeline assumes an IAM role via OIDC to interact with AWS resources, following the principle of least privilege.
- **State Management:** Pulumi state is managed via an external S3 bucket, as configured in the deployment workflow.
