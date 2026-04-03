"""
JD.com Cookie-Aware Crawler
使用已登录Cookie抓取JD竞品数据
支持：商品名称、价格、销量、评价、卖家信息
"""

import requests
import json
import time
import re
import os
from datetime import datetime
from typing import Dict, List, Optional

# JD.com 登录Cookie（已提供）
JD_COOKIES = {
    "__jda": "173673530.17746064027131028945616.1774606403.1774867565.1775015721.5",
    "__jdb": "173673530.9.17746064027131028945616|5.1775015721",
    "__jdc": "173673530",
    "__jdu": "17746064027131028945616",
    "__jdv": "178324346|www.google.com|-|referral|-|1774606402713",
    "_pst": "jd_KfxUghHQpPMK",
    "_tp": "XqZmFh00R1lVjeFI3mGFdw%3D%3D",
    "3AB9D23F7A4B3C9B": "YGHZYCMZ2EJ2XR3RSVZHRFE26MMUPDTMRILWIMPASJZMQYZJT3VR47TQIPBWD5O4AVOI3A5UQPF7PD6MO4XABNF7EQ",
    "shshshfpa": "845e995f-bb31-70c5-dfba-5e1c82d8c81c-1774607035",
    "pin": "jd_KfxUghHQpPMK",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.jd.com/",
}

SEARCH_KEYWORDS = [
    "猫粮", "狗粮", "猫砂", "宠物零食", "猫罐头", "狗零食",
    "猫窝", "狗窝", "宠物玩具", "猫爬架", "猫条", "猫冻干",
]

JD_SEARCH_URL = "https://search.jd.com/Search"
JD_PRODUCT_URL = "https://item.jd.com/{pid}.html"
JD_PRICE_URL = "https://p.3.cn/prices/mgets?skuIds={sku_ids}"
JD_STOCK_URL = "https://l.{location}.jd.com/data/get Stock?skuId={pid}"


class JDCookieCrawler:
    """JD Cookie认证爬虫"""

    def __init__(self, cookies: Dict[str, str] = None, delay: float = 2.0):
        self.session = requests.Session()
        self.cookies = cookies or JD_COOKIES
        self.delay = delay
        self.session.headers.update(HEADERS)
        
        # 设置Cookie
        for name, value in self.cookies.items():
            self.session.cookies.set(name, value)

    def _get(self, url: str, params: dict = None, retries: int = 3) -> Optional[requests.Response]:
        """带重试的GET请求"""
        for attempt in range(retries):
            try:
                resp = self.session.get(url, params=params, timeout=15)
                if resp.status_code == 200:
                    return resp
                elif resp.status_code == 403:
                    print(f"[WARN] 403 Forbidden (attempt {attempt+1}/{retries})")
                elif resp.status_code == 404:
                    return None
            except requests.exceptions.RequestException as e:
                print(f"[ERROR] Request failed (attempt {attempt+1}/{retries}): {e}")
            time.sleep(self.delay * (attempt + 1))
        return None

    def search_products(self, keyword: str, page: int = 1, sort: str = "sales") -> List[Dict]:
        """
        搜索商品
        sort: sales(销量), price_asc(价格升), price_desc(价格降), relevance(相关)
        """
        params = {
            "keyword": keyword,
            "enc": "utf-8",
            "page": page,
            "s": (page - 1) * 30 + 1,
            "click": 0,
        }
        
        if sort == "sales":
            params["ev"] = "exprice_0"
        elif sort == "price_asc":
            params["sort"] = "sort=sort_totalsales_1_d"
        elif sort == "price_desc":
            params["sort"] = "sort=sort_totalsales_1_a"
        
        url = JD_SEARCH_URL
        resp = self._get(url, params=params)
        if not resp:
            return []
        
        try:
            # 尝试解析JavaScript动态内容
            html = resp.text
            
            # 提取商品列表 (通过正则匹配)
            products = []
            
            # 方法1: 尝试从页面中提取skuid
            sku_pattern = re.compile(r'data-sku="(\d+)"')
            name_pattern = re.compile(r'<a[^>]+class="[^"]*p-name[^"]*"[^>]*>([^<]+)<')
            price_pattern = re.compile(r'<i class="[^"]*J_price[^"]*">([^<]+)</i>')
            
            # 从<script>中提取数据
            script_pattern = re.compile(r'skuIds\s*=\s*\[([^\]]+)\]')
            price_script = re.search(r'skuIds\s*=\s*\[([^\]]+)\]', html)
            
            skus = re.findall(r'"skuId":\s*"?(\d+)"?', html)
            
            # 提取商品信息
            item_blocks = re.findall(
                r'<li[^>]+class="[^"]*gl-item[^"]*"[^>]*data-sku="(\d+)"[^>]*>(.*?)</li>',
                html, re.DOTALL
            )
            
            if not item_blocks:
                # 备选：从script标签中提取
                item_blocks = re.findall(
                    r'\{.*?"skuId"\s*:\s*"?(\d+)"?.*?"skuName"\s*:\s*"([^"]+)".*?"skuPrice"\s*:\s*"([^"]+)".*?\}',
                    html, re.DOTALL
                )
            
            for block in item_blocks[:30]:  # 每页最多30个
                if len(block) >= 3:
                    sku_id = block[0] if isinstance(block, tuple) else block
                    name = block[1] if isinstance(block, tuple) and len(block) > 1 else ""
                    price = block[2] if isinstance(block, tuple) and len(block) > 2 else ""
                    
                    products.append({
                        "sku_id": sku_id,
                        "name": name.strip(),
                        "price": float(price) if price and price.replace(".", "").isdigit() else 0,
                        "keyword": keyword,
                        "source": "jd",
                        "crawled_at": datetime.now().isoformat(),
                    })
            
            return products
            
        except Exception as e:
            print(f"[ERROR] Failed to parse search results: {e}")
            return []

    def get_product_detail(self, sku_id: str) -> Optional[Dict]:
        """获取商品详情"""
        url = JD_PRODUCT_URL.format(pid=sku_id)
        resp = self._get(url)
        if not resp:
            return None
        
        html = resp.text
        
        # 提取价格
        price = 0
        price_match = re.search(r'<span[^>]+class="[^"]*price[^"]*"[^>]*>.*?([\d.]+)</span>', html, re.DOTALL)
        if price_match:
            price = float(price_match.group(1))
        
        # 提取商品名称
        name = ""
        name_patterns = [
            r'<div[^>]+class="[^"]*sku-name[^"]*"[^>]*>([^<]+)</div>',
            r'<h1[^>]+class="[^"]*item-title[^"]*"[^>]*>([^<]+)</h1>',
            r'"productName"\s*:\s*"([^"]+)"',
        ]
        for pattern in name_patterns:
            m = re.search(pattern, html, re.DOTALL)
            if m:
                name = m.group(1).strip()
                break
        
        # 提取店铺名称
        shop_name = ""
        shop_match = re.search(r'<a[^>]+class="[^"]*shop-name[^"]*"[^>]*>([^<]+)</a>', html)
        if shop_match:
            shop_name = shop_match.group(1).strip()
        
        # 提取评价数量
        comments = 0
        comment_match = re.search(r'<span[^>]+class="[^"]*comment-count[^"]*"[^>]*>([^<]+)</span>', html)
        if comment_match:
            count_str = comment_match.group(1)
            comments = self._parse_count(count_str)
        
        # 提取销量
        sales = 0
        sales_patterns = [
            r'"sales"\s*:\s*"?(\d+)"?',
            r'销量\s*[:：]\s*([\d万]+)',
            r'<span[^>]+class="[^"]*sales[^"]*"[^>]*>([^<]+)</span>',
        ]
        for pattern in sales_patterns:
            m = re.search(pattern, html)
            if m:
                sales = self._parse_count(m.group(1))
                break
        
        return {
            "sku_id": sku_id,
            "name": name,
            "price": price,
            "shop_name": shop_name,
            "comments": comments,
            "sales": sales,
            "url": url,
            "crawled_at": datetime.now().isoformat(),
        }
    
    def _parse_count(self, text: str) -> int:
        """解析数量字符串"""
        if not text:
            return 0
        text = text.strip().replace(",", "").replace("+", "")
        if "万" in text:
            try:
                return int(float(text.replace("万", "")) * 10000)
            except:
                return 0
        try:
            return int(text)
        except:
            return 0

    def get_product_prices(self, sku_ids: List[str]) -> Dict[str, float]:
        """批量获取商品价格"""
        if not sku_ids:
            return {}
        
        sku_str = ",".join([f"J_{sid}" for sid in sku_ids])
        url = JD_PRICE_URL.format(sku_ids=sku_str)
        
        resp = self._get(url)
        if not resp:
            return {}
        
        try:
            data = resp.json()
            prices = {}
            for item in data:
                sku = item.get("id", "").replace("J_", "")
                price = item.get("p", "0")
                prices[sku] = float(price) if price else 0
            return prices
        except Exception as e:
            print(f"[ERROR] Failed to parse prices: {e}")
            return {}

    def search_with_screenshot(self, keyword: str) -> List[Dict]:
        """
        搜索并截图（用于AI视觉分析）
        返回截图路径和商品基本信息
        """
        products = self.search_products(keyword)
        
        screenshots = []
        for i, product in enumerate(products[:5]):  # 最多截取前5个
            url = JD_PRODUCT_URL.format(pid=product["sku_id"])
            screenshot_path = f"competitor_analysis/jd_search_{keyword}_{i}_{int(time.time())}.png"
            
            # 注意：实际截图需要selenium/playwright
            # 这里记录URL供后续处理
            screenshots.append({
                "product": product,
                "screenshot_url": url,
                "screenshot_path": screenshot_path,
            })
        
        return screenshots

    def crawl_category(self, keyword: str, pages: int = 2) -> List[Dict]:
        """抓取整个类别的商品"""
        all_products = []
        
        for page in range(1, pages + 1):
            print(f"[INFO] Crawling {keyword} page {page}...")
            products = self.search_products(keyword, page=page)
            
            # 补充价格信息
            sku_ids = [p["sku_id"] for p in products]
            prices = self.get_product_prices(sku_ids)
            
            for product in products:
                product["price"] = prices.get(product["sku_id"], product.get("price", 0))
            
            all_products.extend(products)
            
            if len(products) < 10:
                break  # 没有更多结果
            
            time.sleep(self.delay)
        
        return all_products

    def save_results(self, products: List[Dict], filepath: str = None):
        """保存结果到JSON文件"""
        if filepath is None:
            filepath = os.path.join(
                os.path.dirname(__file__),
                "jd_cookie_products.json"
            )
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # 加载已有数据
        existing = []
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except:
                pass
        
        # 合并去重
        existing_ids = {p.get("sku_id") for p in existing if p.get("sku_id")}
        new_products = [p for p in products if p.get("sku_id") not in existing_ids]
        
        all_products = existing + new_products
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(all_products, f, ensure_ascii=False, indent=2)
        
        print(f"[INFO] Saved {len(new_products)} new products to {filepath}")
        print(f"[INFO] Total products: {len(all_products)}")
        return all_products


def run_crawl():
    """运行爬虫主函数"""
    print("[INFO] Starting JD Cookie Crawler...")
    
    crawler = JDCookieCrawler(delay=2.0)
    
    all_results = []
    
    for keyword in SEARCH_KEYWORDS:
        print(f"\n[INFO] Processing keyword: {keyword}")
        products = crawler.crawl_category(keyword, pages=2)
        print(f"[INFO] Found {len(products)} products for '{keyword}'")
        all_results.extend(products)
        
        # 避免请求过快
        time.sleep(3)
    
    # 保存结果
    output_path = os.path.join(
        os.path.dirname(__file__),
        "jd_cookie_products.json"
    )
    crawler.save_results(all_results, output_path)
    
    print(f"\n[INFO] Crawl complete! Total products: {len(all_results)}")
    
    # 生成分析报告
    analyze_results(all_results)
    
    return all_results


def analyze_results(products: List[Dict]):
    """分析抓取结果"""
    if not products:
        print("[WARN] No products to analyze")
        return
    
    # 按类别统计
    by_category = {}
    for p in products:
        cat = p.get("keyword", "未知")
        if cat not in by_category:
            by_category[cat] = {"count": 0, "total_price": 0, "prices": []}
        by_category[cat]["count"] += 1
        if p.get("price", 0) > 0:
            by_category[cat]["total_price"] += p["price"]
            by_category[cat]["prices"].append(p["price"])
    
    print("\n" + "="*60)
    print("竞品分析报告")
    print("="*60)
    
    for cat, info in sorted(by_category.items(), key=lambda x: -x[1]["count"]):
        avg_price = info["total_price"] / len(info["prices"]) if info["prices"] else 0
        print(f"\n【{cat}】")
        print(f"  商品数: {info['count']}")
        if info["prices"]:
            print(f"  平均价格: ¥{avg_price:.2f}")
            print(f"  价格区间: ¥{min(info['prices']):.2f} - ¥{max(info['prices']):.2f}")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    run_crawl()
