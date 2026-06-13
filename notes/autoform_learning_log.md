# AutoForm Learning Log

| What I now understand | What I still depend on Claude for | What could go wrong with other users |
|---|---|---|
| How an AI agent works — screenshot → decide → act → repeat | Reading Python code and knowing which lines to change | User uploads a real CV to a form they don't trust — data sent to Anthropic API without fully understanding that |
| Why API costs depend on model choice and how many tokens you send | Diagnosing terminal errors independently | Agent fills a field wrongly (e.g. wrong date format) and user submits without checking |
| Why sensitive files (.env, profile JSON) must never be committed to git | Writing git commands without being told exactly what to run | Downloaded HTML form doesn't work on real portals — user thinks the job has been applied for when it hasn't |
| What Docker does — packages the app so it runs the same anywhere | Knowing what could go wrong *before* we deploy, not after | No HTTPS — data travelling over plain HTTP, not encrypted |
| The difference between local and server environments | Spotting when a design decision has a non-obvious cost (e.g. screenshot history growing quadratically) | Supporting statement left blank — user doesn't notice and submits an incomplete application |
| Why the Submit button must be blocked in code, not just in the prompt | Structuring a new feature from scratch without guidance | Profile data is one person's — if shared with Iain's brother, his own data goes in the profile and could be mishandled |
| How to direct UI changes even without writing the code myself | Knowing which error message means what | No audit log — if something goes wrong during a run, there's no record of exactly what the agent did |
