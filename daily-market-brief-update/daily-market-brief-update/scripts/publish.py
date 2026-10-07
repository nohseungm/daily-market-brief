#!/usr/bin/env python3
"""posts/<날짜>/ 중 승인(approved=true)됐고 아직 게시 안 된 글을 게시한다. GitHub Actions에서 실행.
1) 인스타 캐러셀 (필수 — 실패하면 작업 실패)
2) 인스타 스토리 (manifest.story 이미지가 있으면)          ┐ 부가 게시: 실패해도 캐러셀 기록은 남기고
3) 인스타 릴스   (reel.mp4가 있으면 — 일요일에만 생성됨)    │ 결과를 published.json의 extras에 적는다.
4) 스레드 캐러셀 (THREADS_ACCESS_TOKEN이 설정돼 있으면)     ┘
환경변수: IG_USER_ID, IG_ACCESS_TOKEN, PAGES_BASE, (선택) THREADS_ACCESS_TOKEN
옵션: DRY_RUN=1 이면 API 호출 없이 점검만.
"""
import json, os, sys, time, glob, re, unicodedata, urllib.request, urllib.parse, urllib.error

IG = "https://graph.instagram.com/v25.0"
TH = "https://graph.threads.net/v1.0"
DRY = os.environ.get("DRY_RUN") == "1"
UID = os.environ.get("IG_USER_ID", "")
TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
TH_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "").strip()
BASE = os.environ.get("PAGES_BASE", "").rstrip("/")


class ApiError(Exception):
    pass


def call(method, path, params=None, api=IG, token=None):
    token = token or TOKEN
    params = dict(params or {})
    params["access_token"] = token
    data = urllib.parse.urlencode(params).encode()
    url = f"{api}/{path}"
    req = urllib.request.Request(f"{url}?{data.decode()}") if method == "GET" else \
        urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        for t in (TOKEN, TH_TOKEN):
            if t:
                body = body.replace(t, "***")
        raise ApiError(f"API 오류 {e.code} on {path.split('?')[0]}: {body[:500]}")


def wait_public(url, ctype="image/jpeg", limit=900):
    """GitHub Pages 배포가 끝나 파일이 공개될 때까지 대기"""
    t0 = time.time()
    while time.time() - t0 < limit:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=20) as r:
                if r.status == 200 and ctype in r.headers.get("Content-Type", ""):
                    return
        except Exception:
            pass
        time.sleep(15)
    raise ApiError(f"파일이 공개되지 않음(Pages 배포 확인 필요): {url}")


def wait_ig(cid, limit=300):
    t0 = time.time()
    while time.time() - t0 < limit:
        st = call("GET", cid, {"fields": "status_code"}).get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise ApiError(f"컨테이너 {cid} 상태 {st}")
        time.sleep(5)
    raise ApiError(f"컨테이너 {cid} 처리 시간 초과")


def wait_th(cid, limit=300):
    t0 = time.time()
    while time.time() - t0 < limit:
        st = call("GET", cid, {"fields": "status,error_message"}, api=TH, token=TH_TOKEN)
        if st.get("status") in ("FINISHED", "PUBLISHED"):
            return
        if st.get("status") in ("ERROR", "EXPIRED"):
            raise ApiError(f"스레드 컨테이너 {cid} 상태 {st}")
        time.sleep(5)
    raise ApiError(f"스레드 컨테이너 {cid} 처리 시간 초과")


def th_len(s):
    """스레드 글자 수(이모지는 UTF-8 바이트로 셈 — 보수적으로 계산)"""
    return sum(len(ch.encode()) if ord(ch) > 0xFFFF or unicodedata.category(ch) == "So" else 1 for ch in s)


def threads_text(caption, link, limit=500):
    lines = [l for l in caption.strip().splitlines() if not re.fullmatch(r"\s*(#\S+\s*)+", l)]
    tail = f"\n\n카드뉴스 전체 ▶ {link}" if link else ""
    while lines and th_len("\n".join(lines).strip() + tail) > limit:
        lines.pop(-2 if len(lines) > 1 else -1)  # 마지막 줄(면책 문구)은 유지하고 그 앞부터 줄인다
    return ("\n".join(lines).strip() + tail)[:limit]


def pending_posts():
    for m in sorted(glob.glob("posts/*/manifest.json")):
        d = os.path.dirname(m)
        man = json.load(open(m, encoding="utf-8"))
        if man.get("approved") is True and not os.path.exists(f"{d}/published.json"):
            yield d, man


def post_carousel(urls, caption):
    for u in urls:
        wait_public(u)
    children = []
    for u in urls:
        cid = call("POST", f"{UID}/media", {"image_url": u, "is_carousel_item": "true"})["id"]
        wait_ig(cid)
        children.append(cid)
    car = call("POST", f"{UID}/media", {"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption})["id"]
    wait_ig(car)
    media = call("POST", f"{UID}/media_publish", {"creation_id": car})["id"]
    return media, call("GET", media, {"fields": "permalink"}).get("permalink", "")


def post_story(url):
    wait_public(url)
    cid = call("POST", f"{UID}/media", {"media_type": "STORIES", "image_url": url})["id"]
    wait_ig(cid)
    return {"media_id": call("POST", f"{UID}/media_publish", {"creation_id": cid})["id"]}


def post_reel(url, caption):
    wait_public(url, ctype="video/mp4")
    cid = call("POST", f"{UID}/media", {"media_type": "REELS", "video_url": url, "caption": caption,
                                         "share_to_feed": "true"})["id"]
    wait_ig(cid, limit=900)
    media = call("POST", f"{UID}/media_publish", {"creation_id": cid})["id"]
    return {"media_id": media, "permalink": call("GET", media, {"fields": "permalink"}).get("permalink", "")}


def post_threads(urls, text):
    children = []
    for u in urls:
        children.append(call("POST", "me/threads", {"media_type": "IMAGE", "image_url": u, "is_carousel_item": "true"},
                             api=TH, token=TH_TOKEN)["id"])
    for c in children:
        wait_th(c)
    car = call("POST", "me/threads", {"media_type": "CAROUSEL", "children": ",".join(children), "text": text},
               api=TH, token=TH_TOKEN)["id"]
    wait_th(car)
    time.sleep(30)  # 공식 권장: 게시 전 약 30초 대기
    media = call("POST", "me/threads_publish", {"creation_id": car}, api=TH, token=TH_TOKEN)["id"]
    link = call("GET", media, {"fields": "permalink"}, api=TH, token=TH_TOKEN).get("permalink", "")
    return {"media_id": media, "permalink": link}


def main():
    if not DRY and not (UID and TOKEN and BASE):
        sys.exit("IG_USER_ID / IG_ACCESS_TOKEN / PAGES_BASE 설정 필요")
    posts = list(pending_posts())
    if not posts:
        print("게시할 항목 없음")
        return
    d, man = posts[-1]  # 가장 최신 1건만 (밀린 과거 글 일괄 게시 방지)
    caption = open(f"{d}/{man['caption_file']}", encoding="utf-8").read()
    urls = [f"{BASE}/{d}/{img}" for img in man["images"]]
    assert 2 <= len(urls) <= 10, "캐러셀은 2~10장"
    assert len(caption) <= 2200
    story = man.get("story") if man.get("story") and os.path.exists(f"{d}/{man['story']}") else None
    reel = os.path.exists(f"{d}/reel.mp4")
    print(f"[{d}] 캐러셀 {len(urls)}장 · 스토리 {'O' if story else 'X'} · 릴스 {'O' if reel else 'X'} · "
          f"스레드 {'O' if TH_TOKEN else 'X(토큰 없음)'}")
    if DRY:
        print("DRY_RUN:", urls)
        print("스레드 본문 미리보기:\n" + threads_text(caption, "https://www.instagram.com/p/EXAMPLE/"))
        return
    try:
        media, link = post_carousel(urls, caption)
    except ApiError as e:
        sys.exit(f"캐러셀 게시 실패: {e}")
    print(f"캐러셀 게시 완료: {link}")
    rec = {"media_id": media, "permalink": link, "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "extras": {}}
    jobs = []
    if story:
        jobs.append(("story", lambda: post_story(f"{BASE}/{d}/{story}")))
    if reel:
        jobs.append(("reel", lambda: post_reel(f"{BASE}/{d}/reel.mp4", caption)))
    if TH_TOKEN:
        jobs.append(("threads", lambda: post_threads(urls, threads_text(caption, link))))
    failed = []
    for name, fn in jobs:
        try:
            rec["extras"][name] = fn()
            print(f"{name} 게시 완료: {rec['extras'][name]}")
        except Exception as e:  # 부가 게시 실패는 기록만 하고 계속
            rec["extras"][name] = {"error": str(e)[:500]}
            failed.append(name)
            print(f"::warning::{name} 게시 실패: {str(e)[:300]}")
    json.dump(rec, open(f"{d}/published.json", "w"), ensure_ascii=False, indent=1)
    if failed:
        print(f"부가 게시 실패: {failed} (캐러셀은 정상 게시됨)")


if __name__ == "__main__":
    main()
