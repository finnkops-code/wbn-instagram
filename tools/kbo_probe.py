import re, requests, json
from bs4 import BeautifulSoup
UA={"User-Agent":"Mozilla/5.0"}
u="https://eng.koreabaseball.com/Teams/PlayerSearch.aspx"
out=[]
for q in ["Kwak Bin","KWAK Bin","Kwak","Kim Do-yeong","Kim Doyeong","Kim Do Yeong","Park Hae-min","Park Haemin","Koo Bon-hyeok","Koo Bonhyeok","Ku Bon Hyeok"]:
    sess=requests.Session()
    s=BeautifulSoup(sess.get(u,headers=UA,timeout=30).content,"html.parser")
    form={i["name"]:i.get("value","") for i in s.select("input[name]")}
    box=[k for k in form if k.endswith("txtPlayerSearch")][0]
    btn=s.find("a",href=re.compile("btnPlayerSearch"))
    tgt=re.search(r"__doPostBack\('([^']+)'",btn["href"].replace("&#39;","'")).group(1)
    form[box]=q; form["__EVENTTARGET"]=tgt
    r=sess.post(u,data=form,headers=UA,timeout=30)
    soup=BeautifulSoup(r.text,"html.parser")
    rows=[tr.get_text(" ",strip=True)[:90]+" | "+",".join(re.findall(r"pcode=(\d+)",str(tr))) for tr in soup.select("table tr") if "pcode" in str(tr)]
    out.append({"q":q,"rows":rows[:5]})
    print(q, rows[:4])
open("probe/kbo_search.json","w").write(json.dumps(out,indent=1,ensure_ascii=False))
