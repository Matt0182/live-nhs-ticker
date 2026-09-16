import json,re
from datetime import date,datetime
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parent; DATA=ROOT/"budgets.json"
COLLECTION="https://www.gov.uk/government/collections/financial-directions-to-nhs-england"
H={"User-Agent":"NHS-Ticker-Budget-Updater/1.0"}
def get(u): r=requests.get(u,headers=H,timeout=30);r.raise_for_status();return r.text
def years(t):
 m=re.search(r"(20\d{2})\s+to\s+(20\d{2})",t,re.I);return (int(m.group(1)),int(m.group(2))) if m else None
def amount(t):
 for p in [r"total revenue resource use.*?does not exceed\s+£\s*([\d,]+)\s*million",r"total revenue resource use limit.*?£\s*([\d,]+)\s*million"]:
  m=re.search(p,t,re.I|re.S)
  if m:return int(m.group(1).replace(",",""))*1000000
 raise RuntimeError("Budget amount not found")
def pub(h):
 s=BeautifulSoup(h,"html.parser");m=s.find("meta",attrs={"property":"article:published_time"})
 if m and m.get("content"):return m["content"][:10]
 m=re.search(r"Published\s+(\d{1,2}\s+\w+\s+20\d{2})",s.get_text(" ",strip=True))
 return datetime.strptime(m.group(1),"%d %B %Y").date().isoformat() if m else "1900-01-01"
def main():
 s=BeautifulSoup(get(COLLECTION),"html.parser");items={}
 for a in s.find_all("a",href=True):
  t=a.get_text(" ",strip=True);y=years(t)
  if y and "financial directions to nhs england" in t.lower():
   u=urljoin("https://www.gov.uk",a["href"]);h=get(u);items[y]=(t,u,y,amount(soup_text(h)),pub(h))
 data=json.loads(DATA.read_text()); today=date.today(); y=today.year
 # Create the current calendar-year snapshot only if it doesn't already exist.
 if str(y) not in data["budgets"]:
  usable=[x for x in items.values() if x[2][0]<=y]
  if not usable: raise RuntimeError("No suitable published budget found")
  x=max(usable,key=lambda z:(z[2][0],z[4]))
  data["budgets"][str(y)]={"financialYear":f"{x[2][0]}/{str(x[2][1])[-2:]}","amount":x[3],"sourceUrl":x[1],"published":x[4],"snapshotDate":f"{y}-01-01"}
 # Pre-stage next year's official direction once it exists.
 ny=y+1
 if str(ny) not in data["budgets"] and ny in [x[2][0] for x in items.values()]:
  x=max([z for z in items.values() if z[2][0]==ny],key=lambda z:z[4])
  data["budgets"][str(ny)]={"financialYear":f"{x[2][0]}/{str(x[2][1])[-2:]}","amount":x[3],"sourceUrl":x[1],"published":x[4],"snapshotDate":f"{ny}-01-01"}
 data["lastUpdated"]=str(today);DATA.write_text(json.dumps(data,indent=2)+"\n")
def soup_text(h): return BeautifulSoup(h,"html.parser").get_text(" ",strip=True)
if __name__=="__main__": main()
