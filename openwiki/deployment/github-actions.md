---
type: CI/CD Documentation
title: GitHub Actions
description: Automated GitHub Actions workflows for OpenWiki documentation updates and CI/CD.
tags: [github-actions, ci-cd, openwiki, deployment]
---

# GitHub Actions

This repository uses GitHub Actions to automate the process of keeping the OpenWiki documentation up-to-date.

## OpenWiki Update Workflow

The workflow is defined in [`.github/workflows/openwiki-update.yml`](../../.github/workflows/openwiki-update.yml). It runs on a schedule (daily at 8:00 UTC) and can also be triggered manually.

The workflow performs the following steps:

1.  **Checks out the repository:** It starts by checking out the latest version of the code.
2.  **Sets up Node.js:** It installs Node.js version 22.
3.  **Installs OpenWiki:** It installs the `openwiki` CLI tool globally using `npm`.
4.  **Runs OpenWiki:** It runs the `openwiki code --update --print` command to update the documentation in the `/openwiki` directory. This step now includes several environment variables to configure the OpenWiki run:
    *   `OPENWIKI_PROVIDER`: Sets the provider to `openai-compatible`.
    *   `OPENAI_COMPATIBLE_BASE_URL`: Sets the base URL for the Gemini API OpenAI-compatible endpoint.
    *   `OPENAI_COMPATIBLE_API_KEY`: Uses a secret to authenticate with the Gemini API.
    *   `OPENWIKI_MODEL_ID`: Specifies the model to be used as `gemini-3.1-flash-lite`.
    *   `LANGSMITH_API_KEY`: Configures LangSmith for tracing.
    *   `LANGCHAIN_PROJECT`: Sets the LangChain project name to `openwiki`.
    *   `LANGCHAIN_TRACING_V2`: Enables LangChain tracing.
5.  **Creates a pull request:** It uses the `peter-evans/create-pull-request` action to create a pull request with the updated documentation. The pull request now includes changes to the following files:
    *   `openwiki/`
    *   `AGENTS.md`
    *   `CLAUDE.md`
    *   `.github/workflows/openwiki-update.yml`

This automated process ensures that the documentation stays in sync with the codebase without manual intervention.
