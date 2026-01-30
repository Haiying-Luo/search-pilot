---
name: wiki-search
description: Search Wikipedia for specific entities (people, places, concepts, events) and return structured page content including summaries, full articles, and historical revisions.
---

# Wikipedia Search

## Goal

Look up Wikipedia pages for specific entities to retrieve authoritative, structured encyclopedic information. This skill is useful when:

- The user asks about a specific person, place, concept, or event
- You need background knowledge or a factual overview of an entity
- You want a reliable summary with a source URL
- You need to disambiguate between entities with similar names
- **You need historical information as it appeared at a specific point in time**

## Script

Execute the search script with the entity name:

```shell
python scripts/wiki_page_search.py --entity "entity name"
```

### Options

**Current Page:**
- `--entity "name"`: The entity to search for (required)
- `--first_sentences N`: Number of sentences to return from the introduction. Set to 0 to return full page content (default: 0)

**Historical Revisions:**
- `--date "YYYY-MM-DD"`: Get the page content as it appeared on this date
- `--revision_id N`: Get a specific revision by its ID (overrides --date)

**List Revisions (use this first when you don't know the exact date/revision):**
- `--list_revisions`: List available revisions for the page
- `--start_date "YYYY-MM-DD"`: Filter revisions from this date onwards
- `--end_date "YYYY-MM-DD"`: Filter revisions up to this date
- `--limit N`: Maximum revisions to list (default: 20, max: 50)

## Examples

### Current Page Content

Get full page content:

```shell
python scripts/wiki_page_search.py --entity "Albert Einstein"
```

Get a brief summary (first 5 sentences):

```shell
python scripts/wiki_page_search.py --entity "Python (programming language)" --first_sentences 5
```

### Historical Page Content

**Recommended workflow for historical research:**

**Step 1**: List available revisions to find the right one:

```shell
python scripts/wiki_page_search.py --entity "2020 United States presidential election" --list_revisions --start_date "2020-11-01" --end_date "2020-11-10"
```

**Step 2**: Get content from the specific revision ID found in step 1:

```shell
python scripts/wiki_page_search.py --entity "2020 United States presidential election" --revision_id 987654321
```

**Alternative**: If you know the approximate date, get the latest revision on or before that date:

```shell
python scripts/wiki_page_search.py --entity "2020 United States presidential election" --date "2020-11-04"
```

## Output Format

### Current Page Search

- **Page Title**: The canonical title of the Wikipedia page
- **Content**: Either the first N sentences (introduction) or full page content
- **URL**: Direct link to the Wikipedia page

### List Revisions

- **Page Title**: The canonical title
- **Revisions Found**: Number of revisions in the result
- **History URL**: Link to full revision history
- **Available Revisions**: List with ID, date, editor, size, and edit comment for each revision

### Historical Revision Search

- **Page Title**: The canonical title of the Wikipedia page
- **Revision ID**: The specific revision number
- **Revision Date**: When this revision was made
- **Editor**: Who made this edit
- **Edit Comment**: The editor's comment for this revision
- **URL**: Direct link to this specific historical revision
- **Content**: The page content as it appeared at that revision

## Error Handling

- **Disambiguation**: If the entity matches multiple pages, returns up to 10 candidate options. Retry with a more specific name.
- **Page Not Found**: Returns up to 5 similar page suggestions. Retry with one of the suggested names.
- **No Revision Found**: If the page didn't exist at the specified date, returns an appropriate message.
- **Network Error**: Returns connection failure details.

## Notes

- Use the exact entity name for best results (e.g., "Python (programming language)" instead of "Python")
- For ambiguous entities, add context in parentheses to avoid disambiguation pages
- Use `--first_sentences` to limit output when you only need a brief overview
- **For historical research**: Use `--list_revisions` first to discover available revisions, then use `--revision_id` to fetch content
- The `--date` option returns the latest revision on or before the specified date
- Historical content is cleaned of wiki markup for readability
