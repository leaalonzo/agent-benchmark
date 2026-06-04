---
name: web_search
description: "Search the web via Brave Search API. Returns title, url, description, and published_date for each result."
version: 1.0.0
metadata:
  openclaw:
    emoji: "🌐"
    requires:
      env:
        - BRAVE_API_KEY
    envVars:
      - name: BRAVE_API_KEY
        required: true
        description: "Brave Search API subscription token"
---

# Web Search

Search the web using the Brave Search API.

## Usage

Run the following command, replacing `<query>` with the search query and `<num_results>` with how many results to return (default 5):

```bash
python3 openclaw_skills/handlers/web_search_handler.py "<query>" <num_results>
```

## Output

A JSON array of results. Each result has:
- `title` — page title
- `url` — page URL
- `description` — snippet or summary
- `published_date` — publication date if available

## Example

```bash
python3 openclaw_skills/handlers/web_search_handler.py "AI agent frameworks 2026" 5
```
