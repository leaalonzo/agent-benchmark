---
name: github_search
description: "Search GitHub for repositories matching a query, sorted by stars. Returns name, full_name, description, stars, url, language, and updated_at."
version: 1.0.0
metadata:
  openclaw:
    emoji: "🐙"
    envVars:
      - name: GITHUB_TOKEN
        required: false
        description: "GitHub personal access token. Unauthenticated requests are limited to 10/min."
---

# GitHub Search

Search GitHub for repositories matching a query, sorted by star count.

## Usage

Run the following command, replacing `<query>` with the search query and `<max_results>` with how many repos to return (default 5):

```bash
python3 openclaw_skills/handlers/github_search_handler.py "<query>" <max_results>
```

## Output

A JSON array of repositories. Each entry has:
- `name` — repository name
- `full_name` — `owner/repo` slug
- `description` — repository description
- `stars` — stargazer count
- `url` — link to the repository
- `language` — primary language
- `updated_at` — ISO 8601 last-updated timestamp

## Example

```bash
python3 openclaw_skills/handlers/github_search_handler.py "AI agent framework" 5
```
