## 무신사 리뷰 크롤링 프로젝트

- 프로젝트 디렉터리 구조

```project_root/
├─ category_master.csv
├─ collect_urls.py
├─ crawler.py
├─ merge_small_to_big.py
├─ merge_all.py
├─ clean_reviews.py
├─ categories/
│  ├─ 001/
│  │  ├─ 001001/
│  │  │  ├─ product_urls.txt
│  │  │  ├─ processed_goods.txt
│  │  │  ├─ failed_goods.txt
│  │  │  ├─ errors.log
│  │  │  ├─ debug_html/
│  │  │  └─ batches/
│  │  │     ├─ musinsa_reviews_batch01.csv
│  │  │     └─ musinsa_reviews_batch01.jsonl
│  │  ├─ 001002/
│  │  └─ ...
│  ├─ 002/
│  ├─ 003/
│  └─ ...
├─ merged/
│  ├─ big/
│  │  ├─ musinsa_001_merged.csv
│  │  ├─ musinsa_002_merged.csv
│  │  └─ ...
│  └─ all/
│     ├─ musinsa_all_merged.csv
│     └─ musinsa_all_merged.jsonl
└─ cleaned/
   ├─ musinsa_train_ready.csv
   └─ musinsa_train_ready.jsonl
   
```