from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_extract_bundle_and_baseball_market_catalog():
    from data.tsl_frontend_probe import (
        extract_api_endpoints,
        extract_baseball_market_catalog,
        extract_bundle_url,
    )

    html = """
    <html>
      <head></head>
      <body>
        <script type="module" crossorigin src="/assets/index-2x4cx3Nd.js"></script>
      </body>
    </html>
    """
    bundle_js = """
    const Si=Ut.create({baseURL:"https://blob3rd.sportslottery.com.tw/apidata",timeout:"10000"}),
    Cf=Ut.create({baseURL:"https://api3rd.sportslottery.com.tw",timeout:"10000"}),
    GL=(e,t)=>Si.get(`/Pre/${e}-Games.${t}.json`),
    qL=e=>Si.get(`/Live/Games.${e}.json`),
    QF=(e,t,n)=>Cf.post("/services/content/get",{type:e,id:t,language:n=="zh"?"ZH":"UK"},Tf(n)),
    YF=(e,t)=>Cf.post("/api/betting/fo/bookbetslip",e,Tf(t)),
    WL=()=>{V("34731.1","354",U.main,Z.ppl,1,1),V("34731.1","358",U.name,Z.ppl,1,1,"h"),V("34731.1","377",U.name,Z.f5i,0,0,"h")}
    """

    bundle_url = extract_bundle_url(html)
    assert bundle_url == "https://www.sportslottery.com.tw/assets/index-2x4cx3Nd.js"

    endpoints = extract_api_endpoints(bundle_js)
    assert "https://blob3rd.sportslottery.com.tw/apidata" in endpoints
    assert "https://api3rd.sportslottery.com.tw" in endpoints
    assert "/services/content/get" in endpoints
    assert "/api/betting/fo/bookbetslip" in endpoints

    catalog = extract_baseball_market_catalog(bundle_js)
    assert len(catalog) == 3
    assert catalog[0]["market_type_id"] == "354"
    assert catalog[0]["show_on_pre_list"] == 1
    assert catalog[1]["type_key"] == "h"
    assert catalog[2]["filter_key"] == "f5i"
