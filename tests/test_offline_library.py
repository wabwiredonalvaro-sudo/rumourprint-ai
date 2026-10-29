"""Verify offline reading is real, prepackaged and safe to cache.

We deliberately do not ship copyrighted publisher full-text archives. Original
FEM explainers and user-saved personal copies are available to the offline app.
"""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def test_offline_library_ships_twenty_complete_original_reading_articles():
    data = json.loads(read("offline-library.json"))
    articles = data["articles"]
    assert len(articles) >= 20
    assert len({x["id"] for x in articles}) == len(articles)
    assert all(x["rights"].startswith("Original RUMOURPRINT") for x in articles)
    assert all(len(" ".join(x["body"])) >= 200 for x in articles)
    assert all(x["source_url"].startswith("https://") for x in articles)
    assert all(x["title"] and x["category"] for x in articles)


def test_offline_web_copies_match():
    for path in ["offline.html", "offline-library.json", "sw.js", "manifest.webmanifest"]:
        assert read(path) == read("fem-tools-site/" + path)


def test_offline_reader_and_app_install_preload_guides_and_updates():
    sw = read("sw.js")
    assert '"/offline.html"' in sw
    assert '"/offline-library.json"' in sw
    assert 'caches.open(CACHE)' in sw
    assert "fetch(request)" in sw
    assert "caches.match(request)" in sw
    html = read("offline.html")
    assert 'fetch(LIB,{cache:"no-store"})' in html
    assert 'caches.match(LIB)' in html
    assert 'localStorage.setItem(storeName' in html
    assert "document.createElement" in html
    assert "textContent=value" in html
    assert 'reader.hidden=false' in html


def test_web_main_portal_offers_offline_access_and_registers_worker():
    for path in ["index.html", "fem-tools-site/index.html"]:
        html = read(path)
        assert 'href="/offline.html"' in html
        assert 'navigator.serviceWorker.register("/sw.js")' in html
        assert 'rel="manifest"' in html


def test_android_bundle_has_guides_for_first_open_with_no_internet():
    raw = read("android-app/app/src/main/assets/offline-library.json")
    data = json.loads(raw)
    assert len(data["articles"]) >= 20
    html = read("android-app/app/src/main/assets/offline.html")
    assert "__RUMOURPRINT_LIBRARY_JSON__" in html
    assert 'byId("android-library")' in html
    assert 'if(packaged)' in html


def test_android_source_offers_library_and_attempts_safe_refresh():
    java = read("android-app/app/src/main/java/africa/freshexclusive/rumourprint/MainActivity.java")
    assert "showOfflineLibrary()" in java
    assert "OFFLINE_FEED" in java
    assert "offline-library.json" in java
    assert "validLibrary(received)" in java
    assert "loadDataWithBaseURL" in java
    assert "refreshOfflineLibraryWhenConnected()" in java
    assert "new Thread(() ->" in java


def test_public_prototype_does_not_claim_offline_ai_verification():
    web = read("offline.html").lower()
    assert "not copied publisher articles" in web
    assert "links to outside websites need internet" in web
    manifest = json.loads(read("manifest.webmanifest"))
    assert manifest["start_url"] == "/offline.html"
