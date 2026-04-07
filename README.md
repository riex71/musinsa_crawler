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

## crawler
- 청크 단위
- 청크 1: 001001 ~ 002006 (14개)
- 청크 2: 002007 ~ 002023 (14개)
- 청크 3: 002024 ~ 004002 (13개)
- 청크 4: 004003 ~ 017017 (13개)
- 청크 5: 017018 ~ 026003 (13개)
- 청크 6: 026004 ~ 103005 (13개)
- 청크 7: 103006 ~ 106012 (13개)
- 청크 8: 106013 ~ 111003 (13개)

## ssh 접속
- 터미널로 접속
- 주피터로 접속
http://qlak315.iptime.org:20109
- vscode로 접속

## tmux
### tmux 사용법
- tmux 방 만들기
```
tmux new -s musinsa
```
세션에서 빠져나오기
키보드로:
Ctrl+b
그다음 d
그러면 작업은 계속 돌고, 세션만 빠져나옴.
- 다시 붙기
```
tmux attach -t musinsa
```
- 세션 목록 보기
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
curl -L -s -S -f https://astral.sh/uv/install.sh | sh
source ~/.bashrc
uv python install 3.12
uv sync
uv run playwright install chromium
```
- 그다음 평소엔:
```
tmux attach -t musinsa
cd /data/musinsa_crawler
git pull
uv run python crawler.py
```
- 마지막엔:
```
uv run python merge_small_to_big.py
uv run python merge_all.py
uv run python clean_reviews.py
```
