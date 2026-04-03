#!/usr/bin/env python3
"""
JD竞品数据抓取脚本 v6 - 通过拦截AJAX接口获取搜索结果
绕过页面渲染问题，直接抓JD搜索API的JSON数据
"""
import json, time, re, sys, os

def get_wechat_products():
    sys.path.insert(0, os.path.dirname(__file__))
    try:
        from wechat_shop_api import WechatShopAPI
        api = WechatShopAPI()
        products = api.get_all_products()
        result = []
        for p in products:
            title = p.get('title') or p.get('name', '')
            price = (p.get('min_price', 0) or 0) / 100
            status = p.get('status', 0)
            if status == 5 and title:
                result.append({'title': title, 'price': price, 'spec': extract_spec(title)})
        return result
    except Exception as e:
        print(f"⚠️ 无法获取微信商品: {e}")
        return []


def extract_spec(title: str):
    text = title.lower()
    patterns = [
        (r'([\d.]+)\s*(?:kg|千克|公斤)', 'kg'),
        (r'([\d.]+)\s*(?:g|克)', 'g'),
        (r'([\d.]+)\s*(?:lb)', 'lb'),
        (r'([\d.]+)\s*(?:l|升)', 'L'),
        (r'([\d.]+)\s*(?:ml|毫升)', 'ml'),
    ]
    for pat, unit in patterns:
        m = re.search(pat, text)
        if m:
            val = float(m.group(1))
            return {'value': val, 'raw': m.group(0), 'unit': unit}
    return None


def to_per_kg(price, spec):
    if not spec:
        return price
    val = spec['value']
    unit = spec['unit']
    if unit == 'kg':    return price / val
    elif unit == 'g':   return (price / val) * 1000
    elif unit == 'lb':  return (price / val) * 2.20462
    elif unit == 'L':   return price / val
    elif unit == 'ml':  return (price / val) * 1000
    return price


def per_kg_str(price_per_kg, spec):
    if not spec:
        return f"¥{price_per_kg:.1f}/份"
    val = spec['value']
    u = spec['unit']
    unit_label = {'kg':'kg','g':'g','lb':'lb','L':'L','ml':'ml'}.get(u, '')
    if u == 'g':
        return f"¥{price_per_kg:.1f}/kg(共{val:.0f}g)"
    return f"¥{price_per_kg:.1f}/kg"


def extract_search_kw(title: str) -> str:
    title_clean = re.sub(r'[\d.]+\s*(?:kg|g|ml|lb|升|毫升|克|公斤)', '', title, flags=re.I)
    title_clean = re.sub(r'[（(].*?[）)]', '', title_clean)
    for kw in ['猫粮','狗粮','猫砂','猫罐头','猫零食','猫冻干','猫条',
               '化毛膏','营养膏','猫窝','猫爬架','鸡肉味','三文鱼','牛肉味']:
        if kw in title_clean:
            return kw
    return title_clean[:8].strip()


def run():
    from playwright.sync_api import sync_playwright
    import urllib.parse

    print("📦 读取微信小店商品...")
    wechat_products = get_wechat_products()
    if not wechat_products:
        print("❌ 无法获取微信商品"); return
    print(f"   {len(wechat_products)} 个在售商品\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
            viewport={'width': 1920, 'height': 1080},
        )
        page = context.new_page()

        # 拦截JD搜索API
        search_api_responses = []
        def on_api_response(response):
            url = response.url
            # 捕获JD搜索结果API
            if 'search.jd.com' in url and ('keyword' in url or 'k' in url):
                try:
                    data = response.json()
                    search_api_responses.append({'url': url, 'data': data})
                except Exception:
                    pass

        page.on('response', on_api_response)

        page.goto('https://www.jd.com/', timeout=30000, wait_until='domcontentloaded')
        page.wait_for_timeout(2000)

        try:
            page.wait_for_selector('.nickname', timeout=3000)
            print("✅ 已登录\n")
        except Exception:
            print("⚠️ 请扫码登录京东...\n")
            page.wait_for_selector('.nickname', timeout=120000)
            print("✅ 登录成功\n")

        all_results = []

        for item in wechat_products:
            title = item['title']
            title_short = title[:35]
            my_price = item['price']
            my_spec = item['spec']
            kw = extract_search_kw(title)
            my_per_kg = to_per_kg(my_price, my_spec) if my_spec else 0
            spec_str = per_kg_str(my_per_kg, my_spec) if my_spec else f"¥{my_price:.1f}/份"

            print(f"  🔍 {title_short}... [{kw}]", end=" ", flush=True)

            search_api_responses.clear()

            try:
                page.goto('https://www.jd.com/', timeout=15000, wait_until='domcontentloaded')
                page.wait_for_timeout(800)

                # 找搜索框
                for sel in ['#key', 'input#key', 'input.search-text']:
                    try:
                        inp = page.wait_for_selector(sel, timeout=2000)
                        inp.click(); inp.fill(kw); inp.press('Enter')
                        break
                    except Exception:
                        continue
                else:
                    print("❌ 找不到搜索框"); continue

                # 等待搜索API响应
                time.sleep(4)

                # 尝试从拦截的API中提取数据
                items = []
                for api_resp in search_api_responses:
                    items = parse_jd_api_response(api_resp['data'])
                    if items:
                        break

                # 如果API没抓到，尝试滚动DOM
                if not items:
                    for _ in range(5):
                        page.evaluate('window.scrollBy(0, 800)')
                        time.sleep(600)
                    time.sleep(1000)
                    html = page.content()
                    items = parse_jd_dom(html, kw)

                if items:
                    comp_prices = [to_per_kg(it['price'], it['spec']) for it in items]
                    avg_per_kg = sum(comp_prices) / len(comp_prices) if comp_prices else 0

                    if my_per_kg > 0 and avg_per_kg > 0:
                        diff_pct = (my_per_kg - avg_per_kg) / avg_per_kg * 100
                        if diff_pct < -20:   icon, pos = "🔵", f"偏低 {diff_pct:+.0f}%"
                        elif diff_pct > 20:  icon, pos = "🔴", f"偏高 {diff_pct:+.0f}%"
                        else:                icon, pos = "🟢", f"合理 {diff_pct:+.0f}%"
                    else:
                        icon, pos = "⚪", "无法对比规格"

                    print(f"✅ {len(items)}个 | 我店{spec_str} | 竞品均¥{avg_per_kg:.1f}/kg | {icon}{pos}")

                    all_results.append({
                        'wechat_title': title,
                        'wechat_price': my_price,
                        'wechat_spec': my_spec['raw'] if my_spec else '',
                        'wechat_per_kg': round(my_per_kg, 2),
                        'search_kw': kw,
                        'competitors': items,
                        'avg_per_kg': round(avg_per_kg, 2),
                        'price_position': pos,
                        'comp_count': len(items),
                    })
                else:
                    print("⚠️ 无数据")

                time.sleep(1)

            except Exception as e:
                print(f"❌ {e}")

        browser.close()

        out_path = 'competitor_analysis/jd_competitors_local.json'
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump({
                'crawled_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'source': 'wechat_products_normalized_v6',
                'total_products': len(wechat_products),
                'analyzed': all_results,
            }, f, ensure_ascii=False, indent=2)

        print(f"\n{'='*60}")
        print(f"✅ 完成！分析了 {len(all_results)} 个商品")
        print(f"   保存到: {out_path}")
        if all_results:
            print(f"\n{'商品':<20} {'本店价':>14} {'竞品均/kg':>10} {'定位':>12}")
            print(f"   {'-'*60}")
            for r in all_results:
                t = r['wechat_title'][:18]
                my = f"¥{r['wechat_price']:.0f}({r['wechat_spec'] or '份'})" if r['wechat_spec'] else f"¥{r['wechat_price']:.0f}"
                avg = f"¥{r['avg_per_kg']:.1f}/kg" if r['avg_per_kg'] > 0 else "未知"
                print(f"   {t:<20} {my:>14} {avg:>10} {r['price_position']:>12}")
        print(f"{'='*60}")


def parse_jd_api_response(data):
    """从JD搜索API JSON响应中提取商品数据"""
    items = []

    # JD搜索API常见结构
    # 遍历所有可能的字段
    def extract_from_obj(obj):
        if isinstance(obj, dict):
            # 找商品数据
            for key in ['products', 'product_list', 'items', 'result', 'goodsList', 'wareList']:
                if key in obj and isinstance(obj[key], list):
                    for p in obj[key]:
                        items.extend(extract_from_obj(p))
                        break
            # 商品字段
            title = obj.get('title') or obj.get('name') or obj.get('wareName', '')
            price = obj.get('price') or obj.get('salePrice') or obj.get('promotionPrice', 0)
            if title and price:
                spec = extract_spec(str(title))
                try:
                    price_f = float(price)
                    if price_f > 0:
                        items.append({'title': title[:80], 'price': price_f, 'spec': spec})
                except (ValueError, TypeError):
                    pass
            # 递归
            for v in obj.values():
                if isinstance(v, (dict, list)):
                    extract_from_obj(v)
        elif isinstance(obj, list):
            for item in obj:
                extract_from_obj(item)

    extract_from_obj(data)
    # 去重
    seen = set(); unique = []
    for it in items:
        key = (it['title'][:20], int(it['price']))
        if key not in seen and it['price'] > 0:
            seen.add(key); unique.append(it)
    return unique[:10]


def parse_jd_dom(html: str, kw: str):
    """从DOM HTML中提取商品数据（备用）"""
    items = []
    li_blocks = re.findall(r'<li[^>]+data-sku="(\d+)"[^>]*>(.*?)</li>', html, re.DOTALL)
    for sku, block in li_blocks[:12]:
        title_m = re.search(r'<em[^>]*>([^<]{3,80})</em>', block)
        price_m = re.search(r'<i[^>]*>([\d.]+)</i>', block)
        title = clean_html(title_m.group(1)) if title_m else ''
        try:
            price = float(price_m.group(1)) if price_m else 0
        except ValueError:
            price = 0
        if price > 0:
            spec = extract_spec(title)
            items.append({'sku': sku, 'title': title[:80], 'price': price, 'spec': spec})
    return items


def clean_html(text):
    return re.sub(r'<[^>]+>', '', text).strip()


if __name__ == '__main__':
    run()
