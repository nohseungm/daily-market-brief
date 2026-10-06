# Daily Market Brief — 인스타 카드뉴스 자동 게시

> 이 공개 저장소에는 **게시용 코드와 이미지만** 있습니다. 조사·재검증·카드 생성 로직은 비공개(Claude 예약 작업)에 있습니다.

매일 아침 Claude가 세계·미국·국내 증시 팩트를 조사 → **독립 재검증** → 카드뉴스(JPEG) 생성 → 이 저장소에 push →
GitHub Actions가 인스타그램에 캐러셀로 게시합니다. 전부 무료 구성입니다.

```
Claude 예약 작업 (06:52 KST, 비공개)
  ├─ 1. 조사: 기사·공식 데이터로 초안(draft.json) 작성. 모든 숫자는 {fact_id}로만 카드에 들어감
  ├─ 2. 블라인드 재검증: 값을 가린 질문지 → 별도 에이전트가 처음부터 다시 조사
  ├─ 3. verify.py 대조: 불일치·근거 부족·목록에 없는 숫자 → 게시 보류
  ├─ 4. render.py: 1080×1350 JPEG + caption + manifest(approved)
  └─ 5. git push posts/YYYY-MM-DD/
GitHub Pages → 이미지 공개 URL
GitHub Actions(publish.yml) → Instagram API로 캐러셀 게시 → published.json 기록
GitHub Actions(refresh-token.yml) → 매달 2번 토큰 자동 갱신
```

## 1회 설정 (약 30분)

### A. 인스타그램
1. 인스타 앱 → 설정 → 계정 유형 → **프로페셔널 계정(크리에이터 또는 비즈니스)** 으로 전환 (무료)

### B. Meta 개발자 앱
1. https://developers.facebook.com 가입 → **앱 만들기** → 사용 사례에서 *Instagram에서 메시지 및 콘텐츠 관리* 선택
2. **Instagram API with Instagram Login** 설정 화면에서
   - *Instagram 테스터* 또는 *계정 추가*로 본인 인스타 계정 연결 (본인 계정만 쓰면 앱 검수 불필요)
   - 권한 `instagram_business_basic`, `instagram_business_content_publish` 포함
   - **액세스 토큰 생성** → 장기 토큰(60일) 복사
3. 같은 화면에 나오는 **Instagram 사용자 ID**(숫자) 복사

### C. GitHub
1. 이 폴더를 **공개(public)** 저장소 `daily-market-brief` 로 업로드 (Pages·Actions 무료 조건)
2. Settings → Pages → *Deploy from a branch* → `main` / `(root)` 저장
3. Settings → Secrets and variables → Actions → New repository secret
   - `IG_USER_ID` = B-3의 숫자 ID
   - `IG_ACCESS_TOKEN` = B-2의 장기 토큰
   - `GH_PAT_SECRETS` = 토큰 자동 갱신용 PAT (아래 D-2)
4. Settings → Actions → General → Workflow permissions → **Read and write** 선택

### D. 토큰 2개 (Fine-grained PAT, github.com/settings/personal-access-tokens)
1. **Claude push용**: Repository access = 이 저장소만, Permissions → *Contents: Read and write*. 만료 90일 → Claude 예약 작업 설정의 GITHUB_PUSH_TOKEN 자리에 직접 입력 (채팅에 붙여넣지 않기)
2. **토큰 갱신용(GH_PAT_SECRETS)**: 이 저장소만, Permissions → *Secrets: Read and write*. Claude에게 주지 말고 Secret에만 저장

### E. 테스트
Actions 탭 → *Publish to Instagram* → Run workflow. `posts/` 에 승인된 글이 없으면 "게시할 항목 없음"으로 끝나면 정상.

## 안전장치
- 핵심 수치(지수 종가·등락률·환율·금리·휴장 여부)가 하나라도 재검증 불일치/근거 부족이면 **push 자체를 하지 않음** → 알림만
- 카드·캡션에 팩트 목록에 없는 숫자가 있으면 게시 보류 (`verify.py` 커버리지 검사)
- 게시 기록(`published.json`)이 있는 날짜는 다시 게시하지 않음, 밀린 글은 최신 1건만
- 인스타 토큰은 GitHub Secrets에만 존재 (Claude는 모름)

## 공개 저장소 보안 체크
- Settings → Code security → **Secret scanning / Push protection** 켜기 (공개 저장소 무료) — 실수로 토큰이 커밋되면 push 차단
- Settings → Actions → General → *Fork pull request workflows*: 외부 기여자 승인 필수(기본값) 유지
- 이 저장소의 워크플로는 `pull_request`로 실행되지 않으므로 남이 PR을 보내도 Secrets에 접근 못 함
- 저장소 쓰기 권한은 본인만 (Collaborators 추가 금지)

## 수동으로 보류/게시
- 보류: 해당 `posts/날짜/manifest.json`의 `approved`를 `false`로 커밋
- 다시 게시 시도: Actions → Publish to Instagram → Run workflow
