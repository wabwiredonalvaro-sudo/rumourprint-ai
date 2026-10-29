"""Collect real photos and actual screenshots for the hackathon presentation.
Run only in a GitHub Actions runner. Media saved as reference files, not committed.
"""
from __future__ import annotations
import os
import json
from pathlib import Path
import requests
from PIL import Image,ImageOps,ImageDraw
from io import BytesIO

OUT=Path("pitch-assets")
OUT.mkdir(exist_ok=True)
UA={"User-Agent":"RumourPrint-AI-Research-Presentation/1.0 (educational photo attribution; github.com)"}

PHOTOS=[
 ("boda_gulu","A boda boda motorcyclist near Gulu University, Uganda.jpg"),
 ("boda_riders","Motorcycle riders in Uganda.jpg"),
 ("boda_waiting","A bodaboda guy looking for a customer.jpg"),
 ("boda_men","Boda boda drivers of Uganda.jpg"),
 ("newsroom_laptop","Journalist at work... laptop, recorder.... 07.jpg"),
 ("newsroom_office","Newsroom.jpg"),
]
links=[]
for name,filename in PHOTOS:
    try:
        query={"action":"query","titles":"File:"+filename,
               "prop":"imageinfo","iiprop":"url|extmetadata","iiurlwidth":"1280",
               "format":"json","formatversion":2}
        r=requests.get("https://commons.wikimedia.org/w/api.php",params=query,headers=UA,timeout=22)
        print("COMMONS API",name,r.status_code,flush=True)
        r.raise_for_status()
        pages=r.json()["query"]["pages"]
        info=pages[0]["imageinfo"][0]
        url=info.get("thumburl") or info["url"]
        rr=requests.get(url,headers=UA,timeout=35)
        print("IMAGE",name,rr.status_code,len(rr.content),flush=True)
        rr.raise_for_status()
        img=Image.open(BytesIO(rr.content)).convert("RGB")
        img.thumbnail((1250,1250))
        img.save(OUT/(name+".jpg"),quality=87,optimize=True)
        links.append({"file":name+".jpg","title":filename,"source":"https://commons.wikimedia.org/wiki/File:"+filename.replace(" ","_"),"image_url":url,"license":str(info.get("extmetadata",{}).get("LicenseShortName",{}).get("value","See Wikimedia page"))})
    except Exception as ex:
        print("FAILED PHOTO",name,str(ex)[:200],flush=True)

# Additional truly photographed scenes with clearly identified publisher origin.
# These are not automatically eligible for redistribution; they are references only.
for name,url,source in [
 ("boda_phone_editorial","https://www.monitor.co.ug/resource/image/2304942/portrait_ratio1x1/1600/1600/26fbea57094f74dd21fbf042d9f284/Cv/prosper01pix.jpg","https://www.monitor.co.ug/uganda/business/prosper/making-money-from-mobile-apps--2304940"),
 ("boda_phone_eastafrican","https://www.theeastafrican.co.ke/resource/image/4045012/landscape_ratio3x2/1620/1080/8bcd2d5359573bb18be66569ffbd0152/zY/phone.jpg","https://www.theeastafrican.co.ke/tea/business-tech/uganda-seeks-tech-revolution-with-free-smartphones-4045010"),
]:
 try:
    r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=25)
    print("EDITORIAL PHOTO",name,r.status_code,len(r.content),flush=True)
    r.raise_for_status()
    img=Image.open(BytesIO(r.content)).convert("RGB")
    img.thumbnail((1250,1250));img.save(OUT/(name+".jpg"),quality=88,optimize=True)
    links.append({"file":name+".jpg","title":name,"source":source,"license":"Editorial publisher photo; permission/usage rights not established"})
 except Exception as ex:
    print("FAILED EDITORIAL",name,str(ex)[:180],flush=True)

(OUT/"photo_sources.json").write_text(json.dumps(links,indent=2),encoding="utf-8")

try:
 from playwright.sync_api import sync_playwright
 with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=["--no-sandbox"])
    URL="https://rumourprint-fem.streamlit.app/"
    for name,width,height,scale in [("desktop",1440,900,1),("phone",390,844,2)]:
      page=browser.new_page(viewport={"width":width,"height":height},device_scale_factor=scale)
      try:
       page.goto(URL,wait_until="domcontentloaded",timeout=120000)
       page.wait_for_timeout(16000)
       try: page.get_by_text("Seen something suspicious?").wait_for(timeout=45000)
       except Exception: pass
       print("PAGE TITLE",name,page.title(),flush=True)
       page.screenshot(path=str(OUT/(name+"_initial.png")),full_page=False,timeout=30000)
       inp=page.locator("textarea").first
       inp.fill("WhatsApp users claim Makerere University has cancelled all examinations next week.")
       try:
        page.get_by_text("WhatsApp",exact=True).first.click(timeout=7000)
       except Exception: pass
       try:
        page.get_by_role("button",name="Investigate").first.click(timeout=10000)
        page.wait_for_timeout(13000)
       except Exception as ex:
        print("INVESTIGATE error",name,str(ex)[:200],flush=True)
       page.screenshot(path=str(OUT/(name+"_investigation.png")),full_page=False,timeout=30000)
       print("SCREENSHOT",name,flush=True)
      except Exception as ex:
       print("SCREENSHOT FAILED",name,str(ex)[:300],flush=True)
      finally: page.close()
    browser.close()
except Exception as ex:
 print("PLAYWRIGHT UNAVAILABLE",str(ex)[:400],flush=True)
