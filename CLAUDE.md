# kamqor: rules for Claude

## Subagent models: optimise cost

Pick the cheapest model and the lowest reasoning effort that does the job. Set `model` (and `effort` where noted) explicitly on every subagent dispatch; never let a subagent inherit the session model.

- **Research and review** (task reviews, whole-branch reviews, re-reviews, builder checks, code exploration): at most Opus 5.5 (`model: "opus"`) with `effort: "medium"`. Use a smaller model (Sonnet 5.5, Haiku) or lower effort whenever the job does not need Opus: small or mechanical diffs, scoped re-reviews of fix rounds, lookups.
- **Implementation** (implementers, fix rounds, fix waves): only Sonnet 5.5 (`model: "sonnet"`) or Haiku (`model: "haiku"`), never a larger model. Haiku for mechanical work where the brief contains the exact code or copy; Sonnet otherwise. Keep reasoning effort low (`effort: "low"`, or `"medium"` when the task needs design judgment).
- When a task seems to need more than these limits allow, stop and ask instead of escalating the model.
