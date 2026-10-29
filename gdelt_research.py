"""Optional GDELT public news search; bounded, no key and not exhaustive."""
from __future__ import annotations
import json
import urllib.parse
import urllib.request
from evidence import safe_link

def search_gdelt(query: str, *, limit: int=20, fetch=None) -> list[dict]:
    query = " ".join(str(query or "").split())[:170]
    if len(query) < 3: return []
    if fetch is None:
        params = urllib.parse.urlencode({"query":query,"mode":"artlist","format":"json","maxrecords":min(limit,25),"timespan":"3months"})
        url = "https://api.gdeltproject.org/api/v2/doc/doc?" + params
        req = urllib.request.Request(url, headers={"Accept":"application/json"})
        with urllib.request.urlopen(req, timeout=8) as response:
            content = response.read(950001)
            if len(content)>950000: raise ValueError("News search response too large")
            data = json.loads(content)
    else: data = fetch(query, limit)
    if not isinstance(data,dict): return []
    result=[]
    for a in (data.get("articles") or [])[:limit]:
        if not isinstance(a,dict): continue
        link=safe_link(a.get("url"))
        title=str(a.get("title") or "").strip()[:220]
        if not link or not title: continue
        date=str(a.get("seendate") or "")
        if len(date)>=8 and date[:8].isdigit(): date=date[:4]+"-"+date[4:6]+"-"+date[6:8]
        result.append({"type":"news","title":title,"url":link,"publisher":str(a.get("domain") or "News publisher")[:100],"date":date or "Unknown","description":"Indexed news link; review the original article."})
    return result
