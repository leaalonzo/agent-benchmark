---
name: arxiv_search
description: "Search ArXiv for recent academic papers on a topic. Returns title, authors, abstract, arxiv_id, url, and published date."
version: 1.0.0
metadata:
  openclaw:
    emoji: "📄"
    envVars: []
---

# ArXiv Search

Search ArXiv for recent academic papers matching a topic query.

## Usage

Run the following command, replacing `<topic>` with the search query and `<max_results>` with how many papers to return (default 10):

```bash
python3 openclaw_skills/handlers/arxiv_search_handler.py "<topic>" <max_results>
```

## Output

A JSON array of papers. Each paper has:
- `title` — paper title
- `authors` — list of author names
- `abstract` — full abstract
- `arxiv_id` — short ArXiv ID (e.g. `2401.12345`)
- `url` — link to the paper
- `published` — ISO 8601 publication date

## Example

```bash
python3 openclaw_skills/handlers/arxiv_search_handler.py "large language models" 5
```
