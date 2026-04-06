import csv
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median

BASE_DIR = Path(__file__).resolve().parent
CATEGORIES_ROOT = BASE_DIR / "categories"
CATEGORY_MASTER_CSV = BASE_DIR / "category_master.csv"

PRODUCT_URL_PATTERN = re.compile(r"^https://www\.musinsa\.com/products/(\d+)$")


def load_category_master(csv_path: Path) -> list[dict]:
    if not csv_path.exists():
        raise FileNotFoundError(f"{csv_path} 파일이 없습니다.")

    rows = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            include_flag = str(row.get("include_for_project", "")).strip().upper()
            category_url = str(row.get("category_url", "")).strip()
            big_code = str(row.get("big_category_code", "")).strip()
            small_code = str(row.get("small_category_code", "")).strip()

            if include_flag != "Y":
                continue
            if not big_code or not small_code or not category_url:
                continue

            rows.append(
                {
                    "big_category_code": big_code,
                    "big_category_name_ko": str(row.get("big_category_name_ko", "")).strip(),
                    "small_category_code": small_code,
                    "small_category_name_ko_norm": str(row.get("small_category_name_ko_norm", "")).strip(),
                    "category_url": category_url,
                }
            )

    rows.sort(key=lambda x: (x["big_category_code"], x["small_category_code"]))
    return rows


def read_product_urls(product_urls_file: Path) -> list[str]:
    if not product_urls_file.exists():
        return []
    return [
        line.strip()
        for line in product_urls_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def extract_goods_no(url: str) -> str | None:
    match = PRODUCT_URL_PATTERN.match(url)
    return match.group(1) if match else None


def summarize_one_category(category_info: dict) -> dict:
    big_code = category_info["big_category_code"]
    small_code = category_info["small_category_code"]
    small_dir = CATEGORIES_ROOT / big_code / small_code
    product_urls_file = small_dir / "product_urls.txt"

    urls = read_product_urls(product_urls_file)
    goods_counter = Counter()
    invalid_urls = []

    for url in urls:
        goods_no = extract_goods_no(url)
        if goods_no is None:
            invalid_urls.append(url)
            continue
        goods_counter[goods_no] += 1

    duplicated_goods = {g: c for g, c in goods_counter.items() if c > 1}

    return {
        "big_category_code": big_code,
        "big_category_name_ko": category_info["big_category_name_ko"],
        "small_category_code": small_code,
        "small_category_name_ko_norm": category_info["small_category_name_ko_norm"],
        "dir_exists": small_dir.exists(),
        "file_exists": product_urls_file.exists(),
        "total_urls": len(urls),
        "unique_goods": len(goods_counter),
        "invalid_url_count": len(invalid_urls),
        "invalid_urls_sample": invalid_urls[:5],
        "duplicate_goods_count": len(duplicated_goods),
        "duplicate_goods_sample": list(duplicated_goods.items())[:5],
        "goods_set": set(goods_counter.keys()),
        "sample_urls": urls[:5],
    }


def print_basic_summary(results: list[dict]) -> None:
    valid_results = [r for r in results if r["file_exists"]]
    total_urls_list = [r["total_urls"] for r in valid_results]
    unique_goods_list = [r["unique_goods"] for r in valid_results]

    print("\n========== 전체 요약 ==========")
    print(f"대상 소분류 수: {len(results)}")
    print(f"product_urls.txt 존재: {sum(r['file_exists'] for r in results)}")
    print(f"product_urls.txt 없음: {sum(not r['file_exists'] for r in results)}")

    if not valid_results:
        print("유효한 결과가 없습니다.")
        return

    print(f"총 URL 수 합계: {sum(total_urls_list)}")
    print(f"총 고유 goods_no 수 합계(카테고리 내부 기준): {sum(unique_goods_list)}")
    print(f"카테고리당 평균 URL 수: {mean(total_urls_list):.2f}")
    print(f"카테고리당 중앙 URL 수: {median(total_urls_list):.2f}")
    print(f"최소 URL 수: {min(total_urls_list)}")
    print(f"최대 URL 수: {max(total_urls_list)}")


def print_count_distribution(results: list[dict]) -> None:
    valid_results = [r for r in results if r["file_exists"]]
    count_counter = Counter(r["total_urls"] for r in valid_results)

    print("\n========== URL 개수 분포 ==========")
    for count, freq in count_counter.most_common(15):
        print(f"URL {count}개: {freq}개 카테고리")

    suspicious_same_counts = [
        (count, freq) for count, freq in count_counter.items() if freq >= 5
    ]
    if suspicious_same_counts:
        print("\n[참고] 같은 URL 개수로 몰린 카테고리들")
        for count, freq in sorted(suspicious_same_counts):
            matched = [
                f"{r['small_category_code']}({r['small_category_name_ko_norm']})"
                for r in valid_results
                if r["total_urls"] == count
            ]
            print(f"- URL {count}개: {freq}개 카테고리")
            print("  ", ", ".join(matched[:12]))
            if len(matched) > 12:
                print(f"   ... 외 {len(matched) - 12}개")


def print_suspicious_categories(results: list[dict]) -> None:
    valid_results = [r for r in results if r["file_exists"]]
    if not valid_results:
        return

    total_urls_list = [r["total_urls"] for r in valid_results]
    med = median(total_urls_list)

    low_threshold = max(20, int(med * 0.25))
    high_threshold = int(med * 3.0)

    suspicious = []

    for r in results:
        reasons = []

        if not r["file_exists"]:
            reasons.append("product_urls.txt 없음")
        else:
            if r["total_urls"] == 0:
                reasons.append("URL 0개")
            if r["invalid_url_count"] > 0:
                reasons.append(f"형식 이상 URL {r['invalid_url_count']}개")
            if r["duplicate_goods_count"] > 0:
                reasons.append(f"카테고리 내부 중복 goods_no {r['duplicate_goods_count']}개")
            if r["total_urls"] < low_threshold:
                reasons.append(f"URL 수가 너무 적음(<{low_threshold})")
            if r["total_urls"] > high_threshold:
                reasons.append(f"URL 수가 너무 많음(>{high_threshold})")

        if reasons:
            suspicious.append((r, reasons))

    print("\n========== 의심 카테고리 ==========")
    if not suspicious:
        print("특별히 강한 이상 신호는 없습니다.")
        return

    for r, reasons in suspicious:
        print(
            f"- {r['small_category_code']} ({r['small_category_name_ko_norm']}) | "
            f"URL={r['total_urls']} | unique_goods={r['unique_goods']}"
        )
        print(f"  사유: {', '.join(reasons)}")
        if r["invalid_urls_sample"]:
            print(f"  이상 URL 샘플: {r['invalid_urls_sample']}")
        if r["duplicate_goods_sample"]:
            print(f"  중복 goods 샘플: {r['duplicate_goods_sample']}")


def analyze_cross_category_overlap(results: list[dict]) -> None:
    goods_to_categories = defaultdict(list)

    for r in results:
        for goods_no in r["goods_set"]:
            goods_to_categories[goods_no].append(
                (
                    r["small_category_code"],
                    r["small_category_name_ko_norm"],
                )
            )

    overlapping = {
        goods_no: cats
        for goods_no, cats in goods_to_categories.items()
        if len(cats) >= 2
    }

    print("\n========== 카테고리 간 상품 중복 ==========")
    print(f"전체 고유 goods_no 수(전 카테고리 합집합): {len(goods_to_categories)}")
    print(f"2개 이상 카테고리에 등장한 goods_no 수: {len(overlapping)}")

    if not overlapping:
        print("카테고리 간 중복 상품은 거의 없습니다.")
        return

    overlap_size_counter = Counter(len(cats) for cats in overlapping.values())
    print("중복 등장 횟수 분포:")
    for k, v in sorted(overlap_size_counter.items()):
        print(f"- {k}개 카테고리에 등장: {v}개 상품")

    print("\n중복 샘플 10개:")
    for idx, (goods_no, cats) in enumerate(overlapping.items()):
        if idx >= 10:
            break
        cat_str = ", ".join(f"{code}({name})" for code, name in cats[:5])
        print(f"- goods_no={goods_no}: {cat_str}")


def print_top_categories(results: list[dict], top_n: int = 15) -> None:
    valid_results = [r for r in results if r["file_exists"]]
    sorted_results = sorted(valid_results, key=lambda x: x["total_urls"], reverse=True)

    print(f"\n========== URL 상위 {top_n}개 카테고리 ==========")
    for r in sorted_results[:top_n]:
        print(
            f"- {r['small_category_code']} ({r['small_category_name_ko_norm']}): "
            f"URL={r['total_urls']}, unique_goods={r['unique_goods']}"
        )


def main():
    category_rows = load_category_master(CATEGORY_MASTER_CSV)
    results = [summarize_one_category(row) for row in category_rows]

    print_basic_summary(results)
    print_count_distribution(results)
    print_top_categories(results, top_n=15)
    print_suspicious_categories(results)
    analyze_cross_category_overlap(results)


if __name__ == "__main__":
    main()