"""Agentra hooks — git hooks and CI template management."""

from agentra.hooks.git import install_git_hooks, uninstall_git_hooks, hooks_status
from agentra.hooks.ci import generate_github_actions_step, generate_gitlab_ci_job

__all__ = [
    "install_git_hooks",
    "uninstall_git_hooks",
    "hooks_status",
    "generate_github_actions_step",
    "generate_gitlab_ci_job",
]
