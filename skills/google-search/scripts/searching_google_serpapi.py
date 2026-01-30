#!/usr/bin/env python3
"""
Google Search Skill Script

Uses SerpAPI to perform Google searches and return structured results.
Requires SERPAPI_API_KEY environment variable to be set.

Usage:
    python searching_google_serpapi.py "your search query"
    python searching_google_serpapi.py "your search query" --num 5
"""

import argparse
import json
import os
from typing import Optional

import requests


def google_search(
    query: str,
    num_results: int = 10,
    location: Optional[str] = None,
    language: str = "en",
) -> dict:
    """
    Perform a Google search using SerpAPI.

    Args:
        query: The search query string
        num_results: Number of results to return (default: 10)
        location: Optional location for localized results
        language: Language code (default: "en")

    Returns:
        dict containing search results with title, link, and snippet
    """
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        return {"error": "SERPAPI_API_KEY environment variable is not set"}

    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "num": num_results,
        "hl": language,
    }

    if location:
        params["location"] = location

    try:
        response = requests.get(
            "https://serpapi.com/search",
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        # Extract organic search results
        results = []
        organic_results = data.get("organic_results", [])

        for item in organic_results[:num_results]:
            result = {
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            }
            # Include additional useful fields if available
            if "date" in item:
                result["date"] = item["date"]
            results.append(result)

        # Include answer box if available
        answer_box = data.get("answer_box")
        knowledge_graph = data.get("knowledge_graph")

        output = {
            "query": query,
            "results_count": len(results),
            "results": results,
        }

        if answer_box:
            output["answer_box"] = {
                "type": answer_box.get("type", ""),
                "title": answer_box.get("title", ""),
                "answer": answer_box.get("answer", answer_box.get("snippet", "")),
            }

        if knowledge_graph:
            output["knowledge_graph"] = {
                "title": knowledge_graph.get("title", ""),
                "type": knowledge_graph.get("type", ""),
                "description": knowledge_graph.get("description", ""),
            }

        return output

    except requests.exceptions.Timeout:
        return {"error": "Request timed out"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}
    except json.JSONDecodeError:
        return {"error": "Failed to parse API response"}


def format_results_for_display(results: dict) -> str:
    """Format search results for readable output."""
    if "error" in results:
        return f"Error: {results['error']}"

    lines = []
    lines.append(f"Search Query: {results['query']}")
    lines.append(f"Results Found: {results['results_count']}")
    lines.append("-" * 50)

    # Show answer box if available
    if "answer_box" in results:
        ab = results["answer_box"]
        lines.append("\n[Answer Box]")
        if ab.get("title"):
            lines.append(f"Title: {ab['title']}")
        if ab.get("answer"):
            lines.append(f"Answer: {ab['answer']}")
        lines.append("")

    # Show knowledge graph if available
    if "knowledge_graph" in results:
        kg = results["knowledge_graph"]
        lines.append("\n[Knowledge Graph]")
        if kg.get("title"):
            lines.append(f"Title: {kg['title']}")
        if kg.get("type"):
            lines.append(f"Type: {kg['type']}")
        if kg.get("description"):
            lines.append(f"Description: {kg['description']}")
        lines.append("")

    # Show organic results
    lines.append("\n[Search Results]")
    for i, result in enumerate(results["results"], 1):
        lines.append(f"\n{i}. {result['title']}")
        lines.append(f"   URL: {result['link']}")
        if result.get("snippet"):
            lines.append(f"   {result['snippet']}")
        if result.get("date"):
            lines.append(f"   Date: {result['date']}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Perform Google search using SerpAPI"
    )
    parser.add_argument(
        "query",
        type=str,
        help="The search query",
    )
    parser.add_argument(
        "--num",
        type=int,
        default=10,
        help="Number of results to return (default: 10)",
    )
    parser.add_argument(
        "--location",
        type=str,
        default=None,
        help="Location for localized results",
    )
    parser.add_argument(
        "--language",
        type=str,
        default="en",
        help="Language code (default: en)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted text",
    )

    args = parser.parse_args()

    results = google_search(
        query=args.query,
        num_results=args.num,
        location=args.location,
        language=args.language,
    )

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(format_results_for_display(results))


if __name__ == "__main__":
    main()
