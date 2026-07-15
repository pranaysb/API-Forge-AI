# Benchmarks

`run_benchmark.py` uploads each spec in `SPECS` to a locally running backend
(`http://localhost:8000`) and records success, runtime, and retry counts to
`results/`.

Small specs (`petstore.json`, `jsonplaceholder.json`) are committed. The large
vendor specs are gitignored to keep the repo small — fetch them locally:

- github.json  — https://raw.githubusercontent.com/github/rest-api-description/main/descriptions/api.github.com/api.github.com.json
- stripe.json  — https://raw.githubusercontent.com/stripe/openapi/master/openapi/spec3.json
- discord.json — https://raw.githubusercontent.com/discord/discord-api-spec/main/specs/openapi.json
