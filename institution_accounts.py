"""Small, sourced directory of public institutional X account candidates.

A link in an old institutional page is a starting point, not a guarantee
that the same person controls an account today. Never imply a blue badge
independently establishes real-world identity.
"""
from __future__ import annotations
import re
from urllib.parse import urlencode
from evidence import suggest_query

DIRECTORY = (
    {
        "name": "Uganda Police Force",
        "phrases": ("uganda police force", "uganda police", "police spokesman", "police spokesperson"),
        "handle": "PoliceUg",
        "reference": "https://www.upf.go.ug/",
        "source_label": "Police institution website — verify the current account link",
    },
    {
        "name": "Bank of Uganda",
        "phrases": ("bank of uganda", "central bank of uganda", "bou interest", "bou exchange"),
        "handle": "BOU_Official",
        "reference": "https://bou.or.ug/uploads/Joppa_Exchange_Services_Limited_Ceases_Foreign_Exchange_Business_4e37d76197.pdf",
        "source_label": "Bank of Uganda public notice naming the account",
    },
    {
        "name": "Makerere University",
        "phrases": ("makerere university", "makerere campus", "makerere examinations"),
        "handle": "Makerere",
        "reference": "https://rif.mak.ac.ug/makerere-university-phd-research-grant-awards-launched/",
        "source_label": "Makerere-managed news page linking to the account",
    },
    {
        "name": "Parliament of Uganda",
        "phrases": ("parliament of uganda", "ugandan parliament", "parliament passed", "parliamentary bill"),
        "handle": "Parliament_Ug",
        "reference": "https://gateway.parliament.go.ug/form/contact-us",
        "source_label": "Parliament's contact page naming its X account",
    },
)


def suggested_institution_accounts(claim: str) -> list[dict]:
    text = " ".join(str(claim or "").casefold().split())[:2500]
    words = " ".join(suggest_query(claim).split()[:4])
    result = []
    for account in DIRECTORY:
        if not any(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text) for phrase in account["phrases"]):
            continue
        handle = account["handle"]
        query = f"from:{handle} {words}".strip()
        result.append({
            "name": account["name"],
            "handle": handle,
            "source": account["reference"],
            "source_label": account["source_label"],
            "x_search": "https://x.com/search?" + urlencode({"q": query, "f": "live"}),
            "warning": "Likely institutional account — check current ownership and the exact post.",
        })
    return result[:4]
