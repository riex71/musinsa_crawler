# 무신사 크롤링 프로젝트

## 1. 프로젝트 개요
무신사 카테고리 페이지에서 상품 URL을 수집하고, 각 상품의 리뷰를 API 기반으로 수집한 뒤, 병합·정제·분석까지 수행하는 파이프라인입니다.

목표:

- 무신사 상품 리뷰 데이터셋 구축
- 카테고리별/브랜드별/평점별 리뷰 특성 파악
- 저평점 리뷰 중심 complaint 신호 탐색
- 전통적 NLP 기반 키워드 분석 및 인사이트 도출

---

## 2. 디렉터리 구조

```
musinsa_crawler/
├─ category_master.csv           # 프로젝트 대상 카테고리 마스터 테이블
├─ collect_urls.py               # 카테고리 페이지에서 상품 URL 수집
├─ check_collect_urls.py         # 상품 URL 수집 결과 점검
├─ crawler.py                    # 청크 단위 리뷰 수집 메인 크롤러
├─ check_crawler.py              # 리뷰 수집 상태/실패/배치 결과 점검
├─ merge_small_to_big.py         # 소분류 배치 파일을 대분류 단위로 병합
├─ merge_all.py                  # 대분류 병합 파일을 전체 단위로 병합
├─ clean_reviews.py              # 병합본 정제 및 분석용 데이터셋 생성
├─ nlp_analysis_final.py         # 최종 전통적 NLP 분석 수행
│
├─ categories/                   # 원천 수집 데이터 저장 루트
│  ├─ 001/                       # 대분류 코드별 디렉터리
│  │  ├─ 001001/                 # 소분류 코드별 작업 디렉터리
│  │  │  ├─ product_urls.txt     # 수집된 상품 URL 목록
│  │  │  ├─ processed_goods.txt  # 리뷰 수집 완료 상품 번호 목록
│  │  │  ├─ failed_goods.txt     # 리뷰 수집 실패 상품 번호/URL 목록
│  │  │  ├─ errors.log           # 요청 실패/예외 로그
│  │  │  ├─ debug_html/          # URL 수집 시 저장한 디버깅용 HTML
│  │  │  └─ batches/             # 리뷰 수집 배치 결과 저장 폴더
│  │  │     ├─ musinsa_reviews_batch01.csv    # 배치 1 리뷰 CSV
│  │  │     └─ musinsa_reviews_batch01.jsonl  # 배치 1 리뷰 JSONL
│  │  └─ ...
│  ├─ 107/
│  │  └─ 107001/
│  │     ├─ product_urls.txt     
│  │     ├─ processed_goods.txt 
│  │     ├─ failed_goods.txt     
│  │     ├─ errors.log          
│  │     ├─ debug_html/         
│  │     └─ batches/
│  │        ├─ musinsa_reviews_batch01.csv    # 1차 리뷰 수집 결과 CSV
│  │        ├─ musinsa_reviews_batch01.jsonl  # 1차 리뷰 수집 결과 JSONL
│  │        ├─ musinsa_reviews_batch02.csv    # 재시도/추가 수집 결과 CSV
│  │        └─ musinsa_reviews_batch02.jsonl  # 재시도/추가 수집 결과 JSONL
│  └─ ...
│
├─ merged/                       # 병합 결과 저장 폴더
│  ├─ big/                       # 대분류 단위 병합 결과
│  │  ├─ musinsa_001_merged.csv     # 대분류 001 병합 CSV
│  │  ├─ musinsa_001_merged.jsonl   # 대분류 001 병합 JSONL
│  │  └─ ...
│  └─ all/                       # 전체 병합 결과
│     ├─ musinsa_all_merged.csv     # 전체 리뷰 병합 CSV
│     └─ musinsa_all_merged.jsonl   # 전체 리뷰 병합 JSONL
│
├─ cleaned/                      # 최종 정제 데이터 저장 폴더
│  ├─ musinsa_train_ready.csv    # 정제 완료된 분석/학습용 CSV
│  └─ musinsa_train_ready.jsonl  # 정제 완료된 분석/학습용 JSONL
│
└─ analysis_final/               # 최종 NLP 분석 결과 저장 폴더
   ├─ report.md                  # 분석 결과 요약 리포트
   ├─ charts.pdf                 # 분석 차트 모음 PDF
   └─ short_reviews_le_5.csv     # 5자 이하 짧은 리뷰 검수용 파일
````

---

## 3. 각 파일/기능 상세 설명

### 3.1 `category_master.csv`

프로젝트의 기준 마스터 파일입니다.

역할:

* 대분류/소분류 코드 관리
* 한글 카테고리명 관리
* 프로젝트 포함 여부(`include_for_project`) 관리
* 이후 모든 수집/병합/분석의 기준점 역할

주요 컬럼:

* `big_category_code`: 대분류 코드
* `big_category_name_ko`: 대분류 한글명
* `small_category_code`: 소분류 코드
* `small_category_name_ko_raw`: 원본 소분류명
* `small_category_name_ko_norm`: 정규화된 소분류명
* `category_url`: 카테고리 URL
* `include_for_project`: 프로젝트 포함 여부 (`Y`/`N`)

---

### 3.2 `collect_urls.py`

카테고리 페이지에서 상품 URL을 수집하는 스크립트입니다.

역할:

* 각 소분류 페이지 접속
* 스크롤을 여러 번 내려 상품 URL 노출 확대
* HTML/본문에서 상품 URL 추출
* 결과를 `product_urls.txt`로 저장
* 디버깅용 HTML 스냅샷 저장

최종 주요 설정:

* 카테고리당 최대 스크롤 수: 7
* 스크롤 간 대기: 3000ms
* 새 URL 증가가 멈추면 조기 종료 가능

출력:

* `categories/<big>/<small>/product_urls.txt`
* `categories/<big>/<small>/debug_html/scroll_*.html`

주의:

* 이 단계는 전수 수집이 아니라, 동일 스크롤 budget 기반 capped sampling에 가깝습니다.
* 카테고리별 실제 전체 상품 수를 정확히 반영하기보다는, 각 카테고리에서 일정량의 후보 상품을 균형 있게 확보하는 목적입니다.

---

### 3.3 `check_collect_urls.py`

상품 URL 수집 결과 점검 스크립트입니다.

역할:

* `product_urls.txt` 존재 여부 확인
* 카테고리별 URL 수 집계
* 카테고리 내부 중복 확인
* 카테고리 간 상품 중복 확인
* 이상한 분포가 있는지 확인

왜 필요한가:

* URL 수집이 끝난 뒤 바로 리뷰 크롤링으로 넘어가기 전에, 수집 자체가 망가진 건 아닌지 검증하기 위해 사용했습니다.

---

### 3.4 `crawler.py`

상품 리뷰를 실제로 수집하는 메인 크롤러입니다.

역할:

* `category_master.csv` 기준 대상 소분류 로딩
* 전체 소분류를 총 8개 청크로 균등 분할
* 사용자가 실행 시 청크 번호를 입력
* 해당 청크 안의 각 소분류에 대해 1회 실행당 1배치(상품 100개)만 처리
* 무신사 리뷰 API 호출
* 리뷰를 CSV/JSONL로 배치 저장
* 처리 완료 상품은 `processed_goods.txt` 기록
* 실패 상품은 `failed_goods.txt` 기록
* 에러는 `errors.log` 기록

주요 정책:

* `BATCH_SIZE = 100`
* `MAX_REVIEWS_PER_PRODUCT = 100`
* 상품당 최대 리뷰 100개 수집
* 리뷰는 API 기본 정렬 순서 기준으로 앞에서부터 수집
* 실질적으로는 최근 리뷰 중심 수집에 가까운 패턴으로 관찰됨

출력:

* `categories/<big>/<small>/batches/musinsa_reviews_batchXX.csv`
* `categories/<big>/<small>/batches/musinsa_reviews_batchXX.jsonl`
* `processed_goods.txt`
* `failed_goods.txt`
* `errors.log`

---

### 3.5 `check_crawler.py`

리뷰 수집 상태 점검 스크립트입니다.

역할:

* 소분류별 상품 수 / 처리 완료 수 / 실패 수 집계
* 전체 리뷰 row 수 집계
* batch 파일 개수 확인
* 중복 리뷰 여부 확인
* 이상 카테고리 탐지

왜 필요한가:

* 청크 수집이 끝난 뒤, merge 전에 수집이 정상적으로 진행되었는지 확인하기 위해 사용했습니다.

주의:

* 초기 버전에서는 `처리율 30% 미만`을 경고로 잡았으나, 현재 운영 방식이 소분류당 1배치=100개 상품 처리 구조라 대부분 카테고리가 원래 30% 미만이 되는 점을 확인했습니다.
* 따라서 이 경고는 실제 이상이 아니라 운영 방식의 결과일 수 있습니다.

---

### 3.6 `merge_small_to_big.py`

소분류 배치 파일들을 대분류 단위로 병합하는 스크립트입니다.

역할:

* 각 소분류의 `batches/*.csv`, `batches/*.jsonl` 전부 읽기
* 같은 대분류에 속한 소분류 데이터 합치기
* `goods_no + review_id + content` 기준 dedup
* 대분류별 merged CSV/JSONL 저장

출력:

* `merged/big/musinsa_<big>_merged.csv`
* `merged/big/musinsa_<big>_merged.jsonl`

특징:

* `107001`처럼 batch01, batch02가 같이 있는 경우도 자동으로 병합됨

---

### 3.7 `merge_all.py`

대분류별 merged 파일을 전체 merged 파일로 다시 병합하는 스크립트입니다.

역할:

* `merged/big/*.csv`, `*.jsonl` 전부 읽기
* 전체 리뷰 데이터로 합치기
* 전역 dedup 수행
* 전체 merged CSV/JSONL 저장

출력:

* `merged/all/musinsa_all_merged.csv`
* `merged/all/musinsa_all_merged.jsonl`

특징:

* 단순 concat만 하는 것이 아니라 전체 중복 제거까지 수행합니다.

---

### 3.8 `clean_reviews.py`

병합된 원시 리뷰 데이터를 최종 분석용 데이터셋으로 정제하는 스크립트입니다.

역할:

* 불필요한 컬럼 제거
* 너무 짧은 리뷰 제거
* 최종 dedup 강화
* 분석용 통합 카테고리(`analysis_category`) 생성
* cleaned CSV/JSONL 저장

핵심 정제 내용:

* `raw_json` 제거
* 결측이 심하거나 활용도가 낮은 컬럼 제거
* `content_length < 5` 제거
* `review_id` 중복 제거
* `goods_no + normalized content` 기준 중복 제거

출력:

* `cleaned/musinsa_train_ready.csv`
* `cleaned/musinsa_train_ready.jsonl`

결과:

* 원본 merged CSV 약 1.3GB → cleaned CSV 약 282MB 수준으로 축소
* 가장 큰 감소 원인은 `raw_json` 제거와 dedup(중복 제거)

---

### 3.9 `nlp_analysis_final.py`

최종 분석 스크립트입니다.

역할:

* cleaned 데이터 로딩
* 전통적 NLP 기반 텍스트 분석 수행
* report.md와 charts.pdf 생성

분석 내용:

* 기본 통계
* 전체/긍정/부정 리뷰 분리
* 전체 top token
* 긍정/부정 top token
* 전체/부정 bigram
* 부정 vs 긍정 구분 키워드(log-odds)
* 카테고리별 특징 키워드(TF-IDF)
* 브랜드별 저평점 비율
* 차트 PDF 생성

출력:

* `analysis_final/report.md`
* `analysis_final/charts.pdf`
* `analysis_final/short_reviews_le_5.csv` (검수용)

사용 라이브러리:

* `pandas`
* `matplotlib`
* `scikit-learn`
* `kiwipiepy`

---

## 4. CSV / JSONL 주요 컬럼 설명

### 식별 관련

* `goods_no`: 상품 번호
* `review_id`: 리뷰 번호
* `product_url`: 상품 페이지 URL

### 텍스트/평점 관련

* `content`: 리뷰 본문
* `content_length`: 리뷰 글자 수
* `rating`: 평점
* `created_at`: 리뷰 작성 시각
* `created_at_dt`: datetime 변환 버전

### 상품 정보

* `brand_name`: 브랜드명
* `goods_name`: 상품명
* `goods_sex`: 상품 성별 구분
* `option_text`: 옵션명

### 리뷰 메타 정보

* `review_type`: 리뷰 타입 코드
* `review_type_name`: 리뷰 타입 이름
* `like_count`: 좋아요 수
* `comment_count`: 댓글 수
* `comment_reply_count`: 대댓글 수
* `is_first_review`: 첫 리뷰 여부

### 작성자 프로필 정보

* `review_sex`: 리뷰 작성자 성별
* `user_height`: 작성자 키
* `user_weight`: 작성자 몸무게
* `user_level`: 작성자 레벨

### 설문 기반 정보

* `survey_size`: 사이즈 관련 응답
* `survey_color`: 색감 관련 응답
* `survey_thickness`: 두께감 관련 응답
* `survey_stretch`: 신축성 관련 응답
* `repurchase_intent`: 재구매 의사

### 카테고리 정보

* `source_big_category_code`: 원본 대분류 코드
* `source_big_category_name_ko`: 원본 대분류 한글명
* `source_small_category_code`: 원본 소분류 코드
* `source_small_category_name_ko_raw`: 원본 소분류명
* `source_small_category_name_ko_norm`: 정규화된 소분류명
* `analysis_category`: 분석용 통합 카테고리

### 제거된 주요 컬럼 예시

* `raw_json`: 리뷰 API 원본 JSON 전체 문자열
* `review_sub_type`: 거의 전부 비어 있어서 제거
* `sale_status`: 거의 전부 비어 있어서 제거
* `user_id`: 거의 전부 비어 있어서 제거
* `channel_source`, `channel_source_name`: 활용도가 낮아 제거

---

## 5. 분석 결과

### 기본 분포

* rows: 391,182
* unique_goods: 7,687
* mean_rating: 4.7774
* positive_ratio(>=4): 96.17%
* negative_ratio(<=2): 1.37%

해석:

* 무신사 리뷰는 전형적인 쇼핑몰 리뷰처럼 고평점 편향이 매우 강함
* 전체 리뷰보다 저평점 리뷰를 따로 보는 분석이 complaint 탐지에 더 적합함

### 전체 핵심 키워드

상위 키워드:

* 사이즈
* 만족
* 가격
* 디자인
* 재질
* 배송

해석:

* 소비자들은 주로 사이즈감, 가격 대비 만족도, 디자인, 재질, 배송 경험에 주목함

### 저평점 핵심 키워드

상위 키워드:

* 불편
* 마감
* 교환
* 사진
* 세탁

해석:

* 저평점 리뷰의 핵심 complaint 축은 사이즈 문제, 배송 문제, 마감/품질 문제, 실물-사진 차이로 요약 가능

### 카테고리별 특징 예시

* 가방: 수납, 공간, 크기, 여행, 카드
* 하의: 허리, 기장, 길이, 와이드
* 신발: 불편, 발등, 쿠션, 착화감
* 속옷/홈웨어: 착용감, 잠옷, 촉감

해석:

* 카테고리별로 complaint 요인이 다르므로 카테고리별 분석이 중요함

---

## 6. 진행 타임라인

### 단계 1. 카테고리 구조 정리

* 처음에는 프로젝트 대상 카테고리 범위를 확정하는 작업부터 시작함
* `category_master.csv`를 만들고, 대분류/소분류 코드와 한글명을 수작업으로 정리함
* 한글 카테고리명을 단순 코드만이 아니라 README/분석에 쓸 수 있도록 같이 관리하도록 방향을 잡음

### 단계 2. 상품 URL 수집기 구현

* `collect_urls.py`를 작성해 카테고리 페이지에서 상품 URL을 수집함
* 초기에는 스크롤 5회 기준으로 운영했고, 카테고리당 약 282개 수준의 URL이 수집됨
* 이후 서버 환경을 사용하게 되면서 스크롤 수를 7로 늘렸고, 카테고리당 약 402개 수준으로 확대함

### 단계 3. URL 수집 결과 검증

* `check_collect_urls.py`를 작성해 URL 수집 결과를 점검함
* 카테고리별 분포가 지나치게 균일해 보여 한때 이상으로 의심했으나,
  이는 동일 스크롤 budget으로 capped sampling한 결과라는 점을 확인함
* 즉 전수 수집이 아니라, 카테고리별로 일정량의 후보 상품을 균형 있게 확보하는 방식으로 정리함

### 단계 4. 실행 환경 전환

* 처음에는 팀원 분산 실행도 고려했으나,
  라이브러리 설치/경로/깃 머지 충돌/체크포인트 관리 문제 때문에 중앙 서버 단일 실행 방식으로 전환함
* `/data/musinsa_crawler` 아래에서 모든 작업을 수행하도록 결정함
* 장시간 실행을 위해 `tmux` 사용 방식을 도입함

### 단계 5. 리뷰 크롤러 구현

* `crawler.py`를 구현해 청크 단위 리뷰 수집 구조를 만듦
* 전체 소분류를 8개 청크로 나누고, 실행 시 청크 번호만 입력하면 되도록 UX를 단순화함
* 한 번 실행당 소분류별 상품 100개만 처리하도록 설계하여, 중단/재실행에 강한 구조로 만듦
* `processed_goods.txt`, `failed_goods.txt`, `errors.log`, `batches/` 구조를 사용해 체크포인트를 보존함

### 단계 6. 부분 실패 처리 개선

* 초기 리뷰/피드백 과정에서 “부분 실패 상품을 processed 처리하면 안 된다”는 운영 리스크를 인식함
* 이후 실패 상품은 `processed_goods.txt`에 기록하지 않고 `failed_goods.txt`에 남기도록 정리함
* retry/backoff도 적용해 일시적 요청 실패에 대응할 수 있게 함

### 단계 7. 정렬 기준 검증

* 상품당 최대 100개 리뷰만 수집하도록 했을 때,
  “좋은 리뷰 우선으로 수집되는 것 아닌가?”라는 의문이 생김
* 별도 확인 스크립트로 실제 API 첫 페이지 리뷰를 점검한 결과,
  정렬은 추천순보다는 최신순에 가깝다는 결론을 내림
* 따라서 현재 수집 구조는 실질적으로 최근 리뷰 중심 수집에 가까운 것으로 해석함

### 단계 8. SSL/certifi 이슈 발생

* 청크 수집 완료 후 `check_crawler.py` 결과에서 `107001` 카테고리만 실패가 집중된 것을 발견함
* 원인을 추적한 결과, 상품 문제나 카테고리 문제라기보다
  `certifi` 경로가 꼬이면서 TLS CA bundle을 찾지 못한 SSL 환경 문제였음을 확인함
* 실패 로그를 분석하고, `failed_goods.txt` 기반 강제 재시도 전용 스크립트를 별도로 만들어 해결함
* `107001`의 실패 41개를 재시도한 결과 모두 성공함

### 단계 9. 병합/정제/분석

* `merge_small_to_big.py` → `merge_all.py` 순으로 병합 파이프라인을 정리함
* 병합본 용량은 CSV 약 1.3GB, JSONL 약 1.65GB 수준이었음
* `clean_reviews.py`로 불필요한 컬럼 제거, 짧은 리뷰 제거, dedup, 통합 카테고리 생성 등을 수행함
* 결과적으로 최종 cleaned CSV는 약 282MB 수준으로 축소됨
* 이후 `nlp_analysis_final.py`를 통해 전통적 NLP 기반 최종 분석 리포트를 생성함

### 단계 10. 한글 폰트 이슈

* 분석 자체는 정상 완료되었으나, 차트 PDF 생성 시 matplotlib 기본 폰트가 한글을 지원하지 않아 glyph 경고가 발생함
* 서버에 `fonts-nanum`을 설치하고 `fc-cache`, `fc-list`로 폰트 반영을 확인함
* 이후 차트 가독성 문제를 해결할 수 있는 상태로 정리함

---

## 7. 실행 순서 요약

### 1) 상품 URL 수집

```bash
uv run python collect_urls.py
uv run python check_collect_urls.py
```

### 2) 리뷰 수집

```bash
uv run python crawler.py
uv run python check_crawler.py
```

### 3) (필요 시) 특정 실패 카테고리 재시도

```bash
uv run python crawler_retry_failed_107001.py
```

### 4) 병합

```bash
uv run python merge_small_to_big.py
uv run python merge_all.py
```

### 5) 정제

```bash
uv run python clean_reviews.py
```

### 6) 최종 분석

```bash
uv add pandas matplotlib scikit-learn kiwipiepy
uv run python nlp_analysis_final.py
```