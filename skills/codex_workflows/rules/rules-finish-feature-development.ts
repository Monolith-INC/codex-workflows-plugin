/**
 * Rules for workflows-finish-feature-development.md only.
 * Binding: skills/codex_workflows/resources/workflows-finish-feature-development.md
 * Installed as: .agent/workflows/workflows-finish-feature-development.md
 */
export const workflow = "workflows-finish-feature-development.md" as const;

export const rules = [
  "INVOKE this stage only after required User Stories are merged into the Feature branch.",
  "DO NOT open Feature→trunk while required Story PRs remain open unless the user explicitly waives them.",
  "OPEN the Feature pull request with base equal to the confirmed main work branch.",
  "DO NOT open Story pull requests during finish.",
  "DO NOT create new User Story branches during finish.",
  "PUSH the Feature branch before opening the Feature→trunk pull request.",
  "ADDRESS Feature PR review on the Feature branch.",
  "DO NOT retarget Story PRs as a substitute for the Feature→trunk pull request.",
  "UPDATE the Active ledger with the Feature PR URL and merge outcome after merge.",
] as const;
