import requests
import time

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
UA = "YourAppName/1.0 (contact@example.com) Python/requests"

session = requests.Session()
session.headers.update({"User-Agent": UA})
TIMEOUT = 20

def _get_json(params, max_retries=3, backoff=1.5):
    """GET JSON from MediaWiki with retries and diagnostics."""
    for attempt in range(1, max_retries + 1):
        try:
            r = session.get(WIKIPEDIA_API_URL, params=params, timeout=TIMEOUT)
            ct = r.headers.get("Content-Type", "")
            if r.status_code in (429, 503):
                # throttled — sleep and retry
                time.sleep(backoff ** attempt)
                continue
            r.raise_for_status()
            if "application/json" not in ct and "json" not in ct:
                # Not JSON — dump a snippet for debugging
                snippet = r.text[:300].replace("\n", " ")
                raise ValueError(f"Expected JSON, got {ct}. Snippet: {snippet}")
            return r.json()
        except (requests.RequestException, ValueError) as e:
            if attempt == max_retries:
                raise
            time.sleep(backoff ** attempt)

def search_wikipedia(query, limit=5):
    """Search Wikipedia and return list of normalized titles."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
    }
    data = _get_json(params)
    return [hit["title"] for hit in data.get("query", {}).get("search", [])]

def get_revision_before(title, before_iso="2015-01-01T00:00:00Z"):
    """
    Return the latest revision strictly before `before_iso`.
    Follows redirects and returns dict with title, rev_id, timestamp, user.
    """
    params = {
        "action": "query",
        "redirects": 1,              # follow redirects
        "titles": title,
        "prop": "revisions",
        "rvlimit": 1,
        "rvprop": "ids|timestamp|comment|user",
        "rvdir": "older",
        "rvstart": before_iso,       # get the latest rev BEFORE this date
        "format": "json",
        "formatversion": "2",
    }
    data = _get_json(params)
    pages = data.get("query", {}).get("pages", [])
    if not pages:
        return None
    page = pages[0]
    if "missing" in page:
        return None
    revs = page.get("revisions", [])
    if not revs:
        return None
    rev = revs[0]
    return {
        "title": page["title"],
        "rev_id": rev["revid"],
        "timestamp": rev["timestamp"],
        "user": rev.get("user", ""),
    }

def get_revision_summary(rev_id):
    """Fetch the summary (extract) for a specific revision id."""
    params = {
        "action": "query",
        "prop": "extracts",  # Changed from 'revisions'
        "revids": rev_id,
        "exintro": True,      # Request only the intro section
        "explaintext": True,  # Get plain text instead of HTML
        "format": "json",
        "formatversion": "2",
    }
    data = _get_json(params)
    try:
        # The structure of the response for extracts is different
        return data["query"]["pages"][0]["extract"]
    except (KeyError, IndexError):
        return None
