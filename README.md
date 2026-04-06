응. **지금 구조에서 파이썬 파일은 4~5개 정도로 보면 돼.**
핵심은 수집, 크롤링, 병합, 정제야.

# 전체 디렉터리 구조 추천

```text
musinsa/
├─ collect_urls.py
├─ crawler.py
├─ merge_small_to_big.py
├─ merge_all.py
├─ clean_reviews.py
└─ categories/
   ├─ 001/
   │  ├─ 001001/
   │  │  ├─ product_urls.txt
   │  │  ├─ processed_goods.txt
   │  │  ├─ errors.log
   │  │  ├─ debug_html/
   │  │  └─ batches/
   │  │     ├─ musinsa_reviews_batch01.csv
   │  │     ├─ musinsa_reviews_batch01.jsonl
   │  │     └─ ...
   │  ├─ 001002/
   │  ├─ 001005/
   │  ├─ 001010/
   │  └─ merged/
   │     ├─ musinsa_reviews_001_all.csv
   │     └─ musinsa_reviews_001_all.jsonl
   ├─ 002/
   ├─ 003/
   └─ ...
└─ final/
   ├─ musinsa_reviews_all.csv
   └─ musinsa_reviews_all.jsonl
```

# 파이썬 파일별 역할

## 1. `collect_urls.py`

**역할:** 소분류 디렉터리 이름을 읽어서 상품 URL 수집

* 예: `categories/001/001001/` 디렉터리가 있으면
* 자동으로 `https://www.musinsa.com/category/001001/goods?gf=A` 생성
* 무한 스크롤 5번 정도 수행
* `001001/product_urls.txt` 저장

즉 **“상품 링크 수집기”**야.

---

## 2. `crawler.py`

**역할:** 각 소분류의 `product_urls.txt`를 읽어서 리뷰 실제 수집

* `001001/product_urls.txt` 읽음
* 100개씩 자동 배치
* 상품당 최대 리뷰 100개
* 다 끝날 때까지 자동 반복
* `001001/batches/`에 CSV/JSONL 저장
* `processed_goods.txt` 기록

즉 **“리뷰 본수집기”**야.

---

## 3. `merge_small_to_big.py`

**역할:** 소분류 여러 개 결과를 대분류 하나로 합치기

예:

* `001001/batches/*.csv`
* `001002/batches/*.csv`
* `001005/batches/*.csv`

이걸 다 모아서

* `categories/001/merged/musinsa_reviews_001_all.csv`
* `categories/001/merged/musinsa_reviews_001_all.jsonl`

로 만드는 거야.

합칠 때 보통:

* `goods_no + review_id`
* 또는 `goods_no + content`

기준으로 중복 제거도 같이 함.

즉 **“소분류 → 대분류 병합기”**.

---

## 4. `merge_all.py`

**역할:** 대분류별 합본을 최종 전체 데이터로 합치기

예:

* `categories/001/merged/...`
* `categories/002/merged/...`
* `categories/003/merged/...`

이런 걸 전부 합쳐서

* `final/musinsa_reviews_all.csv`
* `final/musinsa_reviews_all.jsonl`

만듦.

즉 **“대분류 → 전체 병합기”**.

---

## 5. `clean_reviews.py`

**역할:** 최종 CSV를 학습용으로 정리

여기서 하는 일:

* 중복 제거
* 너무 짧은 리뷰 제거
* 상품당 최대 리뷰 수 제한
* 불만 신호 우선 보존 + 나머지 랜덤 샘플링
* 모델 학습용 컬럼만 남기기

즉 **“정제기 / 학습셋 제조기”**야.

---

# 디렉터리 안 파일 역할

## `product_urls.txt`

소분류에서 수집된 상품 URL 목록

## `processed_goods.txt`

이미 크롤링 끝난 상품 번호 목록
중간에 멈춰도 이어서 가능하게 해줌

## `errors.log`

그 소분류에서 난 에러 기록

## `debug_html/`

URL 수집할 때 디버깅용 HTML 저장

## `batches/`

배치별 리뷰 원본 저장

* `musinsa_reviews_batch01.csv`
* `musinsa_reviews_batch02.csv`
* ...

## `merged/`

대분류 합본 저장

## `final/`

전체 최종 합본 저장

---

# 실제 작업 순서

## 1단계

네가 할 것:

* `categories/001/001001/`
* `categories/001/001002/`
  이런 디렉터리 만들기

## 2단계

`collect_urls.py`

* 상품 URL 수집

## 3단계

`crawler.py`

* 리뷰 자동 수집

## 4단계

`merge_small_to_big.py`

* 대분류 합치기

## 5단계

`merge_all.py`

* 전체 합치기

## 6단계

`clean_reviews.py`

* 학습용 정제

---

# 한 줄 요약

파이썬 파일은 보통 이렇게 보면 된다.

* `collect_urls.py` = 상품 URL 모으기
* `crawler.py` = 리뷰 수집
* `merge_small_to_big.py` = 소분류 결과를 대분류로 합치기
* `merge_all.py` = 대분류 결과를 전체로 합치기
* `clean_reviews.py` = 최종 학습용 데이터 정제

원하면 다음엔 내가 `merge_small_to_big.py`부터 바로 코드로 써줄게.
