import asyncio
import csv
import re
from collections import Counter
from pathlib import Path

from playwright.async_api import async_playwright


BASE_DIR = Path(__file__).resolve().parent
CATEGORIES_ROOT = BASE_DIR / "categories"
CATEGORY_MASTER_CSV = BASE_DIR / "category_master.csv"

MAX_SCROLLS_PER_SMALL_CATEGORY = 7
WAIT_MS = 3000
STOP_IF_NO_NEW_FOR = 2


def extract_product_urls_from_text(text: str) -> set[str]:
    return set(re.findall(r"https://www\.musinsa\.com/products/\d+", text))


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
            if not category_url:
                continue
            if not big_code or not small_code:
                continue

            rows.append(
                {
                    "big_category_code": big_code,
                    "big_category_name_ko": str(row.get("big_category_name_ko", "")).strip(),
                    "small_category_code": small_code,
                    "small_category_name_ko_raw": str(row.get("small_category_name_ko_raw", "")).strip(),
                    "small_category_name_ko_norm": str(row.get("small_category_name_ko_norm", "")).strip(),
                    "category_url": category_url,
                    "exclude_reason": str(row.get("exclude_reason", "")).strip(),
                    "notes": str(row.get("notes", "")).strip(),
                }
            )

    rows.sort(key=lambda x: (x["big_category_code"], x["small_category_code"]))
    return rows


def ensure_category_dir(big_code: str, small_code: str) -> Path:
    small_dir = CATEGORIES_ROOT / big_code / small_code
    small_dir.mkdir(parents=True, exist_ok=True)
    (small_dir / "debug_html").mkdir(exist_ok=True)
    return small_dir


async def get_current_urls(page) -> set[str]:
    html = await page.content()
    body_text = await page.locator("body").inner_text()

    html_urls = extract_product_urls_from_text(html)
    text_urls = extract_product_urls_from_text(body_text)

    return html_urls | text_urls


def run_sanity_check(category_info: dict, urls: list[str]) -> None:
    goods_counter = Counter()

    for url in urls:
        match = re.search(r"/products/(\d+)", url)
        if match:
            goods_counter[match.group(1)] += 1

    duplicated = [goods_no for goods_no, cnt in goods_counter.items() if cnt > 1]

    print(f"\n[점검] {category_info['small_category_code']} - {category_info['small_category_name_ko_norm']}")
    print(f"대분류: {category_info['big_category_code']} - {category_info['big_category_name_ko']}")
    print(f"총 URL 수: {len(urls)}")
    print(f"고유 goods_no 수: {len(goods_counter)}")
    print(f"중복 goods_no 수: {len(duplicated)}")

    print("샘플 URL 5개:")
    for url in urls[:5]:
        print(f"  {url}")


async def collect_one_small_category(page, category_info: dict) -> None:
    big_code = category_info["big_category_code"]
    small_code = category_info["small_category_code"]
    category_url = category_info["category_url"]

    small_dir = ensure_category_dir(big_code, small_code)
    output_file = small_dir / "product_urls.txt"
    debug_dir = small_dir / "debug_html"

    print(f"\n[소분류] {small_code} - {category_info['small_category_name_ko_norm']}")
    print(f"  -> URL: {category_url}")

    found_urls: set[str] = set()

    try:
        await page.goto(category_url, wait_until="networkidle", timeout=45000)
        await page.wait_for_timeout(WAIT_MS)
    except Exception as e:
        print(f"  -> 접속 실패: {e}")
        return

    stagnant_rounds = 0

    for scroll_idx in range(1, MAX_SCROLLS_PER_SMALL_CATEGORY + 1):
        current_urls = await get_current_urls(page)
        new_urls = current_urls - found_urls
        found_urls.update(current_urls)

        print(
            f"  - 스크롤 {scroll_idx}: 현재 페이지 URL {len(current_urls)}개 / "
            f"신규 {len(new_urls)}개 / 누적 {len(found_urls)}개"
        )

        html = await page.content()
        debug_file = debug_dir / f"scroll_{scroll_idx}.html"
        debug_file.write_text(html, encoding="utf-8")

        if len(new_urls) == 0:
            stagnant_rounds += 1
        else:
            stagnant_rounds = 0

        if stagnant_rounds >= STOP_IF_NO_NEW_FOR:
            print("    -> 새 URL 증가가 멈춰서 종료")
            break

        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(WAIT_MS)

    sorted_urls = sorted(found_urls)
    output_file.write_text("\n".join(sorted_urls), encoding="utf-8")

    print(f"  -> 저장 파일: {output_file}")
    run_sanity_check(category_info, sorted_urls)


async def main():
    category_rows = load_category_master(CATEGORY_MASTER_CSV)

    if not category_rows:
        print("수집 대상 카테고리가 없습니다.")
        return

    print(f"수집 대상 카테고리 수: {len(category_rows)}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/146.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 2200},
            locale="ko-KR",
        )
        page = await context.new_page()

        for category_info in category_rows:
            await collect_one_small_category(page, category_info)

        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())