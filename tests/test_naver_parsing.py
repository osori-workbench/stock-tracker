from stock_tracker.naver import parse_investor_rows, parse_top_volume_rows


INVESTOR_HTML = """
<table class=\"type_1\">
  <tr class=\"udline\"><th>시간</th><th>개인</th><th>외국인</th><th>기관계</th><th colspan=\"6\">기관</th><th>기타법인</th></tr>
  <tr class=\"udline\"><th>금융투자</th><th>보험</th><th>투신<br>(사모)</th><th>은행</th><th>기타금융기관</th><th>연기금등</th></tr>
  <tr><td colspan=\"11\" class=\"blank_07\"></td></tr>
  <tr><td>15:58</td><td>66,821</td><td>-56,092</td><td>-12,138</td><td>-6,206</td><td>-1,420</td><td>-2,476</td><td>-110</td><td>-70</td><td>-1,857</td><td>1,409</td></tr>
  <tr><td>15:57</td><td>66,822</td><td>-56,092</td><td>-12,139</td><td>-6,206</td><td>-1,420</td><td>-2,476</td><td>-110</td><td>-70</td><td>-1,857</td><td>1,409</td></tr>
</table>
"""

TOP_VOLUME_HTML = """
<table class=\"type_2\">
  <tr><th>순위</th></tr>
  <tr>
    <td>1</td>
    <td><a class=\"tltle\" href=\"/item/main.naver?code=005930\">삼성전자</a></td>
    <td>71,200</td><td>상승</td><td>+1.24%</td>
  </tr>
  <tr>
    <td>2</td>
    <td><a class=\"tltle\" href=\"/item/main.naver?code=000660\">SK하이닉스</a></td>
    <td>201,500</td><td>상승</td><td>+2.10%</td>
  </tr>
</table>
"""


def test_parse_investor_rows_returns_most_recent_snapshot() -> None:
    row = parse_investor_rows(INVESTOR_HTML)

    assert row.basis_label == "15:58"
    assert row.individual == 66821
    assert row.foreign == -56092
    assert row.pension == -1857


def test_parse_top_volume_rows_returns_stock_rows() -> None:
    rows = parse_top_volume_rows(TOP_VOLUME_HTML, limit=2)

    assert [row.code for row in rows] == ["005930", "000660"]
    assert rows[0].name == "삼성전자"
    assert rows[1].change_percent == 2.10
