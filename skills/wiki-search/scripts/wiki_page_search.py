import wikipedia
import wikipedia.wikipedia as wiki_internal
import requests
import argparse
from typing import Optional
from datetime import datetime

def search_wikipedia(entity : str, first_sentences : int = 0) -> str:
    """Get specific Wikipedia page content for the specific entity (people, places, concepts, events) and return structured information.

    This tool searches Wikipedia for the given entity and returns either the first few sentences
    (which typically contain the summary/introduction) or full page content based on parameters.
    It handles disambiguation pages and provides clean, structured output.

    Args:
        entity: The entity to search for in Wikipedia.
        first_sentences: Number of first sentences to return from the page. Set to 0 to return full content. Defaults to 0.

    Returns:
        str: Formatted search results containing title, first sentences/full content, and URL.
             Returns error message if page not found or other issues occur.
    """
    try:
        # Try to get the Wikipedia page directly
        page = wikipedia.page(title=entity, auto_suggest=False)

        # Prepare the result
        result_parts = [f"Page Title: {page.title}"]

        if first_sentences > 0:
            # Get summary with specified number of sentences
            try:
                summary = wikipedia.summary(
                    entity, sentences=first_sentences, auto_suggest=False
                )
                result_parts.append(
                    f"First {first_sentences} sentences (introduction): {summary}"
                )
            except Exception:
                # Fallback to page summary if direct summary fails
                content_sentences = page.content.split(". ")[:first_sentences]
                summary = (
                    ". ".join(content_sentences) + "."
                    if content_sentences
                    else page.content[:5000] + "..."
                )
                result_parts.append(
                    f"First {first_sentences} sentences (introduction): {summary}"
                )
        else:
            # Return full content if first_sentences is 0
            # TODO: Context Engineering Needed
            result_parts.append(f"Content: {page.content}")

        result_parts.append(f"URL: {page.url}")

        return "\n\n".join(result_parts)

    except wikipedia.exceptions.DisambiguationError as e:
        options_list = "\n".join(
            [f"- {option}" for option in e.options[:10]]
        )  # Limit to first 10
        output = (
            f"Disambiguation Error: Multiple pages found for '{entity}'.\n\n"
            f"Available options:\n{options_list}\n\n"
            f"Please be more specific in your search query."
        )

        try:
            search_results = wikipedia.search(entity, results=5)
            if search_results:
                output += f"Try to search {entity} in Wikipedia: {search_results}"
            return output
        except Exception:
            pass

        return output

    except wikipedia.exceptions.PageError:
        # Try a search if direct page lookup fails
        try:
            search_results = wikipedia.search(entity, results=5)
            if search_results:
                suggestion_list = "\n".join(
                    [f"- {result}" for result in search_results[:5]]
                )
                return (
                    f"Page Not Found: No Wikipedia page found for '{entity}'.\n\n"
                    f"Similar pages found:\n{suggestion_list}\n\n"
                    f"Try searching for one of these suggestions instead."
                )
            else:
                return (
                    f"Page Not Found: No Wikipedia page found for '{entity}' "
                    f"and no similar pages were found. Please try a different search term."
                )
        except Exception as search_error:
            return (
                f"Page Not Found: No Wikipedia page found for '{entity}'. "
                f"Search for alternatives also failed: {str(search_error)}"
            )

    except wikipedia.exceptions.RedirectError:
        return f"Redirect Error: Failed to follow redirect for '{entity}'"

    except requests.exceptions.RequestException as e:
        return f"Network Error: Failed to connect to Wikipedia: {str(e)}"

    except wikipedia.exceptions.WikipediaException as e:
        return f"Wikipedia Error: An error occurred while searching Wikipedia: {str(e)}"

    except Exception as e:
        return f"Unexpected Error: An unexpected error occurred: {str(e)}"


def search_wikipedia_revision(
    entity: str,
    date: Optional[str] = None,
    revision_id: Optional[int] = None,
) -> str:
    """Get historical Wikipedia page content as it appeared at a specific date or revision.

    Use this function when you need to find information that may have changed over time,
    such as historical data, past records, or content that existed at a specific point in time.

    Args:
        entity: The entity/page title to search for in Wikipedia.
        date: Target date in 'YYYY-MM-DD' format. Returns the revision closest to (but not after) this date.
        revision_id: Specific revision ID to retrieve. If provided, date is ignored.

    Returns:
        str: Historical page content with revision metadata.
             Returns error message if page or revision not found.

    Note:
        - Either date or revision_id must be provided
        - If date is provided, returns the latest revision on or before that date
        - Useful for researching how information was recorded at a specific point in time
    """
    if not date and not revision_id:
        return "Error: Either 'date' (YYYY-MM-DD) or 'revision_id' must be provided."

    try:
        # Step 1: Use wikipedia library to get page title (handles redirects and disambiguation)
        try:
            page = wikipedia.page(title=entity, auto_suggest=False)
            page_title = page.title
        except wikipedia.exceptions.DisambiguationError as e:
            options_list = "\n".join([f"- {option}" for option in e.options[:10]])
            return (
                f"Disambiguation Error: Multiple pages found for '{entity}'.\n\n"
                f"Available options:\n{options_list}\n\n"
                f"Please be more specific in your search query."
            )
        except wikipedia.exceptions.PageError:
            return f"Page Not Found: No Wikipedia page found for '{entity}'."

        # Step 2: Get revision ID
        target_revid = revision_id

        if not target_revid and date:
            # Parse and validate date
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d")
                # Convert to Wikipedia API timestamp format (end of day)
                # With rvdir=older, rvstart is the starting point going backwards
                rvstart = target_date.strftime("%Y-%m-%dT23:59:59Z")
            except ValueError:
                return f"Error: Invalid date format '{date}'. Use 'YYYY-MM-DD'."

            # Get the latest revision on or before the target date
            # Use wikipedia library's internal _wiki_request which has proper User-Agent
            rev_params = {
                "action": "query",
                "prop": "revisions",
                "titles": page_title,
                "rvlimit": 1,
                "rvprop": "ids|timestamp|comment",
                "rvstart": rvstart,
                "rvdir": "older",
            }
            rev_data = wiki_internal._wiki_request(rev_params)

            rev_pages = rev_data.get("query", {}).get("pages", {})
            rev_page = list(rev_pages.values())[0]
            revisions = rev_page.get("revisions", [])

            if not revisions:
                return (
                    f"No revision found for '{entity}' on or before {date}. "
                    f"The page may not have existed at that time."
                )

            target_revid = revisions[0]["revid"]
            rev_timestamp = revisions[0]["timestamp"]
            rev_comment = revisions[0].get("comment", "No comment")
        else:
            rev_timestamp = None
            rev_comment = None

        # Step 3: Get page content at specific revision
        content_params = {
            "action": "query",
            "prop": "revisions",
            "revids": target_revid,
            "rvprop": "content|timestamp|comment|user",
            "rvslots": "main",
        }
        content_data = wiki_internal._wiki_request(content_params)

        content_pages = content_data.get("query", {}).get("pages", {})
        content_page = list(content_pages.values())[0]

        if "revisions" not in content_page:
            return f"Error: Could not retrieve revision {target_revid} for '{entity}'."

        revision = content_page["revisions"][0]
        raw_content = revision.get("slots", {}).get("main", {}).get("*", "")
        timestamp = revision.get("timestamp", rev_timestamp or "Unknown")
        user = revision.get("user", "Unknown")
        comment = revision.get("comment", rev_comment or "No comment")

        # Step 4: Clean wikitext (basic cleaning)
        import re
        # Remove references
        cleaned = re.sub(r"<ref[^>]*>.*?</ref>", "", raw_content, flags=re.DOTALL)
        cleaned = re.sub(r"<ref[^/]*/>", "", cleaned)
        # Remove templates (basic)
        cleaned = re.sub(r"\{\{[^}]*\}\}", "", cleaned)
        # Remove [[ ]] links but keep text
        cleaned = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", cleaned)
        # Remove ''' and '' (bold/italic)
        cleaned = re.sub(r"'{2,}", "", cleaned)
        # Remove HTML tags
        cleaned = re.sub(r"<[^>]+>", "", cleaned)
        # Clean multiple whitespace
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        cleaned = cleaned.strip()

        # Build result
        result_parts = [
            f"Page Title: {page_title}",
            f"Revision ID: {target_revid}",
            f"Revision Date: {timestamp}",
            f"Editor: {user}",
            f"Edit Comment: {comment}",
            f"URL: https://en.wikipedia.org/w/index.php?title={page_title.replace(' ', '_')}&oldid={target_revid}",
            "",
            f"Content:\n{cleaned[:50000]}"  # Limit content length
        ]

        if len(raw_content) > 50000:
            result_parts.append("\n... (content truncated)")

        return "\n\n".join(result_parts)

    except requests.exceptions.RequestException as e:
        return f"Network Error: Failed to connect to Wikipedia API: {str(e)}"

    except Exception as e:
        return f"Unexpected Error: {str(e)}"


def list_wikipedia_revisions(
    entity: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 20,
) -> str:
    """List available historical revisions for a Wikipedia page.

    Use this function FIRST when you need to find historical information but don't know
    the exact date or revision ID. It returns a list of revisions with dates and comments,
    allowing you to identify the most relevant revision to retrieve.

    Args:
        entity: The entity/page title to search for in Wikipedia.
        start_date: Start of date range in 'YYYY-MM-DD' format (optional). Shows revisions from this date onwards.
        end_date: End of date range in 'YYYY-MM-DD' format (optional). Shows revisions up to this date.
        limit: Maximum number of revisions to return (default: 20, max: 50).

    Returns:
        str: List of revisions with revision ID, date, editor, and edit comment.
             Use the revision_id from this list with search_wikipedia_revision() to get full content.

    Example workflow:
        1. Call list_wikipedia_revisions("Albert Einstein", start_date="2020-01-01", end_date="2020-12-31")
        2. Review the list and identify relevant revision IDs
        3. Call search_wikipedia_revision("Albert Einstein", revision_id=<selected_id>)
    """
    limit = min(limit, 50)  # Cap at 50

    try:
        # Step 1: Use wikipedia library to get page title (handles redirects and disambiguation)
        try:
            page = wikipedia.page(title=entity, auto_suggest=False)
            page_title = page.title
        except wikipedia.exceptions.DisambiguationError as e:
            options_list = "\n".join([f"- {option}" for option in e.options[:10]])
            return (
                f"Disambiguation Error: Multiple pages found for '{entity}'.\n\n"
                f"Available options:\n{options_list}\n\n"
                f"Please be more specific in your search query."
            )
        except wikipedia.exceptions.PageError:
            return f"Page Not Found: No Wikipedia page found for '{entity}'."

        # Step 2: Build revision query params
        rev_params = {
            "action": "query",
            "prop": "revisions",
            "titles": page_title,
            "rvlimit": limit,
            "rvprop": "ids|timestamp|user|comment|size",
        }

        # Add date filters if provided
        # Our API: start_date is older, end_date is newer
        # Wikipedia API with rvdir=older: rvstart=newer, rvend=older
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                rev_params["rvend"] = start_dt.strftime("%Y-%m-%dT00:00:00Z")
            except ValueError:
                return f"Error: Invalid start_date format '{start_date}'. Use 'YYYY-MM-DD'."

        if end_date:
            try:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                rev_params["rvstart"] = end_dt.strftime("%Y-%m-%dT23:59:59Z")
            except ValueError:
                return f"Error: Invalid end_date format '{end_date}'. Use 'YYYY-MM-DD'."

        rev_params["rvdir"] = "older"

        # Step 3: Fetch revisions using wikipedia library's internal request
        rev_data = wiki_internal._wiki_request(rev_params)

        rev_pages = rev_data.get("query", {}).get("pages", {})
        rev_page = list(rev_pages.values())[0]
        revisions = rev_page.get("revisions", [])

        if not revisions:
            date_range_msg = ""
            if start_date or end_date:
                date_range_msg = f" in the specified date range ({start_date or 'beginning'} to {end_date or 'now'})"
            return f"No revisions found for '{entity}'{date_range_msg}."

        # Step 4: Format output
        result_parts = [
            f"Page Title: {page_title}",
            f"Revisions Found: {len(revisions)}",
            f"History URL: https://en.wikipedia.org/w/index.php?title={page_title.replace(' ', '_')}&action=history",
            "",
            "Available Revisions:",
            "-" * 80,
        ]

        for rev in revisions:
            rev_id = rev.get("revid", "Unknown")
            timestamp = rev.get("timestamp", "Unknown")
            user = rev.get("user", "Unknown")
            comment = rev.get("comment", "")[:100]  # Truncate long comments
            size = rev.get("size", 0)

            # Format timestamp for readability
            try:
                dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                date_str = timestamp

            result_parts.append(
                f"  ID: {rev_id} | Date: {date_str} | Editor: {user} | Size: {size} bytes"
            )
            if comment:
                result_parts.append(f"    Comment: {comment}")
            result_parts.append("")

        result_parts.append("-" * 80)
        result_parts.append(
            "To get content from a specific revision, use: "
            f"--entity \"{page_title}\" --revision_id <ID>"
        )

        return "\n".join(result_parts)

    except requests.exceptions.RequestException as e:
        return f"Network Error: Failed to connect to Wikipedia API: {str(e)}"

    except Exception as e:
        return f"Unexpected Error: {str(e)}"


def main():
    parser = argparse.ArgumentParser(
        description="Search Wikipedia for a given entity and return structured information."
    )
    parser.add_argument("--entity", type=str, required=True, help="The entity to search for in Wikipedia.")
    parser.add_argument(
        "--first_sentences",
        type=int,
        default=0,
        help="Number of first sentences to return from the page. Set to 0 to return full content. Defaults to 0.",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target date in 'YYYY-MM-DD' format for historical revision. If provided, searches for page content as of that date.",
    )
    parser.add_argument(
        "--revision_id",
        type=int,
        default=None,
        help="Specific Wikipedia revision ID to retrieve. If provided, --date is ignored.",
    )
    parser.add_argument(
        "--list_revisions",
        action="store_true",
        help="List available revisions instead of fetching content. Use with --start_date and --end_date to filter.",
    )
    parser.add_argument(
        "--start_date",
        type=str,
        default=None,
        help="Start date for listing revisions in 'YYYY-MM-DD' format.",
    )
    parser.add_argument(
        "--end_date",
        type=str,
        default=None,
        help="End date for listing revisions in 'YYYY-MM-DD' format.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of revisions to list (default: 20, max: 50).",
    )

    args = parser.parse_args()

    # List revisions mode
    if args.list_revisions:
        result = list_wikipedia_revisions(
            entity=args.entity,
            start_date=args.start_date,
            end_date=args.end_date,
            limit=args.limit,
        )
    # Historical revision mode
    elif args.date or args.revision_id:
        result = search_wikipedia_revision(
            entity=args.entity,
            date=args.date,
            revision_id=args.revision_id,
        )
    # Current page mode
    else:
        result = search_wikipedia(args.entity, args.first_sentences)

    print(result)


if __name__ == "__main__":
    main()