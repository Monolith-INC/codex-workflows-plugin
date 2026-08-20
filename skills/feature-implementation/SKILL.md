---
name: feature-implementation
description: Plan and implement a feature using tracker hierarchy and stacked SCM branches.
---

# Feature implementation

Use the generic tracker contract to fetch a feature and its user stories, confirm logical states and acceptance criteria, and publish the implementation plan as a tracker artifact. Use the SCM adapter for the feature branch and one story branch per child story.

The branch convention is selected during bootstrap and must be confirmed from integrations.json; do not invent a provider-specific naming rule. Open story pull requests against the feature branch, reconcile ancestor changes before new descendant commits, and hand off to finish-feature-development after all stories merge.
