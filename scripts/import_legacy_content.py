#!/usr/bin/env python3
"""Import legacy Griya Medistra content into a local JSON file for GitHub Pages."""
import json, re, urllib.request
from html import unescape
from bs4 import BeautifulSoup

BASE = "https://terapinarkoba.blogspot.com"
FEED = BASE + "/feeds/posts/default?alt=json&max-results=500"
STATIC_PAGES = [
    ("Profil Tabib Masrukhi", "/p/tabib-masrukhi.html"),
    ("Prosedur Pengobatan", "/p/prosedur-pengobatan.html"),
    ("Informasi Garansi Pengobatan", "/p/garansi-pengobatan.html"),
    ("Testimoni Pasien", "/p/testimoni-pasien-transaksi-pasien.html"),
    ("Tanya Jawab", "/p/tanya-jawab.html"),
]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; GriyaMedistraArchiveImporter/1.0)"}

def get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=40) as response:
        return response.read()

def normalize(text):
    return re.sub(r"\s+", " ", text or "").strip()

def content_from_html(raw):
    soup = BeautifulSoup(raw, "html.parser")
    for el in soup.select("script,style,iframe,object,embed,form,button,.share-buttons,.post-share-buttons"):
        el.decompose()
    # Blogger post feeds may contain a bare HTML fragment without .post-body.
    roots = soup.select(".post-body, .entry-content")
    root = roots[0] if roots else (soup.body or soup)
    blocks = []
    for node in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote", "tr"]):
        # Avoid repeating a paragraph's text through nested descendants.
        if node.find_parent(["p", "li", "blockquote", "tr"]):
            continue
        value = normalize(node.get_text(" ", strip=True))
        if value and (not blocks or blocks[-1]["text"] != value):
            kind = "heading" if node.name in ("h1", "h2", "h3", "h4") else "list" if node.name == "li" else "quote" if node.name == "blockquote" else "paragraph"
            blocks.append({"type": kind, "text": value})
    if not blocks:
        value = normalize(root.get_text(" ", strip=True))
        if value:
            blocks.append({"type": "paragraph", "text": value})
    return blocks

def fetch_static(title, path):
    try:
        raw = get(BASE + path)
        blocks = content_from_html(raw)
        return {"title":title, "url":BASE+path, "date":"", "categories":["Informasi Utama"], "summary":" ".join(b["text"] for b in blocks if b["type"] in ("heading","paragraph"))[:400], "fullText":"\\n\\n".join(b["text"] for b in blocks), "isPage":True}
    except Exception as exc:
        print("Could not import static page", path, exc)
        return None

def fetch_blogger_pages():
    # Use Blogger's actual Pages feed rather than guessed page slugs.
    try:
        url = BASE + "/feeds/pages/default?alt=json&max-results=100"
        payload = json.loads(get(url).decode("utf-8-sig"))
        pages = []
        for entry in payload.get("feed", {}).get("entry", []):
            links = entry.get("link", [])
            page_url = next((x.get("href") for x in links if x.get("rel") == "alternate"), BASE + "/")
            raw = (entry.get("content") or entry.get("summary") or {}).get("$t", "")
            blocks = content_from_html(raw)
            if not blocks and page_url.startswith(BASE):
                try:
                    blocks = content_from_html(get(page_url))
                except Exception as exc:
                    print("Could not fetch static page:", page_url, exc)
            full_text = "\n\n".join(b["text"] for b in blocks)
            title = (entry.get("title") or {}).get("$t", "Halaman tanpa judul")
            pages.append({"title": title, "url": page_url, "date": "", "categories": ["Informasi Utama"], "summary": full_text[:400], "fullText": full_text, "isPage": True})
        if pages:
            return pages
    except Exception as exc:
        print("Blogger Pages feed unavailable; using known page URLs:", exc)
    return [p for title, path in STATIC_PAGES if (p := fetch_static(title, path)) and p.get("fullText") and BASE not in p.get("fullText", "")[:300]]

def main():
    payload = json.loads(get(FEED).decode("utf-8-sig"))
    entries = payload.get("feed", {}).get("entry", [])
    posts = []
    for entry in entries:
        links = entry.get("link", [])
        url = next((x.get("href") for x in links if x.get("rel") == "alternate"), BASE + "/")
        raw = (entry.get("content") or entry.get("summary") or {}).get("$t", "")
        blocks = content_from_html(raw)
        # Some older Blogger feed entries expose only metadata; fetch the article page itself.
        if not blocks and url and url.startswith(BASE):
            try:
                blocks = content_from_html(get(url))
            except Exception as exc:
                print("Could not fetch article body:", url, exc)
        full_text = "\n\n".join(b["text"] for b in blocks)
        title = (entry.get("title") or {}).get("$t", "Artikel tanpa judul")
        published = (entry.get("published") or {}).get("$t", "")
        date = published[:10] if published else ""
        categories = [x.get("term","") for x in entry.get("category",[]) if x.get("term")]
        posts.append({"title":title, "url":url, "date":date, "categories":categories, "summary":full_text[:400], "fullText":full_text, "isPage":False})
    pages = fetch_blogger_pages()
    # Put static pages first, then newest posts.
    posts.sort(key=lambda x: x.get("date",""), reverse=True)
    output = {
        "source": BASE,
        "importedAt": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "notice": "Arsip historis website lama. Informasi kesehatan di dalamnya belum tentu sesuai panduan medis terkini dan tidak menggantikan konsultasi tenaga kesehatan.",
        "pages": pages,
        "posts": posts,
        "total": len(pages) + len(posts)
    }
    with open("legacy-content.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",",":"))
    print(f"Imported {len(pages)} static pages and {len(posts)} posts.")

if __name__ == "__main__":
    main()
