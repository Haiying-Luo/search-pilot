---
name: google-search
description: Search the web using Google. Use when you need to find current information, news, documentation, or any web content that may not be in your training data.
---

# Google Search

## Goal

Perform web searches using Google to retrieve up-to-date information from the internet. This skill is useful when:

- The user asks about current events, news, or recent developments
- You need to find documentation, tutorials, or technical references
- The user asks questions that require real-time or frequently updated information
- You need to verify facts or find authoritative sources

## Prerequisites

This skill requires the `SERPAPI_API_KEY` environment variable to be set.

## Script

Execute the search script with the user's query:

```shell
python scripts/searching_google_serpapi.py "your search query"
```

### Options

- `--num N`: Number of results to return (default: 10)
- `--location "City, Country"`: Get localized search results
- `--language CODE`: Language code for results (default: en)
- `--json`: Output raw JSON instead of formatted text

### Examples

Basic search:

```shell
python scripts/searching_google_serpapi.py "Python asyncio tutorial"
```

Search with limited results:

```shell
python scripts/searching_google_serpapi.py "latest AI news" --num 5
```

Localized search:

```shell
python scripts/searching_google_serpapi.py "weather forecast" --location "Beijing, China" --language zh
```

JSON output for structured processing:

```shell
python scripts/searching_google_serpapi.py "OpenAI API documentation" --json
```

## Output Format

The script returns:

- **Answer Box**: Direct answers from Google (if available)
- **Knowledge Graph**: Entity information (if available)
- **Search Results**: List of organic results with:
  - Title
  - URL
  - Snippet (description)
  - Date (if available)

## Notes

- Results are retrieved from Google via SerpAPI
- The script handles errors gracefully and returns error messages if the search fails
- For best results, use specific and descriptive search queries
