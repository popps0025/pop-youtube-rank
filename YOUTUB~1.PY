# -*- coding: utf-8 -*-
"""
팝성형외과 유튜브 상위노출 · 자체 수집/분석 시스템 (PC 실행용, 구글 Apps Script 미사용)
------------------------------------------------------------------------------------
- YouTube Data API v3로 키워드별 검색 상위 50위를 조회해 우리 채널 순위를 측정
- 각 키워드 상위 3개 경쟁사 영상도 함께 수집
- 결과를 data.json(누적 히스토리)에 저장하고, 그 자리에서 dashboard.html(대시보드)을 생성
- 파이썬 표준 라이브러리만 사용(별도 설치 불필요). 윈도우 작업 스케줄러로 매일 자동 실행.

사용 전 준비: 아래 API_KEY 한 곳만 본인 YouTube Data API 키로 바꾸세요.
"""

import json, os, sys, time, datetime, urllib.parse, urllib.request

# ===================== 설정 (여기만 확인) =====================
API_KEY = os.environ.get("YT_API_KEY") or "PASTE_YOUR_YOUTUBE_DATA_API_KEY_HERE"   # PC: 아래 따옴표에 키 입력 / 클라우드: 환경변수 YT_API_KEY 사용
CHANNEL_MATCH = "팝성형외과"     # 채널명에 이 문자열이 포함되면 '우리 채널'로 인식
CHANNEL_ID = ""                  # (선택) 채널 ID를 알면 넣으면 더 정확. 예: "UCxxxxxxxx"

# 상위노출 통계에 '성형외과 채널이 올린 영상'만 반영. 채널명에 아래 중 하나가 포함되면 인정.
# (게임·스포츠·일반 채널 자동 제외.) 더 엄격히: ["성형외과"] / 더 넓게: 아래에 "의원","피부과","닥터" 등 추가.
CLINIC_MATCH = ["성형외과", "성형", "plastic surgery"]
TOP_N = 50                       # 몇 위까지 추적할지 (최대 50)
REGION = "KR"
LANG = "ko"
HISTORY_DAYS = 90                # 보관할 최근 일수

KEYWORDS = [
    "압구정쌍수","눈성형","눈수술","눈추천","12홀자연유착","자연유착","자연유착쌍수","매몰법","절개법","쌍꺼풀","쌍꺼풀수술",
    "눈재수술","쌍꺼풀재수술","인라인","인아웃라인","세미아웃","세미아웃라인","아웃라인","트임","앞트임","위트임","뒤트임",
    "밑트임","상안검","하안검","눈매교정","눈밑지방재배치","눈썹하거상","리프팅추천","거상수술","안면거상","이마거상",
    "미니거상","실리프팅","리프팅","이중턱","남자눈성형","코수술","코성형","코추천"
]

# 검색 의도가 성형과 달라 순위가 잡혀도 무의미한 키워드(대시보드에서 '의도불일치'로 표기). 필요시 추가.
OFFTOPIC = ["인라인", "거상"]
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data.json")
HTML_FILE = os.path.join(BASE_DIR, "dashboard.html")


def yt_search(q):
    url = ("https://www.googleapis.com/youtube/v3/search"
           "?part=snippet&type=video&maxResults=%d&order=relevance"
           "&regionCode=%s&relevanceLanguage=%s&q=%s&key=%s"
           % (TOP_N, REGION, LANG, urllib.parse.quote(q), API_KEY))
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    if "error" in data:
        raise RuntimeError(data["error"].get("message", str(data["error"])))
    out = []
    for it in data.get("items", []):
        sn = it.get("snippet", {}) or {}
        vid = (it.get("id") or {}).get("videoId", "")
        out.append({"channelId": sn.get("channelId", ""),
                    "channelTitle": sn.get("channelTitle", ""),
                    "title": sn.get("title", ""),
                    "videoId": vid})
    return out


def is_mine(it):
    if CHANNEL_ID and it["channelId"] == CHANNEL_ID:
        return True
    return CHANNEL_MATCH in (it["channelTitle"] or "")


def is_clinic(it):
    t = (it["channelTitle"] or "").lower()
    return any(w.lower() in t for w in CLINIC_MATCH)


def main():
    if API_KEY.startswith("PASTE_"):
        print("먼저 API_KEY를 본인 YouTube Data API 키로 바꾸세요.")
        sys.exit(1)

    today = datetime.datetime.now().strftime("%Y-%m-%d")

    data = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    history = data.get("history", {})
    comphist = data.get("comphist", {})

    dayrec = {}
    comp = {}
    ok_cnt = 0
    for kw in KEYWORDS:
        rank, status = None, "beyond"
        try:
            items = yt_search(kw)
            clinic = [x for x in items if is_clinic(x)]   # 성형외과 채널 영상만
            comp[kw] = [{"t": x["title"], "c": x["channelTitle"], "m": is_mine(x)} for x in clinic[:3]]
            for i, x in enumerate(clinic):
                if is_mine(x):
                    rank, status = i + 1, "ok"
                    break
        except Exception as e:
            status = "error"
            print("ERROR [%s] %s" % (kw, e))
        if status == "ok":
            ok_cnt += 1
        dayrec[kw] = {"r": rank, "s": status}
        print("%-14s %s" % (kw, (str(rank) + "위") if rank else status))
        time.sleep(0.15)

    history[today] = dayrec
    comphist[today] = comp
    dates = sorted(history.keys())[-HISTORY_DAYS:]
    history = {d: history[d] for d in dates}
    comphist = {d: comphist[d] for d in comphist if d in dates}

    out = {
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "channel": "팝성형외과 POP TV",
        "keywords": KEYWORDS,
        "dates": dates,
        "history": history,
        "comp": comp,           # 최신 스냅샷(하위호환)
        "comphist": comphist,   # 날짜별 경쟁사 스냅샷
        "offtopic": OFFTOPIC,
        "top_n": TOP_N,
    }

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    payload = json.dumps(out, ensure_ascii=False).replace("<", "\\u003c")
    html = HTML_TEMPLATE.replace("__DATA__", payload)
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print("\n완료: %s · TOP50 진입 %d개 · 대시보드 → %s" % (today, ok_cnt, HTML_FILE))


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>팝성형외과 유튜브 상위노출 대시보드</title>
<style>
:root{--bg:#0f1720;--panel:#161f2b;--p2:#1c2836;--line:#26333f;--ink:#e8eef5;--mut:#93a4b5;--faint:#6b7d8f;
--ok:#30a46c;--beyond:#3b4b5c;--err:#e5484d;--warn:#f5a623;--accent:#4c8dff;--gold:#e5b53b;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Malgun Gothic","Segoe UI",Roboto,sans-serif;line-height:1.55}
.wrap{max-width:1120px;margin:0 auto;padding:24px 20px 80px}
h1{font-size:21px;margin:0 0 3px}
.sub{color:var(--mut);font-size:12.5px;margin-bottom:18px}
.tabs{display:flex;gap:8px;margin-bottom:22px;border-bottom:1px solid var(--line)}
.tab{padding:11px 18px;font-size:14px;font-weight:700;color:var(--mut);cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px}
.tab.on{color:var(--ink);border-bottom-color:var(--accent)}
.view{display:none} .view.on{display:block}
.subtabs{display:flex;gap:6px;margin-bottom:16px}
.stab{padding:6px 13px;font-size:12.5px;border-radius:20px;background:var(--panel);border:1px solid var(--line);color:var(--mut);cursor:pointer}
.stab.on{background:var(--accent);color:#fff;border-color:var(--accent)}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:22px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:13px}
.kpi .l{font-size:11px;color:var(--mut);font-weight:600;margin-bottom:5px}
.kpi .v{font-size:20px;font-weight:700}
.kpi.good .v{color:var(--ok)} .kpi.warn .v{color:var(--warn)} .kpi.bad .v{color:var(--err)}
h2{font-size:15px;margin:26px 0 4px} .note{color:var(--mut);font-size:12.5px;margin:0 0 14px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}
.dgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px}
.dcard{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:15px;cursor:pointer}
.dcard:hover{border-color:var(--accent);background:var(--p2)}
.dcard .d{font-size:15px;font-weight:700;margin-bottom:8px}
.dcard .row{display:flex;justify-content:space-between;font-size:12.5px;color:var(--mut);padding:2px 0}
.dcard .row b{color:var(--ink)} .dcard .go{color:var(--accent);font-size:11.5px;margin-top:8px}
.back{color:var(--accent);cursor:pointer;font-size:13px;margin-bottom:12px;display:inline-block}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{text-align:left;color:var(--mut);font-weight:600;padding:8px 10px;border-bottom:1px solid var(--line);cursor:pointer;white-space:nowrap}
td{padding:7px 10px;border-bottom:1px solid #1e2a36} tr:hover td{background:var(--p2)}
.num{text-align:right;font-variant-numeric:tabular-nums}
.tag{font-size:10px;padding:2px 7px;border-radius:5px;font-weight:600}
.tag.ok{background:#123726;color:#7ee2b0}.tag.beyond{background:#2a3542;color:#93a4b5}.tag.err{background:#4a1d21;color:#ff9ea1}.tag.off{background:#3a2a10;color:#f5c977}
.rankbig{font-weight:700}.rankbig.g{color:var(--gold)}.rankbig.k{color:var(--ok)}
.tier{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:15px;margin-bottom:12px;border-left:4px solid var(--line)}
.tier.t1{border-left-color:var(--gold)}.tier.t2{border-left-color:var(--ok)}.tier.t3{border-left-color:var(--accent)}.tier.t4{border-left-color:var(--faint)}.tier.risk{border-left-color:var(--err)}
.tier h3{margin:0 0 4px;font-size:14px}.tier .desc{font-size:12.5px;color:var(--mut);margin-bottom:10px}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{font-size:12px;padding:4px 10px;border-radius:16px;background:var(--p2);border:1px solid var(--line)}
.chip b{color:var(--gold)}
.act{display:flex;gap:12px;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:13px 15px;margin-bottom:10px}
.act .rn{width:24px;height:24px;border-radius:7px;background:var(--accent);color:#fff;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:12px}
.act .at{font-size:13.5px;font-weight:700;margin-bottom:2px}.act .ad{font-size:12.5px;color:var(--mut)}
.ideacard{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:14px;margin-bottom:10px}
.ideacard .kw{font-size:13.5px;font-weight:700;display:flex;align-items:center;gap:8px;margin-bottom:8px}
.ideacard ul{margin:0;padding-left:18px}.ideacard li{font-size:12.5px;margin:4px 0}
.compkw{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:14px;margin-bottom:10px}
.compkw .h{font-size:13.5px;font-weight:700;margin-bottom:9px;display:flex;align-items:center;gap:8px}
.vid{display:flex;gap:9px;padding:6px 0;border-top:1px solid #1e2a36;font-size:12px}
.vid:first-of-type{border-top:0}.vid .n{color:var(--faint);width:16px;flex-shrink:0}
.vid .tt{flex:1}.vid .cc{color:var(--mut);font-size:11px}
.vid.mine .tt{color:#7ee2b0;font-weight:600}
.pat{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.pat .p{font-size:11px;padding:3px 9px;border-radius:14px;background:#13233a;border:1px solid #24425f;color:#9ec5ff}
.foot{color:var(--faint);font-size:11.5px;margin-top:28px;text-align:center}
@media(max-width:820px){.kpis{grid-template-columns:repeat(3,1fr)}}
@media(max-width:520px){.kpis{grid-template-columns:repeat(2,1fr)}}
</style></head><body><div class="wrap">
<h1>팝성형외과 유튜브 상위노출 대시보드</h1>
<div class="sub">채널 <b id="ch"></b> · <b>성형외과 채널 영상만</b> 집계 · 최신 수집일 <b id="ld"></b> · 추적 키워드 <b id="nk"></b>개 · 생성 <span id="gen"></span></div>
<div class="tabs">
  <div class="tab on" data-v="numbers">📊 수치 대시보드</div>
  <div class="tab" data-v="content">💡 콘텐츠 추천</div>
</div>
<div class="view on" id="view-numbers">
  <div class="subtabs">
    <div class="stab on" data-s="dates">📅 날짜별 보기</div>
    <div class="stab" data-s="trend">📈 전체 추이</div>
  </div>
  <div id="num-dates">
    <p class="note">추적 중인 날짜입니다. 카드를 클릭하면 그 날짜의 키워드별 순위 상세로 이동합니다.</p>
    <div class="dgrid" id="dgrid"></div>
  </div>
  <div id="num-detail" style="display:none">
    <span class="back" id="backBtn">← 날짜 목록으로</span>
    <h2 id="detailDate" style="margin-top:0"></h2>
    <div class="kpis" id="detailKpis"></div>
    <div class="panel" style="padding:6px 10px">
      <table id="detailTable"><thead><tr><th data-k="kw">키워드</th><th data-k="rank" class="num">순위</th><th data-k="st">상태</th></tr></thead><tbody></tbody></table>
    </div>
  </div>
  <div id="num-trend" style="display:none">
    <p class="note">전체 추적 기간의 TOP50 진입 키워드 수 추이입니다.</p>
    <div class="panel"><canvas id="trendCanvas" width="1040" height="180" style="width:100%;height:180px"></canvas></div>
    <h2>키워드 × 날짜 순위 히트맵</h2>
    <div class="panel"><div style="overflow-x:auto"><table id="heat" style="border-collapse:collapse"></table></div></div>
  </div>
</div>
<div class="view" id="view-content">
  <div style="margin:0 0 18px"><span style="font-size:12.5px;color:var(--mut);margin-right:8px">📅 날짜 선택</span><select id="cDate" style="background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:6px 12px;font-size:13px;cursor:pointer"></select></div>
  <div class="kpis" id="cKpis"></div>
  <h2>🎯 우선 액션</h2>
  <p class="note">선택한 날짜의 순위 기준으로 가장 효과가 클 것으로 보이는 순서입니다.</p>
  <div id="actions"></div>
  <h2>📊 기회 · 위험 분석</h2>
  <div id="oppRisk"></div>
  <h2>✍️ 키워드별 콘텐츠 아이디어</h2>
  <div id="ideas"></div>
  <h2>🏥 타병원 상위 콘텐츠 분석</h2>
  <p class="note">각 키워드 상위 3개 경쟁사 영상입니다. (초록색 = 우리 채널)</p>
  <div id="comp"></div>
</div>
<div class="foot">데이터: YouTube Data API · 내 PC에서 매일 자동 수집 · 이 파일을 열면 마지막 수집 결과가 표시됩니다.</div>
</div>
<script id="p" type="application/json">__DATA__</script>
<script>
var P=JSON.parse(document.getElementById('p').textContent);
init(P);
function init(P){
var KW=P.keywords,H=P.history,DATES=P.dates,COMP=P.comp||{},OFF=new Set(P.offtopic||[]);
var latest=DATES[DATES.length-1];
document.getElementById('ch').textContent=P.channel;
document.getElementById('ld').textContent=latest;
document.getElementById('nk').textContent=KW.length;
document.getElementById('gen').textContent=P.generated;
document.querySelectorAll('.tab').forEach(function(t){t.onclick=function(){document.querySelectorAll('.tab').forEach(function(x){x.classList.remove('on');});t.classList.add('on');document.querySelectorAll('.view').forEach(function(v){v.classList.remove('on');});document.getElementById('view-'+t.dataset.v).classList.add('on');};});
document.querySelectorAll('.stab').forEach(function(t){t.onclick=function(){document.querySelectorAll('.stab').forEach(function(x){x.classList.remove('on');});t.classList.add('on');document.getElementById('num-dates').style.display='none';document.getElementById('num-detail').style.display='none';document.getElementById('num-trend').style.display='none';if(t.dataset.s==='dates')document.getElementById('num-dates').style.display='block';else{document.getElementById('num-trend').style.display='block';drawTrend();}};});
function dayStats(d){var h=H[d]||{},ok=0,beyond=0,err=0,sum=0;KW.forEach(function(kw){var v=h[kw];if(!v)return;if(v.s==='ok'){ok++;sum+=v.r;}else if(v.s==='beyond')beyond++;else if(v.s==='error')err++;});return{ok:ok,beyond:beyond,err:err,avg:ok?Math.round(sum/ok):null};}
document.getElementById('dgrid').innerHTML=DATES.slice().reverse().map(function(dt){var s=dayStats(dt);return '<div class="dcard" data-d="'+dt+'"><div class="d">'+dt+(dt===latest?' <span class="tag ok">최신</span>':'')+'</div><div class="row"><span>TOP50 진입</span><b>'+s.ok+'개</b></div><div class="row"><span>평균 순위</span><b>'+(s.avg?s.avg+'위':'—')+'</b></div><div class="row"><span>50위 밖</span><b>'+s.beyond+'개</b></div><div class="row"><span>수집 오류</span><b>'+s.err+'개</b></div><div class="go">상세 보기 →</div></div>';}).join('');
document.querySelectorAll('.dcard').forEach(function(c){c.onclick=function(){showDetail(c.dataset.d);};});
var dSort='rank',dDir=1;
function showDetail(dt){document.getElementById('num-dates').style.display='none';document.getElementById('num-detail').style.display='block';document.getElementById('detailDate').textContent=dt+' 순위 상세';var s=dayStats(dt);document.getElementById('detailKpis').innerHTML=[{l:'TOP50 진입',v:s.ok+'개',c:s.ok?'good':''},{l:'평균 순위',v:s.avg?s.avg+'위':'—'},{l:'50위 밖',v:s.beyond+'개'},{l:'수집 오류',v:s.err+'개',c:s.err?'bad':'good'},{l:'최고 순위',v:(function(){var rs=KW.map(function(k){return H[dt][k];}).filter(function(v){return v&&v.s==='ok';}).map(function(v){return v.r;});return rs.length?Math.min.apply(null,rs)+'위':'—';})(),c:'good'}].map(function(k){return '<div class="kpi '+(k.c||'')+'"><div class="l">'+k.l+'</div><div class="v">'+k.v+'</div></div>';}).join('');renderDetail(dt);}
function renderDetail(dt){var d=H[dt];var rows=KW.map(function(kw){return{kw:kw,r:(d[kw]&&d[kw].s==='ok')?d[kw].r:null,s:d[kw]?d[kw].s:'nodata',off:OFF.has(kw)};});rows.sort(function(a,b){if(dSort==='kw')return dDir*a.kw.localeCompare(b.kw,'ko');if(dSort==='st')return dDir*(''+a.s).localeCompare(''+b.s);return dDir*((a.r===null?999:a.r)-(b.r===null?999:b.r));});document.querySelector('#detailTable tbody').innerHTML=rows.map(function(x){var rk=x.r!==null?'<span class="rankbig '+(x.r<=10?'g':'k')+'">'+x.r+'위</span>':'—';var st=x.s==='ok'?'<span class="tag ok">진입</span>':x.s==='beyond'?'<span class="tag beyond">50위 밖</span>':x.s==='error'?'<span class="tag err">오류</span>':'<span class="tag beyond">-</span>';var off=x.off?' <span class="tag off">의도불일치</span>':'';return '<tr><td>'+x.kw+off+'</td><td class="num">'+rk+'</td><td>'+st+'</td></tr>';}).join('');}
document.querySelectorAll('#detailTable th').forEach(function(th){th.onclick=function(){var k=th.dataset.k;if(k===dSort)dDir*=-1;else{dSort=k;dDir=1;}renderDetail(document.getElementById('detailDate').textContent.split(' ')[0]);};});
document.getElementById('backBtn').onclick=function(){document.getElementById('num-detail').style.display='none';document.getElementById('num-dates').style.display='block';};
function drawTrend(){var cv=document.getElementById('trendCanvas'),ctx=cv.getContext('2d');var W=cv.width,Hh=cv.height,pad=30;ctx.clearRect(0,0,W,Hh);var vals=DATES.map(function(d){return dayStats(d).ok;});var mx=Math.max.apply(null,[5].concat(vals));ctx.strokeStyle='#26333f';ctx.beginPath();ctx.moveTo(pad,Hh-pad);ctx.lineTo(W-10,Hh-pad);ctx.stroke();ctx.font='11px sans-serif';var n=DATES.length;ctx.strokeStyle='#30a46c';ctx.lineWidth=2;ctx.beginPath();DATES.forEach(function(d,i){var x=n>1?pad+i/(n-1)*(W-pad-15):W/2;var y=Hh-pad-(vals[i]/mx)*(Hh-2*pad);if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);});ctx.stroke();DATES.forEach(function(d,i){var x=n>1?pad+i/(n-1)*(W-pad-15):W/2;var y=Hh-pad-(vals[i]/mx)*(Hh-2*pad);ctx.fillStyle='#30a46c';ctx.beginPath();ctx.arc(x,y,3,0,7);ctx.fill();ctx.fillStyle='#93a4b5';ctx.fillText(vals[i],x-4,y-8);if(n<=20||i%Math.ceil(n/20)===0)ctx.fillText(d.slice(5),x-14,Hh-pad+15);});var hh='<tr><th style="font-size:10px;color:#6b7d8f;padding:2px 6px"></th>'+DATES.map(function(d){return '<th style="font-size:9px;color:#6b7d8f;font-weight:400;padding:2px">'+d.slice(5)+'</th>';}).join('')+'</tr>';KW.forEach(function(kw){hh+='<tr><td style="font-size:10px;color:#93a4b5;padding:1px 6px;white-space:nowrap;text-align:right">'+kw+'</td>'+DATES.map(function(d){var v=H[d][kw];var bg=v&&v.s==='ok'?'#30a46c':v&&v.s==='beyond'?'#3b4b5c':v&&v.s==='error'?'#e5484d':'#232e3a';var tt=v&&v.s==='ok'?v.r+'위':v?v.s:'-';return '<td title="'+kw+' '+d+' '+tt+'" style="width:16px;height:15px;background:'+bg+';border:1px solid #0f1720"></td>';}).join('')+'</tr>';});document.getElementById('heat').innerHTML=hh;}
var cSel=document.getElementById('cDate');
cSel.innerHTML=DATES.slice().reverse().map(function(dt){return '<option value="'+dt+'"'+(dt===latest?' selected':'')+'>'+dt+(dt===latest?' (최신)':'')+'</option>';}).join('');
cSel.onchange=function(){renderContent(cSel.value);};
renderContent(latest);
function renderContent(cd){
var d=H[cd]||{};
var COMPD=(P.comphist&&P.comphist[cd])?P.comphist[cd]:COMP;
function rankOf(kw){return(d[kw]&&d[kw].s==='ok')?d[kw].r:null;}
function tier(kw){var r=rankOf(kw);if(r===null)return 4;if(r<=10)return 1;if(r<=30)return 2;return 3;}
var inTop=KW.filter(function(k){return rankOf(k)!==null;});
document.getElementById('cKpis').innerHTML=[{l:'TOP50 진입',v:inTop.length+'개',c:'good'},{l:'TOP10 진입',v:KW.filter(function(k){var r=rankOf(k);return r&&r<=10;}).length+'개',c:'good'},{l:'진입 임박(11-30)',v:KW.filter(function(k){var r=rankOf(k);return r&&r>10&&r<=30;}).length+'개',c:'warn'},{l:'의도 불일치',v:[].concat(Array.from(OFF)).filter(function(k){return KW.indexOf(k)>=0;}).length+'개',c:'bad'},{l:'신규 공략 필요',v:KW.filter(function(k){return rankOf(k)===null&&!OFF.has(k);}).length+'개'}].map(function(k){return '<div class="kpi '+(k.c||'')+'"><div class="l">'+k.l+'</div><div class="v">'+k.v+'</div></div>';}).join('');
var acts=[];
KW.filter(function(k){var r=rankOf(k);return r&&r>10&&r<=20;}).sort(function(a,b){return rankOf(a)-rankOf(b);}).forEach(function(k){acts.push({t:'「'+k+'」 '+rankOf(k)+'위 → TOP10 집중 공략',d:'상위 10위 진입이 눈앞입니다. 이 키워드 전용 콘텐츠를 이번주 1~2편 추가 발행하고, 기존 상위 영상의 제목·썸네일을 키워드가 앞에 오도록 최적화하세요.'});});
KW.filter(function(k){var r=rankOf(k);return r&&r<=10;}).sort(function(a,b){return rankOf(a)-rankOf(b);}).forEach(function(k){acts.push({t:'「'+k+'」 '+rankOf(k)+'위 사수 + 롱테일 확장',d:'이미 상위권입니다. "'+k+'" 세부 주제(후기·회복·비용 등) 시리즈로 상위권을 굳히세요.'});});
var offNow=Array.from(OFF).filter(function(k){return KW.indexOf(k)>=0;});
if(offNow.length)acts.push({t:'의도 불일치 키워드 재검토 ('+offNow.join(', ')+')',d:'이 키워드들은 성형이 아닌 다른 분야가 상위를 차지합니다. 구체적 조합 키워드로 대체를 권장합니다.'});
document.getElementById('actions').innerHTML=acts.slice(0,6).map(function(a,i){return '<div class="act"><div class="rn">'+(i+1)+'</div><div><div class="at">'+a.t+'</div><div class="ad">'+a.d+'</div></div></div>';}).join('')||'<div class="note">이 날짜엔 TOP50 진입 키워드가 없어요.</div>';
function tierList(t){return KW.filter(function(k){return tier(k)===t&&!(t===3&&OFF.has(k));}).sort(function(a,b){return(rankOf(a)==null?999:rankOf(a))-(rankOf(b)==null?999:rankOf(b));});}
var oppHtml=[{cls:'t1',h:'🏆 상위권 (1-10위) — 사수 & 확장',dsc:'이미 상위 노출 중. 롱테일·시리즈로 방어하세요.',ks:tierList(1)},{cls:'t2',h:'🚀 기회 (11-30위) — 조금만 더',dsc:'상위권 진입이 가시권입니다.',ks:tierList(2)},{cls:'t3',h:'🌱 진입 임박 (31-50위)',dsc:'노출이 시작된 단계입니다.',ks:tierList(3)}].map(function(o){return '<div class="tier '+o.cls+'"><h3>'+o.h+'</h3><div class="desc">'+o.dsc+'</div><div class="chips">'+(o.ks.length?o.ks.map(function(k){return '<span class="chip">'+k+' <b>'+rankOf(k)+'위</b></span>';}).join(''):'<span class="note">해당 없음</span>')+'</div></div>';}).join('');
var gap=KW.filter(function(k){return rankOf(k)===null&&!OFF.has(k);});
var riskHtml='<div class="tier t4"><h3>🎯 신규 공략 (50위 밖)</h3><div class="desc">아직 노출되지 않는 키워드입니다. 아래 아이디어를 참고해 콘텐츠를 제작하세요.</div><div class="chips">'+gap.map(function(k){return '<span class="chip">'+k+'</span>';}).join('')+'</div></div>';
document.getElementById('oppRisk').innerHTML=oppHtml+riskHtml;
var IDEAS=[function(kw){return '「'+kw+'」 전후 사진 + 실제 회복 과정 (수술직후~1개월)';},function(kw){return '「'+kw+'」 부작용·오해, 전문의가 팩트체크';},function(kw){return '「'+kw+'」 vs 다른 방법 비교 — 자가진단 체크리스트';},function(kw){return '「'+kw+'」 비용·수술시간·회복기간 1분 총정리 Q&A';},function(kw){return '「'+kw+'」 이런 분께 추천 / 이런 분은 비추천';},function(kw){return '「'+kw+'」 실제 후기 인터뷰';},function(kw){return '「'+kw+'」 자주 묻는 질문 TOP5 #shorts';}];
function ideasFor(kw,seed){var o=[];for(var i=0;i<3;i++)o.push(IDEAS[(seed+i*2)%IDEAS.length](kw));return o;}
var tierLabel={1:'🏆 상위권',2:'🚀 기회',3:'🌱 진입임박',4:'🎯 신규공략'};
var ideaKws=tierList(2).concat(tierList(3)).concat(KW.filter(function(k){return tier(k)===4&&!OFF.has(k);})).concat(tierList(1)).slice(0,24);
document.getElementById('ideas').innerHTML=ideaKws.map(function(kw,idx){var r=rankOf(kw),t=tier(kw);return '<div class="ideacard"><div class="kw">'+kw+' <span class="tag '+(r?'ok':'beyond')+'">'+(r?r+'위':'미진입')+'</span> <span style="font-size:11px;color:var(--faint)">'+tierLabel[t]+'</span></div><ul>'+ideasFor(kw,idx).map(function(x){return '<li>'+x+'</li>';}).join('')+'</ul></div>';}).join('');
var PATTERNS=[{re:/vs|VS|비교|차이/,label:'비교(VS)'},{re:/총정리|정리|모든것/,label:'총정리'},{re:/자가진단|진단|체크|내 눈|내눈/,label:'자가진단'},{re:/부작용|오해|사기|진실|하지마|후회|실패/,label:'부작용·오해'},{re:/Q&A|QnA|질문|묻는/i,label:'Q&A'},{re:/후기|경과|전후|리뷰/,label:'후기·전후'},{re:/shorts|쇼츠/i,label:'쇼츠'},{re:/추천|비추천|이런분/,label:'추천/비추천'}];
var compKws=Object.keys(COMPD).filter(function(k){return COMPD[k]&&COMPD[k].length;});
document.getElementById('comp').innerHTML=compKws.length?compKws.map(function(kw){var vids=COMPD[kw],r=rankOf(kw),patt={};vids.forEach(function(v){PATTERNS.forEach(function(p){if(p.re.test(v.t))patt[p.label]=1;});});var off=OFF.has(kw);return '<div class="compkw"><div class="h">'+kw+' <span class="tag '+(r?'ok':'beyond')+'">'+(r?'우리 '+r+'위':'우리 미진입')+'</span>'+(off?' <span class="tag off">의도불일치</span>':'')+'</div>'+vids.map(function(v,i){return '<div class="vid '+(v.m?'mine':'')+'"><span class="n">'+(i+1)+'</span><div><div class="tt">'+v.t+(v.m?' ✅':'')+'</div><div class="cc">'+v.c+'</div></div></div>';}).join('')+(Object.keys(patt).length?'<div class="pat">'+Object.keys(patt).map(function(p){return '<span class="p">#'+p+'</span>';}).join('')+'</div>':'')+'</div>';}).join(''):'<div class="note">이 날짜엔 경쟁사 스냅샷이 없어요. (수집기 보강 후 날짜부터 날짜별로 쌓여요.)</div>';
}
}
</script></body></html>"""


if __name__ == "__main__":
    main()
