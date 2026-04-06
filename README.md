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
## tmux
### tmux 사용법 핵심
세션에서 빠져나오기
키보드로:
Ctrl+b
그다음 d
그러면 작업은 계속 돌고, 세션만 빠져나옴.
다시 붙기
```
tmux attach -t musinsa
```
세션 목록 보기
```
tmux ls
```
### 서버 끊겨도 괜찮냐
tmux 안에서 실행 중이면 보통:
SSH 끊겨도
그 안의 Python 프로세스는 계속 살아 있음

### 추천 실제 실행 순서 요약

- 처음 한 번만:
```
apt update
apt install -y tmux
tmux new -s musinsa
cd /data/musinsa_crawler
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install requests playwright
playwright install chromium
```
- 그다음 평소엔:
```
tmux attach -t musinsa
cd /data/musinsa_crawler
source .venv/bin/activate
git pull
python collect_urls.py
python check_collect_urls.py
python crawler.py
```
- 마지막엔:
```
uv run python merge_small_to_big.py
uv run python merge_all.py
uv run python clean_reviews.py
```
- 명령어 요약
```
apt update
apt install -y tmux
tmux new -s musinsa
cd /data/musinsa_crawler
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install requests playwright
playwright install chromium
python collect_urls.py
python check_collect_urls.py
python crawler.py
```