#!/usr/bin/env python3
"""Update validated 2026 lottery records; no synthetic draws.
Optional env TW539_FEED_URL, HK6_FEED_URL, CA5_FEED_URL point to JSON/CSV
feeds containing draw_no, draw_date, numbers, special. TW539 also has
an HTML recent-results fallback. All failed sources are reported explicitly.
"""
import csv,datetime as dt,io,json,os,re,sys,urllib.request,html as htmllib
from pathlib import Path
from html import unescape
ROOT=Path(__file__).resolve().parents[1]/'data'
GAMES={'tw539':(39,5,False),'hk6':(49,6,True),'ca5':(39,5,False)}
TODAY=(dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))).date()
def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; THEWIN-LottoSync/1.6)','Accept':'text/html,application/json,text/csv'})
 with urllib.request.urlopen(req,timeout=25) as r:return r.read().decode('utf-8-sig')
def validate(g,row):
 mx,k,extra=GAMES[g];no=str(row['draw_no']).strip();date=str(row['draw_date'])[:10]
 day=dt.date.fromisoformat(date)
 if day<dt.date(2026,1,1) or day>TODAY:raise ValueError('date out of range')
 raw=row['numbers'];nums=[int(x) for x in (raw if isinstance(raw,list) else re.findall(r'\d+',str(raw)))]
 sp=row.get('special');sp=int(sp) if sp not in (None,'') else None
 if not no or len(nums)!=k or len(set(nums))!=k or not all(1<=n<=mx for n in nums):raise ValueError('invalid numbers')
 if extra and (sp is None or sp in nums or not 1<=sp<=mx):raise ValueError('invalid special')
 if not extra and sp is not None:raise ValueError('unexpected special')
 return {'draw_no':no,'draw_date':date,'numbers':sorted(nums),'special':sp}
def parse_feed(txt):
 try:
  obj=json.loads(txt)
  return obj['draws'] if isinstance(obj,dict) else obj
 except json.JSONDecodeError:return list(csv.DictReader(io.StringIO(txt)))
def tw539_recent_html(html):
 # Works with HTML pages that present date + ROC issue number + 5 balls together.
 txt=unescape(re.sub(r'<[^>]+>',' ',html));txt=re.sub(r'\s+',' ',txt)
 rows=[]
 pat=r'(10/\d{1,2}|\d{4}/\d{1,2}/\d{1,2})\s*(?:週[一二三四五六日])?\s*(115000\d{3})\s+((?:\d{1,2}\s+){4}\d{1,2})'
 for m in re.finditer(pat,txt):
  date=m.group(1);date='2026-'+date.replace('/','-') if date.startswith('10/') else date.replace('/','-')
  try:rows.append(validate('tw539',{'draw_no':m.group(2),'draw_date':date,'numbers':m.group(3)}))
  except ValueError:pass
 return rows
def hk_archive(txt):
 # The 2026 archive presents draw id, date, then 7 numbers in order.
 from html.parser import HTMLParser
 class Extract(HTMLParser):
  def __init__(self):super().__init__();self.bits=[]
  def handle_data(self,d):
   d=d.strip()
   if d:self.bits.append(d)
 p=Extract();p.feed(txt);bits=p.bits;rows=[]
 for i,t in enumerate(bits):
  if not re.fullmatch(r'26/\d{3}',t):continue
  if i+8>=len(bits) or not re.fullmatch(r'\d{2}/\d{2}/2026',bits[i+1]):continue
  try:
   nums=[int(x) for x in bits[i+2:i+9]]
   day=dt.datetime.strptime(bits[i+1],'%d/%m/%Y').date().isoformat()
   rows.append({'draw_no':t,'draw_date':day,'numbers':nums[:6],'special':nums[6]})
  except (ValueError,IndexError):continue
 return rows

def ca_archive(txt):
 # Extract rows from a public Fantasy 5 historical results table.
 from html.parser import HTMLParser
 class Extract(HTMLParser):
  def __init__(self):super().__init__();self.bits=[]
  def handle_data(self,d):
   d=d.strip()
   if d:self.bits.append(d)
 p=Extract();p.feed(txt);bits=p.bits;rows=[]
 for i,t in enumerate(bits):
  if not re.fullmatch(r'2026-\d{2}-\d{2}',t):continue
  near=' '.join(bits[i+1:i+9]);m=re.search(r'\b(\d{1,2})\s*[,，]\s*(\d{1,2})\s*[,，]\s*(\d{1,2})\s*[,，]\s*(\d{1,2})\s*[,，]\s*(\d{1,2})\b',near)
  if m:rows.append({'draw_no':t,'draw_date':t,'numbers':[int(x) for x in m.groups()],'special':None})
 return rows

def update(g):
 p=ROOT/(g+'.json');existing=json.loads(p.read_text()) if p.exists() else []
 current={r['draw_no']:validate(g,r) for r in existing};added=0;updated=0
 url=os.getenv(g.upper()+'_FEED_URL','').strip()
 try:
  if url:rows=parse_feed(fetch(url))
  elif g=='tw539':rows=tw539_recent_html(fetch('https://playsport539.com/lottery/539/'))
  elif g=='hk6':rows=hk_archive(fetch('https://lottery.hk/en/mark-six/results/2026'))
  elif g=='ca5':rows=ca_archive(fetch('https://lotterypredictor.com/california/fantasy5/results'))
  else:
   print(g+': no configured feed; existing records retained');return
  if not rows:raise ValueError('no usable results from source')
  for r in rows:
   v=validate(g,r);old=current.get(v['draw_no']);added+=old is None;updated+=old is not None and old!=v;current[v['draw_no']]=v
  result=sorted(current.values(),key=lambda r:(r['draw_date'],r['draw_no']),reverse=True)
  if result!=existing:p.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n')
  print(f'{g}: {len(result)} draws, +{added} new, {updated} corrected')
 except Exception as exc:
  print(f'{g}: sync failed ({exc}); existing records retained',file=sys.stderr)
  if os.getenv('STRICT_SYNC')=='1':raise
if __name__=='__main__':
 for g in GAMES:update(g)
