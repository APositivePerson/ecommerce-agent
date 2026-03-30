#!/usr/bin/env python3
"""
京东竞品爬虫 v3 - API + Playwright 无头模式
"""
import asyncio
import json
import random
import re
import httpx
import time
from pathlib import Path
from playwright.async_api import async_playwright

OUTPUT_DIR = Path(__file__).parent

CATEGORIES = {
    "猫粮": ["猫粮", "成猫粮", "幼猫粮"],
    "猫罐头": ["猫罐头", "猫湿粮", "主食罐头"],
    "猫砂": ["猫砂", "豆腐猫砂", "膨润土猫砂"],
    "猫零食": ["猫零食", "猫条", "猫冻干"],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Referer": "https://www.jd.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}

async def random_delay(min_s=1.5, max_s=4):
    await asyncio.sleep(random.uniform(min_s, max_s))


def parse_price(price_str):
    if not price_str:
        return ""
    match = re.search(r'[\d.]+', price_str)
    return match.group() if match else ""


async def scrape_jd_product_api():
    """通过 JD 产品详情 API 批量抓取"""
    print("=" * 60)
    print("🚀 策略1: 通过 JD API 抓取商品数据")
    print("=" * 60)

    results = []
    api_url = "https://p.3.cn/prices/mgets"

    # 先用搜索API获取商品ID
    for category, keywords in CATEGORIES.items():
        for keyword in keywords:
            print(f"\n🔍 {category} - {keyword}")
            await random_delay(1, 2)

            # JD 搜索页面（带随机参数绕过缓存）
            ts = int(time.time() * 1000)
            search_url = f"https://search.jd.com/Search?keyword={keyword}&enc=utf-8&wq={keyword}&page=1&s=1&scrolling=y&logId="
            async with httpx.AsyncClient(headers=HEADERS, timeout=30.0, follow_redirects=True, trust_env=False) as client:
                try:
                    resp = await client.get(search_url)
                    content = resp.text
                    print(f"   搜索页: {len(content)} bytes, 状态: {resp.status_code}")

                    # 提取商品ID
                    sku_ids = re.findall(r'data-sku="(\d+)"', content)
                    if not sku_ids:
                        sku_ids = re.findall(r'"skuId":"?(\d+)"?', content)
                    if not sku_ids:
                        sku_ids = re.findall(r'/product/(\d+)\.html', content)
                    if not sku_ids:
                        sku_ids = re.findall(r'"id":(\d{4,})', content)

                    print(f"   找到商品ID: {sku_ids[:5]}")

                    # 提取商品信息
                    names = re.findall(r'class="[pjg]-name[^"]*"[^>]*>([^<]+)', content)
                    prices_in_page = re.findall(r'class="[pjg]-price[^"]*"[^>]*>.*?(\d+\.?\d*)', content)

                    for i, (sku, name_list) in enumerate(zip(sku_ids[:10], names[:10])):
                        if len(name_list.strip()) > 3:
                            price = prices_in_page[i] if i < len(prices_in_page) else ""
                            results.append({
                                "category": category,
                                "keyword": keyword,
                                "sku_id": sku,
                                "name": name_list.strip()[:100],
                                "price": parse_price(price),
                                "source": "jd.com"
                            })
                            print(f"   📦 [{parse_price(price)}元] {name_list.strip()[:50]}")

                except Exception as e:
                    print(f"   ❌ 失败: {e}")

            await random_delay(1, 3)

    return results


async def scrape_with_browser():
    """Playwright 无头浏览器模拟真人"""
    print("\n" + "=" * 60)
    print("🚀 策略2: Playwright 无头浏览器抓取")
    print("=" * 60)

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-background-networking',
                '--disable-extensions',
            ]
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )

        page = await context.new_page()

        # 绕过自动化检测
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        for category, keywords in CATEGORIES.items():
            for keyword in keywords:
                print(f"\n🔍 {category} - {keyword}")
                await random_delay(2, 4)

                url = f"https://search.jd.com/Search?keyword={keyword}&enc=utf-8"

                try:
                    resp = await page.goto(url, wait_until="networkidle", timeout=30000)
                    print(f"   状态: {resp.status}")
                except Exception as e:
                    print(f"   ❌ 加载失败: {e}")
                    continue

                await asyncio.sleep(3)

                # 滚动加载
                for _ in range(6):
                    await page.evaluate("window.scrollBy(0, window.innerHeight * 0.8)")
                    await asyncio.sleep(random.uniform(0.5, 1.0))

                await asyncio.sleep(2)

                # 截图（调试用）
                await page.screenshot(path=OUTPUT_DIR / f"jd_{keyword}.png", full_page=False)
                print(f"   📸 截图已保存")

                # 提取数据
                # 方式1: JSON-LD
                jsonld = await page.evaluate("""
                    () => {
                        const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                        let data = [];
                        scripts.forEach(s => {
                            try { data.push(...JSON.parse(s.textContent)); } catch(e) {}
                        });
                        return data;
                    }
                """)
                if jsonld:
                    print(f"   JSON-LD: {len(jsonld)} 条")

                # 方式2: 从页面源码提取
                content = await page.content()

                # 提取搜索结果
                items = re.findall(r'"title":"([^"]+)"[^}]*"skuId":"?(\d+)"?', content)
                prices = re.findall(r'"salePrice":"?([\d.]+)"?', content)

                for i, (name, sku) in enumerate(items[:20]):
                    price = prices[i] if i < len(prices) else ""
                    if len(name) > 3:
                        results.append({
                            "category": category,
                            "keyword": keyword,
                            "sku_id": sku,
                            "name": name.strip()[:100],
                            "price": parse_price(price),
                            "source": "jd.com"
                        })
                        print(f"   📦 [{parse_price(price)}元] {name.strip()[:50]}")

                await random_delay(2, 5)

        await browser.close()

    return results


async def main():
    print("🐱 京东竞品爬虫 v3")
    print(f"⏰ {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    all_results = []

    # 策略1: API
    api_results = await scrape_jd_product_api()
    all_results.extend(api_results)
    print(f"\n策略1完成: {len(api_results)} 条")

    # 策略2: 浏览器
    browser_results = await scrape_with_browser()
    all_results.extend(browser_results)
    print(f"\n策略2完成: {len(browser_results)} 条")

    # 去重
    seen = set()
    unique_results = []
    for r in all_results:
        key = (r.get("sku_id", ""), r.get("name", ""))
        if key not in seen and r.get("name"):
            seen.add(key)
            unique_results.append(r)

    # 保存
    results_file = OUTPUT_DIR / "jd_products_v3.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(unique_results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"✅ 完成！总计 {len(unique_results)} 条数据")
    print(f"💾 保存至: {results_file}")
    print(f"⏰ {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 统计
    summary = {}
    for item in unique_results:
        cat = item.get("category", "未知")
        if cat not in summary:
            summary[cat] = {"count": 0, "prices": []}
        summary[cat]["count"] += 1
        if item.get("price"):
            try:
                summary[cat]["prices"].append(float(item["price"]))
            except:
                pass

    print(f"\n📋 各品类:")
    for cat, info in summary.items():
        p = info["prices"]
        avg = sum(p) / len(p) if p else 0
        print(f"   {cat}: {info['count']} 条, 平均 ¥{avg:.1f}")


if __name__ == "__main__":
    asyncio.run(main())
