import csv
import json
import os
import random
import re
import ssl
import time
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


BASE_DIR = Path(__file__).resolve().parent
CATEGORIES_ROOT = BASE_DIR / "categories"

TARGET_BIG_CODE = "107"
TARGET_SMALL_CODE = "107001"

API_URL = "https://goods.musinsa.com/api2/review/v1/view/list"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.musinsa.com/",
}

MAX_REVIEWS_PER_PRODUCT = 100


def safe_get(d: dict, *keys, default: Any = None) -> Any:
    cur: Any = d
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def extract_survey_answer(survey_block: dict | None, attribute_name: str) -> str:
    if not isinstance(survey_block, dict):
        return ""

    questions = survey_block.get("questions")
    if not isinstance(questions, list):
        return ""

    for q in questions:
        if not isinstance(q, dict):
            continue
        if q.get("attribute") != attribute_name:
            continue

        answers = q.get("answers")
        if not isinstance(answers, list) or not answers:
            return ""

        first_answer = answers[0]
        if not isinstance(first_answer, dict):
            return ""

        return str(first_answer.get("answerShortText", "")).strip()

    return ""


def append_line(file_path: Path, text: str) -> None:
    with file_path.open("a", encoding="utf-8") as f:
        f.write(text.rstrip("\n") + "\n")


def log_error(error_file: Path, message: str) -> None:
    append_line(error_file, message)


def load_failed_product_entries(failed_file: Path) -> list[dict[str, Any]]:
    if not failed_file.exists():
        return []

    goods_map: dict[str, dict[str, Any]] = {}

    for line in failed_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split("\t")
        if len(parts) < 2:
            continue

        goods_no = parts[0].strip()
        product_url = parts[1].strip()

        if not goods_no or not product_url:
            continue

        if goods_no not in goods_map:
            goods_map[goods_no] = {
                "goods_no": goods_no,
                "product_url": product_url,
                "big_category_code": TARGET_BIG_CODE,
                "big_category_name_ko": "아울렛",
                "small_category_code": TARGET_SMALL_CODE,
                "small_category_name_ko_raw": "의류",
                "small_category_name_ko_norm": "의류",
            }

    goods_list = list(goods_map.values())
    goods_list.sort(key=lambda x: x["goods_no"])
    return goods_list


def normalize_review(review: dict, product_info: dict[str, Any], page: int) -> dict[str, Any]:
    content = (
        review.get("content")
        or review.get("reviewContent")
        or review.get("goodsOpinionContents")
        or ""
    )
    content = str(content).strip()

    review_id = (
        review.get("no")
        or review.get("reviewNo")
        or review.get("goodsOpinionNo")
        or ""
    )

    rating = (
        review.get("score")
        or review.get("grade")
        or review.get("point")
        or ""
    )

    created_at = (
        review.get("createDate")
        or review.get("regDate")
        or review.get("writeDate")
        or ""
    )

    option_text = (
        review.get("goodsOption")
        or review.get("optionName")
        or review.get("option")
        or ""
    )

    goods_raw = review.get("goods")
    goods = goods_raw if isinstance(goods_raw, dict) else {}

    user_profile_raw = review.get("userProfileInfo")
    user_profile = user_profile_raw if isinstance(user_profile_raw, dict) else {}

    survey_satisfaction_raw = review.get("reviewSurveySatisfaction")
    survey_satisfaction = survey_satisfaction_raw if isinstance(survey_satisfaction_raw, dict) else {}

    survey_repurchase_raw = review.get("reviewSurveyRepurchase")
    survey_repurchase = survey_repurchase_raw if isinstance(survey_repurchase_raw, dict) else {}

    return {
        "goods_no": product_info["goods_no"],
        "product_url": product_info["product_url"],
        "source_big_category_code": product_info["big_category_code"],
        "source_big_category_name_ko": product_info["big_category_name_ko"],
        "source_small_category_code": product_info["small_category_code"],
        "source_small_category_name_ko_raw": product_info["small_category_name_ko_raw"],
        "source_small_category_name_ko_norm": product_info["small_category_name_ko_norm"],
        "page": page,
        "review_id": str(review_id),
        "content": content,
        "rating": rating,
        "created_at": created_at,
        "option_text": option_text,
        "brand_name": goods.get("brandName", "") or "",
        "goods_name": goods.get("goodsName", "") or "",
        "goods_sex": goods.get("goodsSex", "") or "",
        "sale_status": goods.get("saleStatLabel", "") or "",
        "review_type": review.get("type", "") or "",
        "review_type_name": review.get("typeName", "") or "",
        "review_sub_type": review.get("subType", "") or "",
        "like_count": review.get("likeCount", 0) or 0,
        "comment_count": review.get("commentCount", 0) or 0,
        "comment_reply_count": review.get("commentReplyCount", 0) or 0,
        "is_first_review": review.get("isFirstReview", False),
        "channel_source": review.get("channelSource", "") or "",
        "channel_source_name": review.get("channelSourceName", "") or "",
        "user_id": review.get("userId", "") or review.get("memberId", "") or "",
        "encrypted_user_id": review.get("encryptedUserId", "") or "",
        "review_sex": user_profile.get("reviewSex", "") or "",
        "user_height": user_profile.get("userHeight", "") or "",
        "user_weight": user_profile.get("userWeight", "") or "",
        "user_level": user_profile.get("userLevel", "") or "",
        "survey_size": extract_survey_answer(survey_satisfaction, "사이즈"),
        "survey_color": extract_survey_answer(survey_satisfaction, "화면 대비 색감"),
        "survey_thickness": extract_survey_answer(survey_satisfaction, "두께감"),
        "survey_stretch": extract_survey_answer(survey_satisfaction, "신축성"),
        "repurchase_intent": extract_survey_answer(survey_repurchase, "재구매 의사"),
        "raw_json": json.dumps(review, ensure_ascii=False),
    }


def resolve_ca_bundle() -> str | None:
    for env_name in ("REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
        path = os.environ.get(env_name)
        if path and Path(path).exists():
            return path

    default_paths = ssl.get_default_verify_paths()
    for candidate in [default_paths.cafile, default_paths.openssl_cafile]:
        if candidate and Path(candidate).exists():
            return candidate

    common_paths = [
        "/etc/ssl/certs/ca-certificates.crt",
        "/etc/pki/tls/certs/ca-bundle.crt",
        "/etc/ssl/cert.pem",
        "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",
    ]
    for candidate in common_paths:
        if Path(candidate).exists():
            return candidate

    try:
        import certifi
        path = certifi.where()
        if path and Path(path).exists():
            return path
    except Exception:
        pass

    return None


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)

    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    ca_bundle = resolve_ca_bundle()
    if not ca_bundle:
        raise RuntimeError("사용 가능한 CA bundle 경로를 찾지 못했습니다.")
    session.verify = ca_bundle
    print(f"[SSL] CA bundle 사용: {ca_bundle}")

    return session


def fetch_reviews_for_product(
    session: requests.Session,
    product_info: dict[str, Any],
    error_file: Path,
    sleep_range: tuple[float, float] = (0.8, 1.5),
) -> tuple[list[dict[str, Any]], bool]:
    all_rows: list[dict[str, Any]] = []
    page = 0

    while True:
        params = {
            "goodsNo": product_info["goods_no"],
            "page": page,
            "pageSize": 10,
        }

        try:
            response = session.get(API_URL, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            log_error(
                error_file,
                f"[RETRY-ERROR] 요청 실패 | goods_no={product_info['goods_no']} | "
                f"page={page} | url={product_info['product_url']} | {e}",
            )
            return all_rows, False

        items_raw = safe_get(data, "data", "list", default=[])
        items = items_raw if isinstance(items_raw, list) else []

        page_info_raw = safe_get(data, "data", "page", default={})
        page_info = page_info_raw if isinstance(page_info_raw, dict) else {}

        if not items:
            return all_rows, True

        for item in items:
            if not isinstance(item, dict):
                continue

            row = normalize_review(item, product_info=product_info, page=page)
            if row["content"]:
                all_rows.append(row)

            if len(all_rows) >= MAX_REVIEWS_PER_PRODUCT:
                return all_rows, True

        total_pages = page_info.get("totalPages")
        current_page = page_info.get("page", page)
        page += 1

        if isinstance(total_pages, int) and page >= total_pages:
            return all_rows, True

        if isinstance(current_page, int) and isinstance(total_pages, int):
            if current_page >= total_pages - 1:
                return all_rows, True

        time.sleep(random.uniform(*sleep_range))


def deduplicate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    deduped = []

    for row in rows:
        key = (row["goods_no"], row["review_id"], row["content"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    return deduped


def get_next_batch_number(batches_dir: Path) -> int:
    batches_dir.mkdir(exist_ok=True)
    pattern = re.compile(r"musinsa_reviews_batch(\d+)\.csv$")

    existing_numbers = []
    for path in batches_dir.glob("musinsa_reviews_batch*.csv"):
        match = pattern.search(path.name)
        if match:
            existing_numbers.append(int(match.group(1)))

    return 1 if not existing_numbers else max(existing_numbers) + 1


def get_output_paths(batches_dir: Path, batch_number: int) -> tuple[Path, Path]:
    batch_tag = f"batch{batch_number:02d}"
    csv_path = batches_dir / f"musinsa_reviews_{batch_tag}.csv"
    jsonl_path = batches_dir / f"musinsa_reviews_{batch_tag}.jsonl"
    return csv_path, jsonl_path


def ensure_csv_header(csv_path: Path) -> list[str]:
    fieldnames = [
        "goods_no",
        "product_url",
        "source_big_category_code",
        "source_big_category_name_ko",
        "source_small_category_code",
        "source_small_category_name_ko_raw",
        "source_small_category_name_ko_norm",
        "page",
        "review_id",
        "content",
        "rating",
        "created_at",
        "option_text",
        "brand_name",
        "goods_name",
        "goods_sex",
        "sale_status",
        "review_type",
        "review_type_name",
        "review_sub_type",
        "like_count",
        "comment_count",
        "comment_reply_count",
        "is_first_review",
        "channel_source",
        "channel_source_name",
        "user_id",
        "encrypted_user_id",
        "review_sex",
        "user_height",
        "user_weight",
        "user_level",
        "survey_size",
        "survey_color",
        "survey_thickness",
        "survey_stretch",
        "repurchase_intent",
        "raw_json",
    ]

    if not csv_path.exists():
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

    return fieldnames


def append_rows_to_csv(csv_path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    if not rows:
        return
    with csv_path.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writerows(rows)


def append_rows_to_jsonl(jsonl_path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with jsonl_path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    small_dir = CATEGORIES_ROOT / TARGET_BIG_CODE / TARGET_SMALL_CODE
    processed_file = small_dir / "processed_goods.txt"
    failed_file = small_dir / "failed_goods.txt"
    error_file = small_dir / "errors.log"
    batches_dir = small_dir / "batches"

    small_dir.mkdir(parents=True, exist_ok=True)
    batches_dir.mkdir(exist_ok=True)

    retry_goods = load_failed_product_entries(failed_file)
    if not retry_goods:
        print("failed_goods.txt에 재시도할 상품이 없습니다.")
        return

    batch_number = get_next_batch_number(batches_dir)
    csv_path, jsonl_path = get_output_paths(batches_dir, batch_number)
    fieldnames = ensure_csv_header(csv_path)

    print(f"[타겟] {TARGET_SMALL_CODE} failed 상품 재시도")
    print(f"재시도 대상 상품 수: {len(retry_goods)}")
    print(f"자동 배치 번호: {batch_number}")

    session = create_session()

    success_goods = 0
    failed_goods = 0
    saved_rows_total = 0

    for idx, product_info in enumerate(retry_goods, start=1):
        print(f"[{idx}/{len(retry_goods)}] 재시도 중: {product_info['product_url']}")

        rows, success = fetch_reviews_for_product(
            session=session,
            product_info=product_info,
            error_file=error_file,
        )

        if not success:
            failed_goods += 1
            print("  -> 재시도 실패")
            time.sleep(random.uniform(1.0, 2.0))
            continue

        rows = deduplicate_rows(rows)
        append_rows_to_csv(csv_path, rows, fieldnames)
        append_rows_to_jsonl(jsonl_path, rows)

        # 성공했으면 processed에 다시 찍어도 상관없음(중복 가능)
        append_line(processed_file, product_info["goods_no"])

        success_goods += 1
        saved_rows_total += len(rows)

        if rows:
            print(f"  -> 리뷰 {len(rows)}개 저장 완료")
        else:
            print("  -> 리뷰 없음 (재시도 성공)")

        time.sleep(random.uniform(1.0, 2.0))

    print("\n===== 107001 failed 상품 재시도 종료 =====")
    print(f"성공 상품 수: {success_goods}")
    print(f"실패 상품 수: {failed_goods}")
    print(f"저장 리뷰 수: {saved_rows_total}")


if __name__ == "__main__":
    main()