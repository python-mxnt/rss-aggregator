from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
import sqlite3
import hashlib
import feedparser
from urllib.parse import urlencode
from fastapi.staticfiles import StaticFiles

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Minimal DB setup for saved feeds (if needed later)
conn = sqlite3.connect("rss.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS combined_feeds (
    id TEXT PRIMARY KEY,
    feeds TEXT
)
""")
conn.commit()

# Big RSS feed catalog
RSS_CATALOG = {
    "TechCrunch": "https://techcrunch.com/feed/",
    "BBC": "https://feeds.bbci.co.uk/news/rss.xml",
    "CNN": "http://rss.cnn.com/rss/cnn_topstories.rss",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "Wired": "https://www.wired.com/feed/rss",
    "Engadget": "https://www.engadget.com/rss.xml",
    "Reuters": "http://feeds.reuters.com/reuters/topNews",
    "NYTimes": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "The Guardian": "https://www.theguardian.com/world/rss",
    "Polygon": "https://www.polygon.com/rss/index.xml",
    "IGN": "https://feeds.ign.com/ign/all",
    "ScienceDaily": "https://www.sciencedaily.com/rss/top.xml",
    "NASA": "https://www.nasa.gov/rss/dyn/breaking_news.rss",
    # Add as many as you want here...
}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Pass RSS catalog keys for frontend list
    feed_names = list(RSS_CATALOG.keys())
    return templates.TemplateResponse("index.html", {"request": request, "feeds": feed_names})

@app.post("/generate")
async def generate(feeds: str = Form(...)):
    # feeds = comma separated feed names selected
    selected = feeds.split(",")
    # Filter and get URLs of selected feeds
    urls = [RSS_CATALOG.get(f) for f in selected if f in RSS_CATALOG]
    urls = [u for u in urls if u]

    if not urls:
        return Response("No valid feeds selected", status_code=400)

    # Create a unique ID by hashing URLs list
    combined_key = hashlib.md5(",".join(sorted(urls)).encode()).hexdigest()

    # Save combined URLs to DB (optional)
    cursor.execute("INSERT OR IGNORE INTO combined_feeds (id, feeds) VALUES (?, ?)", (combined_key, ",".join(urls)))
    conn.commit()

    # Redirect to combined feed endpoint
    return RedirectResponse(f"/feed/{combined_key}")

@app.get("/feed/{feed_id}")
async def combined_feed(feed_id: str):
    # Lookup combined feeds URLs from DB
    cursor.execute("SELECT feeds FROM combined_feeds WHERE id = ?", (feed_id,))
    row = cursor.fetchone()
    if not row:
        return Response("Feed not found", status_code=404)
    urls = row[0].split(",")

    # Combine RSS entries from all feeds
    combined_entries = []
    for url in urls:
        d = feedparser.parse(url)
        if d.bozo:
            continue
        combined_entries.extend(d.entries)

    # Sort by published date desc (if exists)
    combined_entries.sort(key=lambda e: e.get("published_parsed", 0), reverse=True)

    # Generate combined RSS feed XML (simple)
    rss_items = ""
    for entry in combined_entries[:50]:  # limit to 50 latest items
        title = entry.get("title", "No title")
        link = entry.get("link", "#")
        published = entry.get("published", "")
        rss_items += f"""
        <item>
            <title>{title}</title>
            <link>{link}</link>
            <pubDate>{published}</pubDate>
        </item>
        """

    rss_feed = f"""<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
    <channel>
        <title>Combined RSS Feed</title>
        <link>http://example.com/</link>
        <description>Combined RSS feed generated</description>
        {rss_items}
    </channel>
    </rss>"""

    return Response(content=rss_feed, media_type="application/rss+xml")
