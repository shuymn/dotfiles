# Writing agent knowledge

Rules for editing hiden, `toolchain`, `public-text`, `wasure` and `steward` (source under `home/dot_claude/**`), and for reviewing their diffs.

- Size: prose caps in `~/.claude/attention/budget.json` and its `create_budget.json` seed only go down; added text pays for itself by deleting at least as much.
- Wording: the model reads words literally. A named product or repo ("only on X") reads as "only there", and a blurred name carries nothing; write the mechanism that decides the rule, or delete the line. Mark parentheses that look like closed lists with 「例:」. Keep a Why only where it tells the reader where the rule stops applying (the cases it does not cover, or why another approach is not chosen); never write the history (who corrected it, where something happened). Rewrite only your own lines into the current conclusion, and give anything temporary a removal condition. Apply this to every diff `wasure` reviews.
- Splits: workers reach a skill by name and never open hiden paths. A rule a worker must find alone becomes its own skill with a distinct leading word; what the orchestrator copies into a brief stays a hiden reference.
- Prune pass (when `wasure` shows hiden has grown, or after a large rewrite): list product-named lines, incident-only Whys and no-ops; probe each "ambiguous" claim with 3 blind readers and rotated options, and edit only what they misread, because most flags read fine; have Codex review the diff for lost judgment; then re-sync and lower the caps to the new sizes.
