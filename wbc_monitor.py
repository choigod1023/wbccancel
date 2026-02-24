#!/usr/bin/env python3
"""
WBC 2026 티켓 매수 건수 모니터링
https://tradead.tixplus.jp/wbc2026 페이지의 매수가(件) 변경 시 Discord 알림 전송
"""

import os
import re
import json
import time
import html
import requests
from pathlib import Path
from datetime import datetime

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

# 설정
BASE_URL = "https://tradead.tixplus.jp/wbc2026"
STATE_FILE = Path(__file__).parent / "wbc_state.json"
# 체크 간격(초). 너무 짧으면 서버가 봇으로 인식해 빈 페이지/차단할 수 있음
_raw_interval = int(os.environ.get("WBC_INTERVAL", "60"))
INTERVAL_SEC = max(30, _raw_interval)  # 최소 30초
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")

# 한일전 / 한국 vs 대만 경기 ID
TARGET_CONCERT_IDS = {1519, 1520}

# 件(건) 숫자 추출 정규식
PATTERN_COUNT = re.compile(r"(\d+)\s*件")


# 요청이 봇으로 인식되면 빈 페이지/차단될 수 있으므로 브라우저와 비슷한 헤더 사용
FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}


def fetch_page():
    """페이지 HTML 가져오기. 반환: (status_code, html_text)"""
    r = requests.get(BASE_URL, headers=FETCH_HEADERS, timeout=15)
    r.raise_for_status()
    return r.status_code, r.text


def parse_counts(html_text: str, debug: bool = False) -> tuple[list[dict], str]:
    """
    data-page JSON 에서 날짜·시간·매수 건수(listings_count) 추출.
    반환: (결과 리스트, 디버그 메시지)
    """
    if not BeautifulSoup:
        return [], "BeautifulSoup4가 설치되지 않았습니다. 'pip install beautifulsoup4' 실행 필요"

    soup = BeautifulSoup(html_text, "html.parser")
    app_div = soup.find("div", id="app")
    if not app_div:
        return [], "div#app 요소를 찾을 수 없습니다"
    if "data-page" not in app_div.attrs:
        return [], "div#app에 data-page 속성이 없습니다"

    # HTML 엔티티(&quot; 등) 제거 후 JSON 파싱
    raw = app_div["data-page"]
    try:
        data_json = html.unescape(raw)
        data = json.loads(data_json)
    except json.JSONDecodeError as e:
        return [], f"data-page JSON 파싱 실패: {e}. data-page 길이: {len(raw)}자"
    except Exception as e:
        return [], f"data-page 처리 중 오류: {e}"

    props = data.get("props", {})
    concerts = props.get("concerts", [])
    
    if not concerts:
        return [], f"concerts 배열이 비어있습니다. props 키: {list(props.keys())}"

    result: list[dict] = []
    for c in concerts:
        # listings_count: 그 경기의 총 리세일 매물 건수
        count = c.get("listings_count", 0)
        concert_id = c.get("id")
        name = c.get("name") or ""
        # 날짜/시간은 웹 포맷 사용
        date_str = c.get("concert_date_web_format") or c.get("concert_date")
        # "2026年03月02日" 같이 들어오면 보기 좋게 가공
        if isinstance(date_str, str) and "年" in date_str and "月" in date_str and "日" in date_str:
            # 2026年03月02日 -> 03-02 식으로 단순 변환
            try:
                # 연/월/일만 잘라 쓰거나, 그대로 써도 됨
                # 여기서는 "03/02" 정도만 쓰자
                _, rest = date_str.split("年", 1)
                month, rest2 = rest.split("月", 1)
                day = rest2.split("日", 1)[0]
                date_display = f"{int(month):02d}/{int(day):02d}"
            except Exception:
                date_display = date_str
        else:
            date_display = date_str or "?"

        time_str = c.get("start_time_web_format") or c.get("start_time") or "?"

        result.append(
            {
                "id": concert_id,
                "date": date_display,
                "time": time_str,
                "name": name,
                "count": int(count) if isinstance(count, (int, float, str)) and str(count).isdigit() else 0,
            }
        )

    # 키(date_time) 기준 중복 제거
    seen_keys = set()
    unique: list[dict] = []
    for c in result:
        k = state_key(c)
        if k not in seen_keys:
            seen_keys.add(k)
            unique.append(c)
    return unique, ""


def get_state() -> dict:
    """저장된 이전 상태 로드"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"counts": [], "updated": None}


def save_state(counts: list[dict]):
    """현재 상태 저장"""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "counts": counts,
            "updated": datetime.now().isoformat(),
        }, f, ensure_ascii=False, indent=2)


def state_key(c: dict) -> str:
    return f"{c['date']}_{c['time']}"


def detect_changes(old: list[dict], new: list[dict]) -> list[tuple[dict, dict]]:
    """이전 상태와 비교해 변경된 항목 (old_item, new_item) 리스트 반환"""
    old_by_key = {state_key(c): c for c in old}
    changes = []
    for c in new:
        k = state_key(c)
        if k in old_by_key and old_by_key[k]["count"] != c["count"]:
            changes.append((old_by_key[k], c))
        elif k not in old_by_key and c["count"] > 0:
            # 새로 생긴 공급
            changes.append(({"date": c["date"], "time": c["time"], "count": 0}, c))
    return changes


def send_discord(changes: list[tuple[dict, dict]], new_counts: list[dict]):
    """Discord 웹훅으로 알림 전송"""
    if not DISCORD_WEBHOOK.strip():
        print("[경고] DISCORD_WEBHOOK_URL 미설정 — 알림 생략")
        return
    lines = []
    mention_everyone = False
    for old_c, new_c in changes:
        name = new_c.get("name") or ""
        title = f"{new_c['date']} {new_c['time']}"
        if name:
            title += f" | {name}"

        # 한일전(1519), 한국 vs 대만(1520) 경기에서 0 -> 양수로 바뀐 경우 @everyone
        new_id = new_c.get("id")
        if (
            isinstance(new_id, int)
            and new_id in TARGET_CONCERT_IDS
            and old_c.get("count", 0) == 0
            and new_c.get("count", 0) > 0
        ):
            mention_everyone = True

        lines.append(
            f"• **{title}** — {old_c['count']}件 → **{new_c['count']}件**"
        )
    # 현재 1건 이상인 항목 요약
    available = [c for c in new_counts if c["count"] > 0]
    body = "**매수 건수 변경**\n\n" + "\n".join(lines)
    if available:
        body += "\n\n**현재 매수 가능**\n" + "\n".join(
            f"• {c['date']} {c['time']} | {c.get('name','')}: {c['count']}件" for c in available
        )

    content = "@everyone" if mention_everyone else None
    payload = {
        "content": content,
        "embeds": [{
            "title": "WBC 2026 티켓 매수 건수 변경",
            "description": body,
            "color": 0x00AA00,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "url": BASE_URL,
        }],
    }
    if mention_everyone:
        payload["allowed_mentions"] = {"parse": ["everyone"]}
    try:
        r = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
        if r.status_code in (200, 204):
            print("[Discord] 알림 전송 완료")
        else:
            print(f"[Discord] 전송 실패: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"[Discord] 오류: {e}")


def run_once():
    """한 번 조회 후 변경 여부 확인 및 알림"""
    html = None
    status_code = None
    for attempt in range(2):
        try:
            status_code, html = fetch_page()
            break
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else "?"
            print(f"[오류] 페이지 조회 실패 (시도 {attempt + 1}/2) — HTTP {code}: {e}")
            if attempt == 0:
                time.sleep(2)
            else:
                return
        except Exception as e:
            print(f"[오류] 페이지 조회 실패 (시도 {attempt + 1}/2): {e}")
            if attempt == 0:
                time.sleep(2)
            else:
                return
    if not html:
        return
    new_counts, debug_msg = parse_counts(html)
    if not new_counts:
        # 디버그를 위해 마지막 HTML을 파일로 저장 (html/ 폴더에 저장해 브라우저에서 열기 쉽게)
        html_dir = Path(__file__).parent / "html"
        html_dir.mkdir(exist_ok=True)
        debug_file = html_dir / "wbc_last.html"
        try:
            debug_file.write_text(html, encoding="utf-8")
            print("[경고] 매수 건수 항목을 찾지 못했습니다.")
            if status_code is not None:
                print(f"       HTTP 상태 코드: {status_code}")
            # debug_msg가 비어있어도 파싱 실패 원인을 추적할 수 있도록 상세 정보 출력
            if debug_msg:
                print(f"       원인: {debug_msg}")
            else:
                # 파싱은 성공했지만 결과가 비어있는 경우
                print("       원인: 파싱은 성공했지만 결과 리스트가 비어있습니다.")
                # HTML 구조 확인
                if "data-page" in html:
                    print("       [참고] HTML에 data-page 속성이 있습니다.")
                    if 'div id="app"' in html:
                        print("       [참고] div#app 요소도 있습니다. JSON 구조를 확인해보세요.")
                else:
                    print("       [참고] HTML에 data-page 속성이 없습니다.")
            print(f"       응답 HTML을 '{debug_file}' 에 저장했습니다. 브라우저로 열어 구조를 확인해 보세요.")
        except Exception as e:
            print("[경고] 매수 건수 항목을 찾지 못했고, 디버그 HTML 저장에도 실패했습니다:", e)
        return
    prev = get_state()
    old_counts = prev.get("counts") or []
    changes = detect_changes(old_counts, new_counts)
    if changes:
        print(f"[변경 감지] {len(changes)}건 — Discord 알림 전송")
        send_discord(changes, new_counts)
    else:
        total = sum(c["count"] for c in new_counts)
        print(f"[확인] 변경 없음 (현재 총 매수 가능: {total}件)")
    save_state(new_counts)


def main():
    print("WBC 2026 티켓 매수 건수 모니터 시작")
    print(f"  URL: {BASE_URL}")
    print(f"  체크 간격: {INTERVAL_SEC}초")
    if _raw_interval < 30:
        print(f"  [참고] WBC_INTERVAL이 30초 미만이어서 30초로 적용됩니다. 너무 짧으면 서버에서 빈 페이지/차단될 수 있습니다.")
    print(f"  Discord: {'설정됨' if DISCORD_WEBHOOK.strip() else '미설정'}")
    print("-" * 50)
    while True:
        run_once()
        time.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    main()
