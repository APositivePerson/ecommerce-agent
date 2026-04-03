#!/usr/bin/env python3
"""
京东竞品分析爬虫 - 增强反检测版本
模拟人类行为，降低被封风险
"""
import asyncio
import json
import random
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict

from playwright.async_api import async_playwright
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from wechat_shop_api import WechatShopAPI

# 配置
OUTPUT_DIR = Path(__file__).parent.parent / "competitor_analysis"
REPORT_DIR = OUTPUT_DIR / "reports"
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)
REPORT_DIR.mkdir(exist_ok=True, parents=True)


class JDCrawlerEnhanced:
    """增强版京东爬虫 - 模拟人类行为"""
    
    def __init__(self):
        self.browser = None
        self.page = None
        self.results = []
        self.cookie_file = OUTPUT_DIR / "jd_cookies.json"
        # 独立的Chrome配置目录，避免和用户日常Chrome冲突
        self.chrome_profile_dir = OUTPUT_DIR / ".chrome_profile"
        
    async def init_browser(self):
        """初始化浏览器 - 更隐蔽的配置"""
        playwright = await async_playwright().start()
        
        # 使用独立Chrome配置目录，永久保存登录态（只需登录一次）
        self.context = await playwright.chromium.launch_persistent_context(
            str(self.chrome_profile_dir),
            headless=False,
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
            permissions=['geolocation', 'notifications'],
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-infobars',
                '--disable-extensions',
                '--disable-plugins-discovery',
                '--disable-default-apps',
                '--disable-sync',
                '--mute-audio',
                '--safebrowsing-disable-auto-update',
            ]
        )
        
        # 取第一个已有页面，或新建一个
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        self.page.set_default_timeout(60000)
        self.page.set_default_timeout(60000)
        
        # 拦截部分请求，减少不必要的加载
        await self.page.route('**/*', lambda route: route.continue_() 
            if not any(x in route.request.url for x in ['jd.com', '360buyimg.com', 'baidu.com']) 
            else route.continue_())
    
    async def human_delay(self, min_ms=500, max_ms=2000):
        """模拟人类随机延迟"""
        await asyncio.sleep(random.randint(min_ms, max_ms) / 1000)
    
    async def human_scroll(self):
        """模拟人类滚动行为，最多2次"""
        for _ in range(random.randint(1, 2)):
            scroll_amount = random.randint(200, 500)
            await self.page.evaluate(f'window.scrollBy(0, {scroll_amount})')
            await self.human_delay(300, 800)
    
    async def human_mouse_move(self):
        """模拟人类鼠标移动"""
        # 随机移动鼠标到不同位置
        for _ in range(random.randint(2, 5)):
            x = random.randint(100, 800)
            y = random.randint(100, 600)
            await self.page.mouse.move(x, y)
            await self.human_delay(100, 300)
    
    async def _ensure_jd_login(self):
        """直接打开京东，等用户自己操作登录/扫码，完成后按回车继续"""
        print("  🌐 正在打开京东，请自己在浏览器里登录/扫码...")
        print("  （登录完成后在终端按回车继续）")
        await self.page.goto('https://www.jd.com/', timeout=30000, wait_until='domcontentloaded')
        
        # 在线程里等待回车，避免阻塞事件循环
        await asyncio.to_thread(input, "\n  ⏎ 登录完成后按回车继续: ")
        print("  ✅ 收到，继续执行")
    
    async def search_and_scrape(self, keyword: str, product_id: str) -> Dict:
        """搜索并抓取数据"""
        result = {
            "keyword": keyword,
            "product_id": product_id,
            "competitors": [],
            "status": "pending"
        }

        try:
            print(f"  🔍 搜索: {keyword[:25]}...")

            # 先打开 JD 搜索结果页（通过 JD 站内链接进入，降低反爬风险）
            encoded_kw = keyword.replace(" ", "+")
            await self.page.goto(
                f'https://search.jd.com/Search?keyword={encoded_kw}&enc=utf-8&wq={encoded_kw}',
                timeout=25000
            )

            # 等搜索结果出现（JD动态渲染）
            try:
                await self.page.wait_for_selector(
                    '#J_goodsList, .gl-item, li[data-sku], [class*="goods"]',
                    timeout=12000
                )
            except Exception:
                pass

            # 等JS完全渲染
            await asyncio.sleep(3)

            # 提取数据
            items = []

            # 方法A: Playwright JS 提取
            raw_items = await self.page.evaluate("""
                () => {
                    // 尝试多个可能的选择器
                    const selectors = [
                        '#J_goodsList li',
                        '.gl-item',
                        'li[data-sku]',
                        "[class*='goods-list'] li",
                        '.search-result li'
                    ];
                    let lis = [];
                    for (const sel of selectors) {
                        lis = document.querySelectorAll(sel);
                        if (lis.length > 0) break;
                    }
                    if (lis.length === 0) {
                        // 兜底: 找所有含价格的结构
                        const all = document.querySelectorAll('li');
                        lis = Array.from(all).filter(li => li.innerText.includes('¥') && li.innerText.length > 10);
                    }
                    return Array.from(lis).slice(0, 20).map(li => {
                        let title = '', price = 0, comment = 0;
                        // 标题
                        const titleEl = li.querySelector('.p-name em, [class*="name"] em, a[title], [class*="title"]');
                        if (titleEl) {
                            title = titleEl.innerText.replace(/<[^>]+>/g, '').trim();
                        }
                        // 价格
                        const priceEl = li.querySelector('.p-price i, [class*="price"], strong[class*="price"]');
                        if (priceEl) {
                            const m = priceEl.innerText.match(/[\\d.]+/);
                            if (m) price = parseFloat(m[0]);
                        }
                        if (!price) {
                            const t = li.innerText;
                            const pm = t.match(/¥([\\d.]+)/);
                            if (pm) price = parseFloat(pm[1]);
                        }
                        // 评价数
                        const cEl = li.querySelector('.p-commit a, .p-commit');
                        if (cEl) {
                            const ct = cEl.innerText;
                            const cm = ct.match(/([\\d.]+)/);
                            if (cm) {
                                comment = parseFloat(cm[1]);
                                if (ct.includes('万')) comment *= 10000;
                                else if (ct.includes('千')) comment *= 1000;
                            }
                        }
                        return { title: title.substring(0, 60), price, comment };
                    }).filter(x => x.price > 0 && x.price < 10000);
                }
            """)

            for item in raw_items:
                items.append({
                    'title': item['title'],
                    'price': float(item['price']),
                    'comment_count': int(item.get('comment') or 0),
                    'source': 'js_eval'
                })

            # 方法B: HTML源码正则兜底
            if len(items) < 3:
                html = await self.page.content()
                # 找内嵌JSON
                import re as _re
                for pattern in [
                    r'search_jd_com\.[^<]{0,100}\s*=\s*(\{.{0,20000})',
                    r'wareList\s*=\s*(\[.{0,10000}\])',
                    r'"goodsList":\s*(\[.{0,10000})',
                ]:
                    matches = _re.findall(pattern, html)
                    for block in matches[:1]:
                        try:
                            block = block.strip().rstrip(';')
                            data = json.loads(block)
                            if isinstance(data, list):
                                prods = data
                            else:
                                prods = (data.get('result') or {}).get('products') or data.get('wareList') or data.get('goodsList') or []
                            for p in prods[:20]:
                                title = p.get('name', '') or p.get('title', '') or p.get('wareName', '')
                                price = float(p.get('price', 0) or p.get('salePrice', 0) or 0)
                                cnt = int(str(p.get('commentCount', 0)).replace(',', '') or 0)
                                if price > 0:
                                    items.append({'title': title[:60], 'price': price, 'comment_count': cnt, 'source': 'json'})
                        except (json.JSONDecodeError, ValueError, KeyError, TypeError):
                            pass
                    if len(items) >= 3:
                        break

            # 去重
            seen, unique = set(), []
            for item in items:
                key = (int(item['price'] * 10), item['title'][:10])
                if key not in seen and item['price'] > 0:
                    seen.add(key)
                    unique.append(item)
            items = unique[:15]

            result['competitors'] = items
            result['count'] = len(items)
            result['status'] = 'success'
            print(f"    ✅ 找到 {len(items)} 个商品")

        except Exception as e:
            result['status'] = 'failed'
            result['error'] = str(e)
            print(f"    ❌ 失败: {e}")

        return result
    
    async def run(self, products: List[Dict]):
        """运行爬虫"""
        print("\n" + "=" * 60)
        print("🚀 京东竞品分析 (增强反检测版)")
        print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60 + "\n")
        
        await self.init_browser()
        
        # 先确保登录 JD
        await self._ensure_jd_login()
        
        try:
            for i, product in enumerate(products):
                product_id = product.get('product_id', '')
                title = product.get('title', '')
                
                print(f"\n[{i+1}/{len(products)}] {title[:40]}...")
                
                # 提取关键词：优先识别完整品类词，其次提取品牌+品类
                kw = _extract_search_keyword(title)
                
                # 搜索
                result = await self.search_and_scrape(kw, product_id)
                if result['status'] == 'success':
                    self.results.append(result)
                
                # 人类-like 延迟
                await self.human_delay(2000, 5000)
                
        finally:
            await self.context.close()
        
        return self.results


def _extract_search_keyword(title: str) -> str:
    """直接提取品类词，不要品牌前缀。"""
    CATEGORY_PATTERNS = [
        '猫粮', '狗粮', '猫砂', '猫罐头', '猫零食', '猫冻干', '猫条',
        '猫湿粮', '幼猫粮', '成猫粮', '化毛膏', '营养膏',
        '鸡肉味', '三文鱼味', '牛肉味', '除口臭', '洁牙', '牙膏',
        '膨润土', '豆腐砂', '混合砂', '钠基砂', '矿晶砂', '冻干',
        '羊奶粉', '奶糕', '风干粮',
    ]
    for cat in CATEGORY_PATTERNS:
        idx = title.find(cat)
        if idx == -1:
            continue
        after = title[idx + len(cat):idx + len(cat) + 3]
        if re.match(r'[\d.]', after):  # 品类词后紧跟数字=规格，跳过
            continue
        return cat  # 只返回品类词，不要品牌

    return title[:8].strip()


def analyze(shop_products, competitor_results):
    """分析数据"""
    analysis = {
        "generated_at": datetime.now().isoformat(),
        "shop_products_count": len(shop_products),
        "products_analyzed": [],
        "recommendations": []
    }
    
    for shop_product in shop_products:
        product_id = shop_product.get("product_id", "")
        title = shop_product.get("title", "")
        my_price = shop_product.get("min_price", 0) / 100 if shop_product.get("min_price") else 0
        
        comp_data = next((r for r in competitor_results if r.get("product_id") == product_id), None)
        competitors = comp_data.get("competitors", []) if comp_data else []
        
        prices = [c.get("price", 0) for c in competitors if 0 < c.get("price", 0) < 10000]
        
        avg_price = sum(prices) / len(prices) if prices else 0
        price_position = "待分析"
        if my_price > 0 and prices:
            if my_price < min(prices) * 0.8:
                price_position = "偏低"
            elif my_price > max(prices) * 1.2:
                price_position = "偏高"
            else:
                price_position = "中等"
        
        # 收集竞品评价数
        comment_counts = [c.get('comment_count', 0) for c in competitors if c.get('comment_count', 0)]
        avg_comment = round(sum(comment_counts) / len(comment_counts)) if comment_counts else 0
        max_comment = max(comment_counts) if comment_counts else 0
        
        product_analysis = {
            "product_id": product_id,
            "title": title,
            "my_price": my_price,
            "competitors_count": len(competitors),
            "price_range": {"min": min(prices) if prices else 0, "max": max(prices) if prices else 0, "avg": round(avg_price, 2)},
            "price_position": price_position,
            "sample_prices": sorted(prices)[:10],
            "comment_stats": {
                "avg": avg_comment,
                "max": max_comment,
                "samples": sorted(comment_counts, reverse=True)[:8]
            }
        }
        analysis["products_analyzed"].append(product_analysis)
    
    return analysis


async def main():
    print("\n🛒 京东竞品分析 - 增强版\n")
    
    # 获取商品
    print("📦 获取微信小店商品...")
    api = WechatShopAPI()
    shop_products = api.get_all_products()
    print(f"   共 {len(shop_products)} 个商品\n")
    
    if not shop_products:
        print("❌ 无商品")
        return
    
    # 爬取
    print("🔍 开始爬取...\n")
    crawler = JDCrawlerEnhanced()
    competitor_results = await crawler.run(shop_products)
    
    # 分析
    print("\n📊 分析中...")
    analysis = analyze(shop_products, competitor_results)
    
    # 保存
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_file = REPORT_DIR / f"analysis_{ts}.json"
    md_file = REPORT_DIR / f"analysis_{ts}.md"
    latest_file = REPORT_DIR / "latest.md"
    
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    
    # 生成Markdown
    md = f"""# 微信小店竞品分析报告

> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> 商品数: {len(shop_products)}

## 商品分析

"""
    for p in analysis["products_analyzed"]:
        comment_stats = p.get('comment_stats', {})
        avg_c = comment_stats.get('avg', 0)
        max_c = comment_stats.get('max', 0)
        md += f"""
### {p['title'][:50]}

| 指标 | 数值 |
|------|------|
| 我的价格 | ¥{p['my_price']:.2f} |
| 竞品数 | {p['competitors_count']} |
| 价格区间 | ¥{p['price_range']['min']:.0f} - ¥{p['price_range']['max']:.0f} |
| 均价 | ¥{p['price_range']['avg']:.0f} |
| 定位 | {p['price_position']} |
| **竞品评价数均值** | **{avg_c:,.0f}** |
| **竞品评价数最高** | **{max_c:,.0f}** |

"""
        if p.get('sample_prices'):
            md += f"竞品价格: {' / '.join([f'¥{x:.0f}' for x in p['sample_prices'][:8]])}\n"
        comment_samples = comment_stats.get('samples', [])
        if comment_samples:
            def fmt(n):
                if n >= 10000: return f'{n/10000:.1f}万'
                return f'{n:.0f}'
            md += f"竞品评价数: {' / '.join([fmt(x) for x in comment_samples])}\n"
        md += "\n"
    
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(md)
    with open(latest_file, "w", encoding="utf-8") as f:
        f.write(md)
    
    print(f"\n✅ 完成! 报告: {md_file}")
    print("\n" + "=" * 60)
    print(f"{'商品':<30} {'本店价':>8} {'竞品均评价数':>12} {'价格定位':>8}")
    print("-" * 60)
    for p in analysis["products_analyzed"]:
        avg_c = p.get('comment_stats', {}).get('avg', 0)
        def fmt_c(n):
            if n >= 10000: return f'{n/10000:.1f}万'
            return f'{n:.0f}'
        print(f"{p['title'][:30]:<30} ¥{p['my_price']:>6.1f} {fmt_c(avg_c):>12} {p['price_position']:>8}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())