#!/usr/bin/env python3
"""
自动竞品分析脚本
针对微信小店每个商品，自动抓取京东竞品数据并生成分析报告
"""
import asyncio
import json
import re
import time
import random
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

import sys
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from playwright.async_api import async_playwright
from wechat_shop_api import WechatShopAPI

# 配置
OUTPUT_DIR = Path(__file__).parent / "competitor_analysis"
REPORT_DIR = OUTPUT_DIR / "reports"
MAX_PRODUCTS = 20  # 最多分析商品数
DELAY_MIN = 2  # 最小延迟（秒）
DELAY_MAX = 5  # 最大延迟（秒）

# 确保目录存在
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)
REPORT_DIR.mkdir(exist_ok=True, parents=True)


class JDCompetitorCrawler:
    """京东竞品爬虫"""
    
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.results = []
        
    async def init_browser(self):
        """初始化浏览器"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-background-networking',
                '--disable-extensions',
                '--disable-web-security',
            ]
        )
        
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
            extra_http_headers={
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
        )
        
        # 绕过自动化检测
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
        """)
        
        self.page = await self.context.new_page()
        
    async def close_browser(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
    
    async def random_delay(self):
        """随机延迟，避免被检测"""
        delay = random.uniform(DELAY_MIN, DELAY_MAX)
        await asyncio.sleep(delay)
    
    def parse_price(self, price_str: str) -> Optional[float]:
        """解析价格"""
        if not price_str:
            return None
        match = re.search(r'[\d.]+', price_str)
        if match:
            try:
                return float(match.group())
            except:
                pass
        return None
    
    async def search_product(self, keyword: str, product_id: str) -> Dict:
        """搜索商品并提取竞品信息"""
        result = {
            "keyword": keyword,
            "product_id": product_id,
            "competitors": [],
            "timestamp": datetime.now().isoformat(),
            "status": "pending"
        }
        
        try:
            # 构建搜索URL
            encoded_keyword = keyword.replace(" ", "+")
            url = f"https://search.jd.com/Search?keyword={encoded_keyword}&enc=utf-8&wq={encoded_keyword}"
            
            print(f"  🔍 搜索: {keyword}")
            
            # 访问搜索页面
            response = await self.page.goto(url, wait_until="networkidle", timeout=30000)
            
            if response.status != 200:
                raise Exception(f"页面加载失败，状态码: {response.status}")
            
            # 等待页面加载
            await asyncio.sleep(3)
            
            # 滚动加载更多商品
            for _ in range(5):
                await self.page.evaluate("window.scrollBy(0, window.innerHeight * 0.8)")
                await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # 提取页面内容
            content = await self.page.content()
            
            # 提取商品数据 - 多种方式尝试
            items = []
            
            # 方式1: 从JS变量提取 (JD搜索页的格式)
            # 尝试多种正则模式
            patterns = [
                r'"skuId":"?(\d+)"[^}]*"title":"([^"]+)"[^}]*"salePrice":"?([\d.]+)"?',
                r'"skuId":(\d+)[^}]*"title":"([^"]+)"[^}]*"salePrice":([\d.]+)',
                r'data-sku="(\d+)"[^>]*title="([^"]+)"[^>]*¥([\d.]+)',
                r'"price":"?([\d.]+)"[^}]*"title":"([^"]+)"',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content)
                if matches:
                    for match in matches[:20]:
                        if len(match) >= 3:
                            try:
                                if pattern.startswith(r'data-sku'):
                                    sku, title, price = match
                                else:
                                    sku, title, price = match[0], match[1], match[2]
                                items.append({
                                    "sku_id": sku if 'sku' not in locals() else None,
                                    "title": title.replace("\\/", "/").replace("&amp;", "&").strip()[:100],
                                    "price": float(price),
                                    "source": "jd_regex"
                                })
                            except (ValueError, IndexError):
                                continue
                    if items:
                        break
            
            # 方式2: 用 page.evaluate 从页面提取数据
            if not items:
                data = await self.page.evaluate("""
                    () => {
                        const results = [];
                        // 尝试从window搜索结果数据中获取
                        try {
                            // 查找页面中的商品数据
                            const goods = document.querySelectorAll('.gl-item, .goods-list li, [class*="item"]');
                            goods.forEach((good, idx) => {
                                const titleEl = good.querySelector('.p-name em, .p-name, .goods-title, [class*="title"]');
                                const priceEl = good.querySelector('.p-price .price, .p-price, [class*="price"]');
                                if (titleEl || priceEl) {
                                    const title = titleEl ? titleEl.innerText.trim() : '';
                                    const priceText = priceEl ? priceEl.innerText : '';
                                    const price = parseFloat(priceText.replace(/[^\\d.]/g, ''));
                                    if (title || price) {
                                        results.push({ title, price: price || 0 });
                                    }
                                }
                            });
                        } catch (e) {}
                        return results.slice(0, 20);
                    }
                """)
                if data and len(data) > 0:
                    for item in data[:20]:
                        if item.get("title") or item.get("price"):
                            items.append({
                                "title": str(item.get("title", ""))[:100],
                                "price": float(item.get("price", 0)) or 0,
                                "source": "jd_evaluate"
                            })
            
            # 方式3: 从页面URL和文本中提取
            if not items:
                # 提取所有包含价格的链接
                price_pattern = r'¥(\d+\.?\d*)'
                link_pattern = r'href="([^"]*item\.jd\.com[^"]*)"'
                
                urls = re.findall(link_pattern, content)
                text_blocks = content.split('\n')
                
                for i, url in enumerate(urls[:20]):
                    # 尝试从上下文获取价格
                    price_match = re.search(price_pattern, content[max(0, content.find(url)-200):content.find(url)+200])
                    price = float(price_match.group(1)) if price_match else 0
                    
                    if price > 0:
                        items.append({
                            "title": f"京东商品 #{i+1}",
                            "price": price,
                            "source": "jd_link_price"
                        })
            
            # 去重
            seen = set()
            unique_items = []
            for item in items:
                key = item.get("title", "")[:30]
                if key and key not in seen:
                    seen.add(key)
                    unique_items.append(item)
            
            result["competitors"] = unique_items
            result["count"] = len(unique_items)
            result["status"] = "success"
            
            print(f"    ✅ 找到 {len(unique_items)} 个竞品")
            
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            print(f"    ❌ 失败: {e}")
        
        return result
    
    async def run(self, products: List[Dict]):
        """运行爬虫"""
        print("\n" + "=" * 60)
        print("🚀 京东竞品分析爬虫启动")
        print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60 + "\n")
        
        await self.init_browser()
        
        try:
            for i, product in enumerate(products[:MAX_PRODUCTS]):
                product_id = product.get("product_id", "")
                title = product.get("title", "")
                
                print(f"\n[{i+1}/{min(len(products), MAX_PRODUCTS)}] 处理商品:")
                print(f"    ID: {product_id}")
                print(f"    名称: {title[:50]}")
                
                # 搜索关键词
                keywords = [
                    title.split("猫")[0] + "猫" if "猫" in title else title[:20],
                    title[:30],
                ]
                
                for kw in keywords:
                    result = await self.search_product(kw, product_id)
                    if result["status"] == "success" and result["competitors"]:
                        self.results.append(result)
                        break
                    
                    await self.random_delay()
                
                # 每个商品间隔
                await self.random_delay()
                
        finally:
            await self.close_browser()
        
        return self.results


def analyze_competitors(shop_products: List[Dict], competitor_results: List[Dict]) -> Dict:
    """分析竞品数据，生成报告"""
    
    analysis = {
        "generated_at": datetime.now().isoformat(),
        "shop_products_count": len(shop_products),
        "products_analyzed": [],
        "market_summary": {
            "total_competitors_found": 0,
            "avg_price_range": {"min": 0, "max": 0},
            "price_distribution": {}
        },
        "recommendations": []
    }
    
    for shop_product in shop_products:
        product_id = shop_product.get("product_id", "")
        title = shop_product.get("title", "")
        my_price = shop_product.get("min_price", 0) / 100
        
        # 找对应的竞品数据
        comp_data = next((r for r in competitor_results if r.get("product_id") == product_id), None)
        
        competitors = comp_data.get("competitors", []) if comp_data else []
        
        # 计算竞品价格统计
        prices = [c.get("price", 0) for c in competitors if c.get("price", 0) > 0]
        avg_price = sum(prices) / len(prices) if prices else 0
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0
        
        # 价格定位
        if my_price > 0:
            if my_price < min_price * 0.8:
                price_position = "偏低（性价比高）"
            elif my_price > max_price * 1.2:
                price_position = "偏高（高端定位）"
            else:
                price_position = "中等（主流价位）"
        else:
            price_position = "未定价"
        
        # 生成建议
        suggestions = []
        
        if my_price > 0 and my_price < avg_price * 0.7:
            suggestions.append("价格偏低，可适当提价提升利润")
        elif my_price > 0 and my_price > avg_price * 1.3:
            suggestions.append("价格偏高，需强化卖点或考虑降价")
        
        if not competitors:
            suggestions.append("未找到竞品数据，建议手动搜索验证")
        
        product_analysis = {
            "product_id": product_id,
            "title": title,
            "my_price": my_price,
            "competitors_count": len(competitors),
            "price_range": {"min": min_price, "max": max_price, "avg": round(avg_price, 2)},
            "price_position": price_position,
            "suggestions": suggestions,
            "top_competitors": competitors[:5] if competitors else []
        }
        
        analysis["products_analyzed"].append(product_analysis)
        analysis["market_summary"]["total_competitors_found"] += len(competitors)
    
    # 总体建议
    low_price_count = sum(1 for p in analysis["products_analyzed"] if "偏低" in p["price_position"])
    high_price_count = sum(1 for p in analysis["products_analyzed"] if "偏高" in p["price_position"])
    
    if low_price_count > high_price_count:
        analysis["recommendations"].append({
            "type": "pricing",
            "priority": "high",
            "content": f"有 {low_price_count} 个商品价格偏低，建议适当提价"
        })
    elif high_price_count > low_price_count:
        analysis["recommendations"].append({
            "type": "pricing",
            "priority": "high", 
            "content": f"有 {high_price_count} 个商品价格偏高，建议强化产品差异化或调整价格"
        })
    
    analysis["recommendations"].append({
        "type": "general",
        "priority": "medium",
        "content": "持续关注竞品价格变化，每周更新一次数据"
    })
    
    return analysis


def generate_markdown_report(analysis: Dict) -> str:
    """生成Markdown格式的报告"""
    
    md = f"""# 📊 微信小店竞品分析报告

> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> 分析商品数: {analysis['shop_products_count']}
> 发现竞品总数: {analysis['market_summary']['total_competitors_found']}

---

## 📋 商品分析详情

"""
    
    for p in analysis["products_analyzed"]:
        md += f"""
### {p['title'][:50]}{'...' if len(p['title']) > 50 else ''}

| 指标 | 数值 |
|------|------|
| 商品ID | {p['product_id']} |
| 我的价格 | ¥{p['my_price']:.2f} |
| 竞品数量 | {p['competitors_count']} |
| 竞品价格区间 | ¥{p['price_range']['min']:.2f} - ¥{p['price_range']['max']:.2f} |
| 竞品平均价 | ¥{p['price_range']['avg']:.2f} |
| 价格定位 | **{p['price_position']}** |

"""
        
        if p["top_competitors"]:
            md += "**Top 竞品:**\n\n"
            md += "| 排名 | 商品名称 | 价格 |\n"
            md += "|------|---------|------|\n"
            for i, comp in enumerate(p["top_competitors"][:5], 1):
                md += f"| {i} | {comp.get('title', 'N/A')[:40]} | ¥{comp.get('price', 0):.2f} |\n"
            md += "\n"
        
        if p["suggestions"]:
            md += "**💡 建议:**\n"
            for s in p["suggestions"]:
                md += f"- {s}\n"
            md += "\n"
        
        md += "---\n\n"
    
    # 总体建议
    md += """
## 🎯 总体运营建议

"""
    
    for rec in analysis.get("recommendations", []):
        priority_icon = "🔴" if rec["priority"] == "high" else "🟡" if rec["priority"] == "medium" else "🟢"
        md += f"{priority_icon} {rec['content']}\n\n"
    
    md += """
---

*报告由 ECAgent 自动生成*
"""
    
    return md


async def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("🛒 微信小店竞品分析")
    print("=" * 60)
    
    # 1. 获取微信小店商品
    print("\n📦 获取微信小店商品...")
    api = WechatShopAPI()
    shop_products = api.get_all_products()
    print(f"   共 {len(shop_products)} 个商品")
    
    for p in shop_products:
        print(f"   - {p.get('title', '')[:50]}")
    
    if not shop_products:
        print("❌ 没有获取到商品数据")
        return
    
    # 2. 爬取竞品数据
    print("\n🔍 开始爬取京东竞品数据...")
    crawler = JDCompetitorCrawler()
    competitor_results = await crawler.run(shop_products)
    
    print(f"\n✅ 爬取完成，共 {len(competitor_results)} 个商品有竞品数据")
    
    # 3. 分析数据
    print("\n📊 生成分析报告...")
    analysis = analyze_competitors(shop_products, competitor_results)
    
    # 4. 保存JSON报告
    report_file = REPORT_DIR / f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    print(f"   JSON报告: {report_file}")
    
    # 5. 保存Markdown报告
    md_report = generate_markdown_report(analysis)
    md_file = REPORT_DIR / f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(md_report)
    print(f"   Markdown报告: {md_file}")
    
    # 6. 更新latest报告
    with open(REPORT_DIR / "latest.md", "w", encoding="utf-8") as f:
        f.write(md_report)
    print(f"   最新报告: {REPORT_DIR / 'latest.md'}")
    
    # 7. 打印摘要
    print("\n" + "=" * 60)
    print("📋 分析摘要")
    print("=" * 60)
    
    for p in analysis["products_analyzed"]:
        print(f"\n【{p['title'][:40]}】")
        print(f"   价格定位: {p['price_position']}")
        print(f"   竞品数量: {p['competitors_count']}")
        if p['suggestions']:
            print(f"   建议: {p['suggestions'][0]}")
    
    print("\n" + "=" * 60)
    print("✅ 竞品分析完成！")
    print(f"📁 报告保存在: {REPORT_DIR}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())