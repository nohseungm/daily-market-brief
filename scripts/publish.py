#!/usr/bin/env python3
"""posts/<날짜>/ 중 승인(approved=true)됐고 아직 게시 안 된 캐러셀을 인스타그램에 게시한다.
GitHub Actions에서 실행. 필요한 환경변수: IG_USER_ID, IG_ACCESS_TOKEN, PAGES_BASE
옵션: DRY_RUN=1 이면 API 호출 없이 점검만.
"""
import json, os, sys, time, glob, urllib.request, urllib.parse, urllib.error

API = "https://graph.instagram.com/v25.0"
DRY = os.environ.get("DRY_RUN") == "1"
UID = os.environ.get("IG_USER_ID", "")
TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
BASE = os.environ.get("PAGES_BASE", "").rstrip("/")


def call(method, path, params=None):
    params = dict(params or {})
    params["access_token"] = TOKEN
    data = urllib.parse.urlencode(params).encode()
    url = f"{API}/{path}"
    if method == "GET":
        req = urllib.request.Request(f"{url}?{data.decode()}")
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace").replace(TOKEN, "***")
        sys.exit(f"Instagram API 오류 {e.code} on {path}: {body}")


def wait_public(url, limit=900):
    """GitHub Pages 배포가 끝나 이미지가 공개될 때까지 대기"""
    t0 = time.time()
    while time.time() - t0 < limit:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=20) as r:
                if r.status == 200 and "image/jpeg" in r.headers.get("Content-Type", ""):
                    return
        except Exception:
            pass
        time.sleep(15)
    sys.exit(f"이미지가 공개되지 않음(Pages 배포 확인 필요): {url}")


def wait_container(cid, limit=300):
    t0 = time.time()
    while time.time() - t0 < limit:
        st = call("GET", cid, {"fields": "status_code"}).get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            sys.exit(f"컨테이너 {cid} 상태 {st}")
        time.sleep(5)
    sys.exit(f"컨테이너 {cid} 처리 시간 초과")


def pending_posts():
    for m in sorted(glob.glob("posts/*/manifest.json")):
        d = os.path.dirname(m)
        man = json.load(open(m, encoding="utf-8"))
        if man.get("approved") is True and not os.path.exists(f"{d}/published.json"):
            yield d, man


def main():
    if not DRY and not (UID and TOKEN and BASE):
        sys.exit("IG_USER_ID / IG_ACCESS_TOKEN / PAGES_BASE 설정 필요")
    posts = list(pending_posts())
    if not posts:
        print("게시할 항목 없음")
        return
    for d, man in posts[-1:]:  # 가장 최신 1건만 (밀린 과거 글 일괄 게시 방지)
        caption = open(f"{d}/{man['caption_file']}", encoding="utf-8").read()
        urls = [f"{BASE}/{d}/{img}" for img in man["images"]]
        assert 2 <= len(urls) <= 10, "캐러셀은 2~10장"
        assert len(caption) <= 2200
        print(f"[{d}] {len(urls)}장 게시 준비")
        if DRY:
            print("DRY_RUN: ", urls)
            continue
        for u in urls:
            wait_public(u)
        children = []
        for u in urls:
            cid = call("POST", f"{UID}/media", {"image_url": u, "is_carousel_item": "true"})["id"]
            wait_container(cid)
            children.append(cid)
        car = call("POST", f"{UID}/media", {"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption})["id"]
        wait_container(car)
        media = call("POST", f"{UID}/media_publish", {"creation_id": car})["id"]
        link = call("GET", media, {"fields": "permalink"}).get("permalink", "")
        json.dump({"media_id": media, "permalink": link, "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
                  open(f"{d}/published.json", "w"), indent=1)
        print(f"게시 완료: {link}")


if __name__ == "__main__":
    main()
