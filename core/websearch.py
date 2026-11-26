"""بحث ويب مجاني بدون مفاتيح — DuckDuckGo HTML (اختياري، يفشل بهدوء)."""
from __future__ import annotations

import re
import urllib.parse

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}


def _unwrap(url: str) -> str:
    if "uddg=" in url and ("/l/?" in url or "duckduckgo.com" in url):
        m = re.search(r"[?&]uddg=([^&]+)", url)
        if m:
            return urllib.parse.unquote(m.group(1))
    return url


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).strip()


def duck_search(query: str, n: int = 5) -> list[dict]:
    """يرجع نتائج [{title, url, snippet}] أو [] عند أي فشل."""
    if not query or not isinstance(query, str) or httpx is None:
        return []
    for endpoint in ("https://html.duckduckgo.com/html/", "https://lite.duckduckgo.com/lite/"):
        try:
            r = httpx.post(endpoint, data={"q": query}, headers=_UA, timeout=12, follow_redirects=True)
            if r.status_code != 200:
                continue
            text = r.text
            results: list[dict] = []
            if endpoint.endswith("lite/"):
                # Use lookahead or flexible attribute ordering with re.S flag
                # matches <a ... rel="nofollow" ... href="..." ...>title</a> or href before rel
                rows = re.findall(
                    r'<a\b(?=[^>]*?\brel=["\']nofollow["\'])(?=[^>]*?\bhref=["\']([^"\']+)["\'])[^>]*>(.*?)</a>',
                    text,
                    re.S,
                )
                for url, title in rows:
                    u = _unwrap(url)
                    if not u.startswith("http"):
                        continue
                    results.append({"title": _strip_tags(title) or u, "url": u, "snippet": ""})
            else:
                # Extract per-block using result container blocks or combined regex
                # DuckDuckGo HTML wraps results in class="result ..." or "results_links"
                # Within each result block, link has class="result__a" and snippet has class="result__snippet"
                # We can match result blocks first, then extract link and snippet from each block
                result_blocks = re.findall(r'<div\b(?=[^>]*?\bclass=["\'][^"\']*?\bresult\b)[^>]*>.*?</div>\s*(?=<div\b(?=[^>]*?\bclass=["\'][^"\']*?\bresult\b)|$)', text, re.S)
                if not result_blocks:
                    # Fallback to broad table or div result blocks if structure varies
                    result_blocks = re.findall(r'<div\b[^>]*?\bclass=["\'][^"\']*?result[^"\']*?["\'][^>]*>.*?</div>', text, re.S)

                for block in result_blocks:
                    link_match = re.search(
                        r'<a\b(?=[^>]*?\bclass=["\'][^"\']*?\bresult__a\b[^"\']*?["\'])(?=[^>]*?\bhref=["\']([^"\']+)["\'])[^>]*>(.*?)</a>',
                        block,
                        re.S,
                    )
                    if not link_match:
                        continue
                    url, title = link_match.group(1), link_match.group(2)
                    u = _unwrap(url)
                    if not u.startswith("http"):
                        continue
                    sn_match = re.search(r'class=["\'][^"\']*?\bresult__snippet\b[^"\']*?["\'][^>]*>(.*?)</a>', block, re.S)
                    sn = _strip_tags(sn_match.group(1)) if sn_match else ""
                    results.append({"title": _strip_tags(title) or u, "url": u, "snippet": sn})

                # Fallback if no blocks found via container regex
                if not results:
                    links = re.findall(
                        r'<a\b(?=[^>]*?\bclass=["\'][^"\']*?\bresult__a\b[^"\']*?["\'])(?=[^>]*?\bhref=["\']([^"\']+)["\'])[^>]*>(.*?)</a>',
                        text,
                        re.S,
                    )
                    snippets = re.findall(r'class=["\'][^"\']*?\bresult__snippet\b[^"\']*?["\'][^>]*>(.*?)</a>', text, re.S)
                    for i, (url, title) in enumerate(links):
                        u = _unwrap(url)
                        if not u.startswith("http"):
                            continue
                        sn = _strip_tags(snippets[i]) if i < len(snippets) else ""
                        results.append({"title": _strip_tags(title) or u, "url": u, "snippet": sn})

            if results:
                seen: set[str] = set()
                out = []
                for item in results:
                    if item["url"] in seen:
                        continue
                    seen.add(item["url"])
                    out.append(item)
                    if len(out) >= n:
                        break
                return out
        except Exception:
            continue
    return []


def wikipedia_search(query: str, lang: str = "ar", n: int = 3) -> list[dict]:
    """ويكيبيديا عربي/إنجليزي — مجاني بدون مفاتيح."""
    if not query or not isinstance(query, str) or httpx is None:
        return []
    try:
        r = httpx.get(f"https://{lang}.wikipedia.org/w/api.php",
                      params={"action": "query", "list": "search", "srsearch": query,
                              "format": "json", "srlimit": n},
                      headers=_UA, timeout=12)
        if r.status_code != 200:
            return []
        out = []
        for hit in (r.json().get("query") or {}).get("search") or []:
            title = hit.get("title", "")
            snippet = re.sub(r"<[^>]+>", "", hit.get("snippet", "") or "")
            url = f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
            out.append({"title": title, "url": url, "snippet": snippet, "kind": "wikipedia"})
        return out
    except Exception:
        return []


def web_search_all(query: str, lang: str = "ar", n: int = 5) -> list[dict]:
    """ويب + ويكيبيديا + أبحاث + سوشيال ميديا حسب طبيعة السؤال — مجاني وبدون مفاتيح."""
    if not query or not isinstance(query, str):
        return []
    ql = query.lower()
    results: list[dict] = []
    try:
        results.extend(wikipedia_search(query, lang="ar" if lang == "ar" else "en", n=3))
    except Exception:
        pass
    if any(w in ql for w in ("بحث", "ورقة", "paper", "research", "arxiv", "study", "دراسة", "منشور", "scholar")):
        try:
            results.extend(duck_search(
                f"{query} (site:arxiv.org OR site:researchgate.net OR site:semanticscholar.org OR site:scholar.google.com)",
                n=3))
        except Exception:
            pass
    if any(w in ql for w in ("تويتر", "twitter", "x.com", "linkedin", "لينكد إن", "لينكد", "فيسبوك",
                             "facebook", "انستجرام", "instagram", "يوتيوب", "youtube", "تيك توك",
                             "tiktok", "reddit", "واتساب", "جروب", "فيس")):
        try:
            results.extend(duck_search(
                f"{query} (site:linkedin.com OR site:x.com OR site:twitter.com OR site:youtube.com OR site:facebook.com OR site:reddit.com)",
                n=4))
        except Exception:
            pass
    try:
        results.extend(duck_search(query, n=n))
    except Exception:
        pass
    seen: set = set()
    out = []
    for r in results:
        u = r.get("url")
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(r)
        if len(out) >= n:
            break
    return out
