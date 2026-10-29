# fixtures (offline 모드용 가상 데이터)

실제 공고가 아닙니다. 각 사이트의 **실제 응답 형식**을 흉내 낸 가상 데이터라서,
offline 실행에서도 파서(agent/sources/*)까지 그대로 검증됩니다. 기준일 TODAY=2026-11-02.

| 파일 | 형식 | 시나리오 |
|---|---|---|
| dacon_list.html | DACON 목록 페이지의 `window.__NUXT__` | 정상 1, 마감 지남 1, 오늘 마감(상금 정보 없음) 1 |
| dacon_detail_*.html | DACON 상세 페이지의 `window.__NUXT__` | 규칙·일정·상금 등 섹션 |
| daker_list.json | `GET /api/hackathons/public-list` | 정상 1, 비공개 1(제외) |
| daker_detail_*.json | `GET /api/hackathons/{slug}` | 섹션 + stages(일정) |
| dev_event.md | Dev-Event README.md | 재게시 중복, 대회 아닌 행사, 상대경로 링크, 지난 행사 기록 |
