# Stage 1: Recon

Inspect the diff, target files, nearby tests, and relevant project instructions without modifying files. Build a concise internal review map:

- changed surfaces and responsibilities
- affected contracts/APIs/config/schema/test behavior
- high-risk files or functions
- existing tests that should protect the change
- review tasks for Hunt

Generate narrow Hunt tasks. Each task must have:

- a specific question
- a small scope hint
- evidence the hunter should look for
- why that task matters for this diff

Avoid generic “review everything” tasks.
