import csv
import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CATEGORIES_ROOT = BASE_DIR / "categories"

BIG_CATEGORY_CODE = "001"


def get_big_category_dir() -> Path:
    big_dir = CATEGORIES_ROOT / BIG_CATEGORY_CODE
    if not big_dir.exists():
        raise FileNotFoundError(f"{big_dir} 디렉터리가 없습니다.")
    return big_dir


def get_small_category_dirs(big_dir: Path) -> list[Path]:
    dirs = [p for p in big_dir.iterdir() if p.is_dir() and p.name.isdigit()]
    dirs.sort(key=lambda p: p.name)
    return dirs


def collect_csv_files_from_small_categories(big_dir: Path) -> list[Path]:
    csv_files = []

    for small_dir in get_small_category_dirs(big_dir):
        batches_dir = small_dir / "batches"
        if not batches_dir.exists():
            continue

        files = sorted(batches_dir.glob("musinsa_reviews_batch*.csv"))
        csv_files.extend(files)

    return csv_files


def read_csv_rows(csv_path: Path) -> list[dict]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def deduplicate_rows(rows: list[dict]) -> list[dict]:
    seen = set()
    deduped = []

    for row in rows:
        key = (
            row.get("goods_no", ""),
            row.get("review_id", ""),
            row.get("content", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    return deduped


def save_csv(rows: list[dict], output_path: Path) -> None:
    if not rows:
        print("저장할 CSV 행이 없습니다.")
        return

    output_path.parent.mkdir(exist_ok=True)

    fieldnames = list(rows[0].keys())

    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def save_jsonl(rows: list[dict], output_path: Path) -> None:
    if not rows:
        print("저장할 JSONL 행이 없습니다.")
        return

    output_path.parent.mkdir(exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    big_dir = get_big_category_dir()
    merged_dir = big_dir / "merged"

    csv_files = collect_csv_files_from_small_categories(big_dir)
    if not csv_files:
        print("합칠 batch CSV 파일이 없습니다.")
        return

    print(f"[대분류] {BIG_CATEGORY_CODE}")
    print(f"발견한 batch CSV 파일 수: {len(csv_files)}")

    all_rows = []
    for csv_file in csv_files:
        rows = read_csv_rows(csv_file)
        all_rows.extend(rows)
        print(f"  - {csv_file} -> {len(rows)}행")

    print(f"\n합치기 전 총 행 수: {len(all_rows)}")
    all_rows = deduplicate_rows(all_rows)
    print(f"중복 제거 후 총 행 수: {len(all_rows)}")

    output_csv = merged_dir / f"musinsa_reviews_{BIG_CATEGORY_CODE}_all.csv"
    output_jsonl = merged_dir / f"musinsa_reviews_{BIG_CATEGORY_CODE}_all.jsonl"

    save_csv(all_rows, output_csv)
    save_jsonl(all_rows, output_jsonl)

    print("\n대분류 합치기 완료")
    print(f"CSV 저장: {output_csv}")
    print(f"JSONL 저장: {output_jsonl}")


if __name__ == "__main__":
    main()