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
        """打开jd.com，已登录则直接继续；未登录则扫码，扫完即开始搜索，不做任何多余操作"""
        print("  🌐 打开京东主页...")
        await self.page.goto('https://www.jd.com/', timeout=30000, wait_until='domcontentloaded')
        await asyncio.sleep(2)  # 简单等一下，让页面自然渲染

        try:
            await self.page.wait_for_selector('.nickname', timeout=5000)
            print(f"  ✅ 已登录")
        except Exception:
            print("  ⚠️ 未登录，请在浏览器窗口扫码登录京东（5分钟内扫完即可）")
            try:
                await self.page.wait_for_selector('.nickname', timeout=300)
                print(f"  ✅ 登录成功，直接开始搜索")
            except Exception:
                print("  ⚠️ 扫码超时，将以未登录状态继续（部分数据可能为空）")
    
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
            
            # 在当前页面使用搜索框，而不是每次goto新URL
            for selector in ['#key', 'input#key', 'input.search-key', '[id="key"]']:
                try:
                    inp = self.page.locator(selector).first
                    if await inp.is_visible(timeout=2000):
                        await inp.click()
                        await inp.fill(keyword)
                        await inp.press('Enter')
                        break
                except Exception:
                    continue
            else:
                # 兜底：直接导航到搜索页
                encoded_kw = keyword.replace(" ", "+")
                await self.page.goto(
                    f'https://search.jd.com/Search?keyword={encoded_kw}&enc=utf-8&wq={encoded_kw}',
                    wait_until='domcontentloaded', timeout=20000
                )
            
            # 等待搜索结果加载
            await self.human_delay(2000, 3500)
            
            # 模拟人类行为
            await self.human_scroll()
            await self.human_mouse_move()
            
            # 再次滚动加载更多
            await self.human_scroll()
            
            # 等待异步加载完成（不用networkidle，用固定延迟避免触发安全检测）
            await asyncio.sleep(2)
            
            # 提取数据
            content = await self.page.content()
            
            # 多种方式提取价格和评价数
            items = []
            
            # 方式1: 从页面结构提取（价格 + 评价数）
            items_data = await self.page.evaluate("""
                () => {
                    const results = [];
                    const items = document.querySelectorAll('.gl-item, li[data-sku]');
                    items.forEach((item, idx) => {
                        if (idx >= 20) return;
                        
                        let title = '';
                        let price = 0;
                        let comment_count = '';
                        
                        // 获取标题
                        const titleEl = item.querySelector('.p-name em, .p-name, .goods-title');
                        if (titleEl) title = titleEl.innerText.trim();
                        
                        // 获取价格
                        const priceEl = item.querySelector('.p-price .price, .p-price i, [class*="price"]');
                        if (priceEl) {
                            const priceText = priceEl.innerText;
                            const match = priceText.match(/[\\d.]+/);
                            if (match) price = parseFloat(match[0]);
                        }
                        
                        // 获取评价数（JD DOM结构: <div class="p-commit"><a>10万+条评价</a>）
                        const commitEl = item.querySelector('.p-commit a, .p-commit');
                        if (commitEl) {
                            const commitText = commitEl.innerText.trim();
                            // 匹配 "10万+条评价" / "1.2万" / "500+" 等格式
                            const match = commitText.match(/([\\d.]+)\\s*[万万千百]?/);
                            if (match) {
                                let num = parseFloat(match[1]);
                                if (commitText.includes('万')) num *= 10000;
                                else if (commitText.includes('千')) num *= 1000;
                                comment_count = num;
                            }
                        }
                        
                        // 备选：从整个item文本中搜索评价数
                        if (!comment_count) {
                            const itemText = item.innerText;
                            const cMatch = itemText.match(/([\\d.]+)\\s*[万万千百]?\\s*(?:条)?评价/);
                            if (cMatch) {
                                let num = parseFloat(cMatch[1]);
                                if (itemText.includes('万')) num *= 10000;
                                comment_count = num;
                            }
                        }
                        
                        // 如果没找到价格，从整个item中搜索
                        if (!price) {
                            const itemText = item.innerText;
                            const priceMatch = itemText.match(/¥([\\d.]+)/);
                            if (priceMatch) price = parseFloat(priceMatch[1]);
                        }
                        
                        if (title || price > 0) {
                            results.push({ title: title || '商品', price, comment_count });
                        }
                    });
                    return results;
                }
            """)
            
            if items_data and len(items_data) > 0:
                for item in items_data:
                    if item.get('price', 0) > 0:
                        items.append({
                            'title': str(item.get('title', '商品'))[:60],
                            'price': float(item['price']),
                            'comment_count': item.get('comment_count', ''),
                            'source': 'playwright_js'
                        })
            
            # 方式2: 如果上面没拿到，从页面源码正则提取
            if len(items) < 3:
                # 尝试多种价格正则
                price_patterns = [
                    r'<em class="price">¥([\d.]+)</em>',
                    r'class="p-price".*?<i>¥</i><strong>([\d.]+)</strong>',
                    r'"salePrice":"?([\d.]+)"?',
                ]
                
                for pattern in price_patterns:
                    prices = re.findall(pattern, content)
                    for p_str in prices[:20]:
                        try:
                            p = float(p_str)
                            if 1 < p < 10000:
                                items.append({
                                    'title': f'商品 ¥{p}',
                                    'price': p,
                                    'comment_count': '',
                                    'source': 'regex'
                                })
                        except:
                            pass
                    if items:
                        break
            
            # 方式3: 从嵌入的 search.jd.com API JSON 中提取（最准确，含评价数）
            try:
                api_json_matches = re.findall(
                    r'search_jd_com\.(?:search_result_v2|SearchResult)\s*=\s*(\{.{0,50000})',
                    content
                )
                for match in api_json_matches[:1]:
                    import ast
                    try:
                        # 截断到有效JSON末尾
                        raw = match.strip()
                        # 尝试找完整对象
                        obj_str = raw
                        data = json.loads(obj_str)
                        products = (data.get('result', {}) or {}).get('products', [])
                        if not products:
                            products = data.get('wareList', []) or data.get('goodsList', []) or []
                        for p in products[:20]:
                            title = p.get('name', '') or p.get('title', '') or p.get('wareName', '')
                            price = float(p.get('price', 0) or p.get('salePrice', 0) or 0)
                            raw_count = p.get('commentCount', '') or p.get('comments', '') or ''
                            comment_count = 0
                            if raw_count:
                                try:
                                    comment_count = int(str(raw_count).replace(',', ''))
                                except:
                                    comment_count = 0
                            if price > 0 and title:
                                items.append({
                                    'title': title[:60],
                                    'price': price,
                                    'comment_count': comment_count,
                                    'source': 'api_json'
                                })
                    except (json.JSONDecodeError, KeyError):
                        pass
            except Exception:
                pass
            
            # 去重（按价格档位 + 标题前10字去重）
            seen = set()
            unique_items = []
            for item in items:
                p_key = (int(item['price'] * 10), item['title'][:10])
                if p_key not in seen and item['price'] > 0:
                    seen.add(p_key)
                    # 保留评价数最大的那个
                    existing = next((u for u in unique_items if int(u['price'] * 10) == int(item['price'] * 10)), None)
                    if existing:
                        if item.get('comment_count', 0) > existing.get('comment_count', 0):
                            unique_items[unique_items.index(existing)] = item
                    else:
                        unique_items.append(item)
            
            result['competitors'] = unique_items[:15]
            result['count'] = len(unique_items)
            result['status'] = 'success'
            
            print(f"    ✅ 找到 {len(unique_items)} 个商品")
            
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
    """
    从微信小店商品标题中提取适合京东搜索的关键词。
    策略：
    1. 找品类词（品类词后紧跟数字+单位的，排除规格描述）
    2. 品类词前取≤6字（优先提取英文/数字品牌词）
    3. 无品类词则取前8字
    """
    CATEGORY_PATTERNS = [
        '猫粮', '狗粮', '猫砂', '猫罐头', '猫零食', '猫冻干', '猫条',
        '猫湿粮', '幼猫粮', '成猫粮', '化毛膏', '营养膏',
        '鸡肉味', '三文鱼味', '牛肉味', '除口臭', '洁牙', '牙膏',
        '膨润土', '豆腐砂', '混合砂', '钠基砂', '矿晶砂', '冻干',
        '羊奶粉', '奶糕', '风干粮',
    ]

    best_cat, best_idx = None, 999
    for cat in CATEGORY_PATTERNS:
        idx = title.find(cat)
        if idx == -1:
            continue
        after = title[idx + len(cat):idx + len(cat) + 3]
        # 品类词后紧跟数字（规格描述如 "10lb4.5kg"），跳过
        if re.match(r'[\d.]', after):
            continue
        if idx < best_idx:
            best_idx = idx
            best_cat = cat

    if best_cat:
        before = title[:best_idx]
        # 提取英文/数字词（品牌/型号），用于精确搜索
        words = re.findall(r'[A-Za-z0-9]+', before)
        if words:
            kw = words[-1] + ' ' + best_cat
        else:
            kw = before[-6:].strip() + ' ' + best_cat
        return kw.strip()[:22].strip()

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