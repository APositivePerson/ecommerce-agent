#!/usr/bin/env python3
"""
竞品分析 - 使用 httpx 替代 playwright
更稳定、更快
"""
import requests
import json
import re
import time
import random
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# 配置
OUTPUT_DIR = Path(__file__).parent.parent / "competitor_analysis"
REPORT_DIR = OUTPUT_DIR / "reports"
MAX_PRODUCTS = 20
DELAY_MIN = 1
DELAY_MAX = 3

# Headers模拟浏览器
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.jd.com/",
}

OUTPUT_DIR.mkdir(exist_ok=True, parents=True)
REPORT_DIR.mkdir(exist_ok=True, parents=True)


class JDCompetitorCrawler:
    """京东竞品爬虫 - 使用requests"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.results = []
        
    def close(self):
        self.session.close()
    
    def random_delay(self):
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
    
    def parse_price(self, text: str) -> Optional[float]:
        if not text:
            return None
        match = re.search(r'[\d.]+', text)
        if match:
            try:
                return float(match.group())
            except:
                pass
        return None
    
    def search_product(self, keyword: str, product_id: str) -> Dict:
        result = {
            "keyword": keyword,
            "product_id": product_id,
            "competitors": [],
            "timestamp": datetime.now().isoformat(),
            "status": "pending"
        }
        
        try:
            encoded_keyword = keyword.replace(" ", "+")
            url = f"https://search.jd.com/Search?keyword={encoded_keyword}&enc=utf-8&wq={encoded_keyword}&page=1"
            
            print(f"  🔍 搜索: {keyword[:30]}...")
            
            response = self.session.get(url, timeout=30)
            content = response.text
            
            # 提取商品数据
            items = []
            
            # 从页面提取价格和标题
            search_items = re.findall(r'<li class="gl-item"[^>]*>(.*?)</li>', content, re.DOTALL)
            
            for i, item_html in enumerate(search_items[:20]):
                title_match = re.search(r'<em>([^<]+)</em>', item_html)
                title = title_match.group(1) if title_match else f"商品 #{i+1}"
                
                price_match = re.search(r'¥([\d.]+)', item_html)
                price = float(price_match.group(1)) if price_match else 0
                
                if price > 0:
                    # 清理HTML标签
                    title = re.sub(r'<[^>]+>', '', title).strip()[:80]
                    if len(title) > 5:
                        items.append({
                            "title": title,
                            "price": price,
                            "source": "jd_li"
                        })
            
            # 备用: 直接提取所有价格
            if not items:
                prices = re.findall(r'<em class="price">¥([\d.]+)</em>', content)
                for price_str in prices[:20]:
                    try:
                        p = float(price_str)
                        if 1 < p < 10000:
                            items.append({
                                "title": f"商品 ¥{p}",
                                "price": p,
                                "source": "jd_price"
                            })
                    except:
                        pass
            
            # 去重
            seen_prices = set()
            unique_items = []
            for item in items:
                p = int(item["price"] * 10)
                if p not in seen_prices:
                    seen_prices.add(p)
                    unique_items.append(item)
            
            result["competitors"] = unique_items[:15]
            result["count"] = len(unique_items)
            result["status"] = "success"
            
            print(f"    ✅ 找到 {len(unique_items)} 个价格数据")
            
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            print(f"    ❌ 失败: {e}")
        
        return result
    
    def run(self, products: List[Dict]):
        print("\n" + "=" * 60)
        print("🚀 京东竞品分析爬虫启动")
        print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60 + "\n")
        
        try:
            for i, product in enumerate(products[:MAX_PRODUCTS]):
                product_id = product.get("product_id", "")
                title = product.get("title", "")
                
                print(f"\n[{i+1}/{min(len(products), MAX_PRODUCTS)}] {title[:40]}...")
                
                # 提取关键词
                kw = title.split("猫")[0][:20] + "猫" if "猫" in title else title[:25]
                
                result = self.search_product(kw, product_id)
                if result["status"] == "success":
                    self.results.append(result)
                
                self.random_delay()
                
        finally:
            self.close()
        
        return self.results


def analyze_competitors(shop_products: List[Dict], competitor_results: List[Dict]) -> Dict:
    analysis = {
        "generated_at": datetime.now().isoformat(),
        "shop_products_count": len(shop_products),
        "products_analyzed": [],
        "market_summary": {"total_prices_found": 0},
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
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0
        
        if my_price > 0:
            if prices:
                if my_price < min_price * 0.8:
                    price_position = "偏低"
                elif my_price > max_price * 1.2:
                    price_position = "偏高"
                else:
                    price_position = "中等"
            else:
                price_position = "待分析"
        else:
            price_position = "未定价"
        
        suggestions = []
        if my_price > 0 and prices:
            if my_price < avg_price * 0.7:
                suggestions.append("价格偏低，可适当提价")
            elif my_price > avg_price * 1.3:
                suggestions.append("价格偏高，需强化卖点")
        
        product_analysis = {
            "product_id": product_id,
            "title": title,
            "my_price": my_price,
            "competitors_count": len(competitors),
            "price_range": {"min": min_price, "max": max_price, "avg": round(avg_price, 2)},
            "price_position": price_position,
            "suggestions": suggestions,
            "sample_prices": sorted(prices)[:10] if prices else []
        }
        
        analysis["products_analyzed"].append(product_analysis)
        analysis["market_summary"]["total_prices_found"] += len(prices)
    
    # 总体建议
    low_count = sum(1 for p in analysis["products_analyzed"] if p["price_position"] == "偏低")
    high_count = sum(1 for p in analysis["products_analyzed"] if p["price_position"] == "偏高")
    
    if low_count > high_count and low_count > 0:
        analysis["recommendations"].append({"priority": "high", "content": f"{low_count}个商品价格偏低，建议适当提价"})
    elif high_count > low_count and high_count > 0:
        analysis["recommendations"].append({"priority": "high", "content": f"{high_count}个商品价格偏高，建议调整或强化差异化"})
    
    analysis["recommendations"].append({"priority": "medium", "content": "持续关注竞品价格，每周更新数据"})
    
    return analysis


def generate_markdown_report(analysis: Dict) -> str:
    md = f"""# 📊 微信小店竞品分析报告

> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> 商品数: {analysis['shop_products_count']}
> 价格数据: {analysis['market_summary']['total_prices_found']}条

---

## 📋 商品价格分析

"""
    
    for p in analysis["products_analyzed"]:
        position_icon = "🟢" if p["price_position"] == "中等" else "🔵" if p["price_position"] == "偏低" else "🔴" if p["price_position"] == "偏高" else "⚪"
        
        md += f"""
### {position_icon} {p['title'][:50]}

| 项目 | 数值 |
|------|------|
| 我的价格 | ¥{p['my_price']:.2f} |
| 竞品数量 | {p['competitors_count']} |
| 价格区间 | ¥{p['price_range']['min']:.0f} - ¥{p['price_range']['max']:.0f} |
| 平均价 | ¥{p['price_range']['avg']:.0f} |
| 定位 | **{p['price_position']}** |

"""
        
        if p["sample_prices"]:
            md += f"**竞品价格样本:** {' / '.join([f'¥{x:.0f}' for x in p['sample_prices'][:8]])}\n\n"
        
        if p["suggestions"]:
            md += f"💡 {p['suggestions'][0]}\n\n"
        
        md += "---\n\n"
    
    md += """
## 🎯 运营建议

"""
    
    for rec in analysis.get("recommendations", []):
        icon = "🔴" if rec["priority"] == "high" else "🟡" if rec["priority"] == "medium" else "🟢"
        md += f"{icon} {rec['content']}\n\n"
    
    md += """
---
*ECAgent 自动生成*
"""
    
    return md


def main():
    print("\n" + "=" * 60)
    print("🛒 微信小店竞品分析")
    print("=" * 60)
    
    # 获取商品
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from wechat_shop_api import WechatShopAPI
    
    print("\n📦 获取微信小店商品...")
    api = WechatShopAPI()
    shop_products = api.get_all_products()
    print(f"   共 {len(shop_products)} 个商品\n")
    
    if not shop_products:
        print("❌ 没有获取到商品")
        return
    
    # 爬取
    print("🔍 爬取京东竞品数据...\n")
    crawler = JDCompetitorCrawler()
    competitor_results = crawler.run(shop_products)
    
    # 分析
    print("\n📊 生成分析报告...")
    analysis = analyze_competitors(shop_products, competitor_results)
    
    # 保存
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_file = REPORT_DIR / f"analysis_{ts}.json"
    md_file = REPORT_DIR / f"analysis_{ts}.md"
    latest_file = REPORT_DIR / "latest.md"
    
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    
    md = generate_markdown_report(analysis)
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(md)
    with open(latest_file, "w", encoding="utf-8") as f:
        f.write(md)
    
    print(f"\n✅ 完成! 报告: {md_file}")
    
    # 打印摘要
    print("\n" + "=" * 50)
    for p in analysis["products_analyzed"]:
        print(f"{p['title'][:35]}... | 定价:{p['price_position']} | 竞品:{p['competitors_count']}个")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()