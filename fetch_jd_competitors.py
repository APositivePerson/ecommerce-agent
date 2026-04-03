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
    """从标题中提取品类关键词，优先最长匹配。"""
    # 品类词表
    CATS = [
        '原矿猫砂', '豆腐猫砂', '混合猫砂', '钠基猫砂', '矿晶猫砂',
        '幼猫粮', '成猫粮', '风干粮', '宠物牙膏',
        '猫粮', '狗粮', '猫砂', '猫罐头', '猫零食', '猫冻干', '猫条',
        '猫湿粮', '化毛膏', '营养膏', '鸡肉味', '三文鱼味', '牛肉味',
        '除口臭', '洁牙', '膨润土', '冻干', '羊奶粉', '奶糕',
    ]
    title_clean = re.sub(r'[\d.]+\s*(?:kg|g|ml|lb|升|毫升|克|公斤)', '', title, flags=re.I)
    title_clean = re.sub(r'[（(].*?[）)]', '', title_clean)
    # 找所有匹配的品类词，返回最长的那个
    matches = [(kw, len(kw)) for kw in CATS if kw in title_clean]
    if matches:
        return max(matches, key=lambda x: x[1])[0]
    return title_clean[:8].strip()


def _jd_search_via_page(page, kw: str) -> tuple:
    """在已登录的 Playwright page 上搜索，返回商品列表。"""
    try:
        # 回到京东首页（站内导航，避免触发安全检测）
        page.goto('https://www.jd.com/', timeout=20000)
        page.wait_for_timeout(2000)

        # DEBUG: 打印页面里所有 input 元素信息
        input_debug = page.evaluate("""
            () => {
                const inputs = Array.from(document.querySelectorAll('input'))
                    .slice(0, 10)
                    .map(el => el.id + '|' + el.className.substring(0,30) + '|' + el.placeholder);
                return inputs.join(' || ');
            }
        """)
        print(f"\n    [DEBUG] 页面input元素: {input_debug}")
        print(f"    [DEBUG] 页面title: {page.title()}")

        # 搜索框选择器（更多兼容）
        search_selectors = [
            '#key', 'input#key', '#searchKey', 'input.search-key',
            '[placeholder*="搜索"]', '[placeholder*="search" i]',
            '.key', 'input[class*="key"]', 'input[class*="search"]'
        ]
        found_sel = None
        for sel in search_selectors:
            try:
                inp = page.wait_for_selector(sel, timeout=2000)
                if inp:
                    found_sel = sel
                    inp.click()
                    inp.fill(kw)
                    inp.press('Enter')
                    print(f"    [DEBUG] 搜索框找到: {sel}")
                    break
            except Exception:
                continue

        if not found_sel:
            return [], '找不到搜索框'

        page.wait_for_timeout(4000)

        # 等商品列表出现
        try:
            page.wait_for_selector('#J_goodsList li, .gl-item, li[data-sku]', timeout=8000)
        except Exception:
            pass
        page.wait_for_timeout(2000)

        html = page.content()
        items = []

        # DEBUG: 打印页面状态
        print(f"\n    [DEBUG] title={page.title()[:40]} html_len={len(html)}")
        # 打印HTML里是否有"验证"相关内容
        has_captcha = '验证' in html or 'captcha' in html.lower() or 'security' in html.lower()
        print(f"    [DEBUG] 包含验证码相关内容: {has_captcha}")
        print(f"    [DEBUG] HTML前300字: {html[:300]}")
        li_count = len(page.query_selector_all('#J_goodsList li'))
        gl_count = len(page.query_selector_all('.gl-item'))
        print(f"    [DEBUG] #J_goodsList li={li_count} .gl-item={gl_count}")

        # 方法0: 直接 JS 查询 DOM（最可靠）
        raw_items_js = page.evaluate("""
            () => {
                const results = [];
                const selectors = ['#J_goodsList li', '.gl-item', 'li[data-sku]', "[class*='goods-list'] li"];
                let lis = [];
                for (const s of selectors) {
                    lis = document.querySelectorAll(s);
                    if (lis.length > 0) break;
                }
                lis.forEach((li, i) => {
                    if (i >= 20) return;
                    let title = '', price = 0, comment = 0;
                    const titleEl = li.querySelector('.p-name em, [class*="name"] em, a[title]');
                    const priceEl = li.querySelector('.p-price i, [class*="price"]');
                    const cEl = li.querySelector('.p-commit a');
                    if (titleEl) title = titleEl.innerText.replace(/<[^>]+>/g, '').trim();
                    if (priceEl) {
                        const m = priceEl.innerText.match(/[\\d.]+/);
                        if (m) price = parseFloat(m[0]);
                    }
                    if (cEl) {
                        const ct = cEl.innerText;
                        const m = ct.match(/([\\d.]+)/);
                        if (m) {
                            comment = parseFloat(m[1]);
                            if (ct.includes('万')) comment *= 10000;
                            else if (ct.includes('千')) comment *= 1000;
                        }
                    }
                    if (price > 0) results.push({ title: title.substring(0,60), price, comment });
                });
                return results;
            }
        """)
        print(f"    [DEBUG] JS DOM提取: {len(raw_items_js)} 个")
        for ri in raw_items_js[:3]:
            items.append({'title': ri['title'], 'price': ri['price'],
                          'comment_count': int(ri.get('comment') or 0), 'spec': extract_spec(ri['title'])})

        # 方法1: script 内嵌 JSON（多种正则兼容）
        json_patterns = [
            r'search_jd_com\.[^\n<]{0,200}\s*=\s*({.{0,30000})',
            r'"wareList":\s*(\[.{0,20000})',
            r'"goodsList":\s*(\[.{0,20000})',
            r'"products":\s*(\[.{0,20000})',
        ]
        json_blocks = []
        for pat in json_patterns:
            found = re.findall(pat, html)
            json_blocks.extend(found)
        print(f"    [DEBUG] JSON blocks found: {len(json_blocks)}")

        for block in json_blocks[:2]:
            try:
                block = block.strip().rstrip(';')
                data = json.loads(block)
                prods = (data.get('result') or {}).get('products', [])
                if not prods:
                    prods = data.get('wareList', []) or data.get('goodsList', []) or []
                for p in prods[:20]:
                    title = p.get('name', '') or p.get('title', '') or p.get('wareName', '')
                    price = float(p.get('price', 0) or p.get('salePrice', 0) or 0)
                    cnt = int(str(p.get('commentCount', 0)).replace(',', '') or 0)
                    if price > 0 and title:
                        items.append({
                            'title': title[:80], 'price': price,
                            'comment_count': cnt, 'spec': extract_spec(title)
                        })
            except (json.JSONDecodeError, ValueError, KeyError, TypeError):
                pass

        # 方法2: DOM 正则
        if len(items) < 3:
            li_blocks = re.findall(r'<li[^>]+data-sku="(\d+)"[^>]*>(.*?)</li>', html, re.DOTALL)
            for sku, block in li_blocks[:15]:
                title_m = re.search(r'<em[^>]*>([^<]{3,80})</em>', block)
                price_m = re.search(r'<i[^>]*>([\d.]+)</i>', block)
                cnt_m = re.search(r'<a[^>]+class="[^"]*p-commit[^"]*"[^>]*>([^<]{0,30})</a>', block)
                title = clean_html(title_m.group(1)) if title_m else ''
                try:
                    price = float(price_m.group(1)) if price_m else 0
                except ValueError:
                    price = 0
                cnt = 0
                if cnt_m:
                    m = re.search(r'([\d.]+)', cnt_m.group(1))
                    if m:
                        cnt = int(float(m.group(1)) * (10000 if '万' in cnt_m.group(1) else 1))
                if price > 0:
                    items.append({
                        'title': title[:80], 'price': price,
                        'comment_count': cnt, 'spec': extract_spec(title)
                    })

        # 去重
        seen, unique = set(), []
        for item in items:
            key = (int(item['price'] * 10), item['title'][:10])
            if key not in seen and item['price'] > 0:
                seen.add(key); unique.append(item)
        return unique[:15], ''

    except Exception as e:
        return [], str(e)


def run():
    from playwright.sync_api import sync_playwright

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

        page.goto('https://www.jd.com/', timeout=30000, wait_until='domcontentloaded')
        page.wait_for_timeout(2000)

        try:
            page.wait_for_selector('.nickname', timeout=3000)
            print("✅ 已登录\n")
        except Exception:
            print("⚠️ 请扫码登录京东（5分钟内扫完即可）...\n")
            try:
                page.wait_for_selector('.nickname', timeout=300000)
                print("✅ 登录成功\n")
            except Exception:
                print("❌ 扫码超时\n")
                return

        # 逐个关键词搜索（全程在 Playwright 里进行）
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

            items, err = _jd_search_via_page(page, kw)

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

                comments = [c.get('comment_count', 0) for c in items if c.get('comment_count')]
                avg_cmt = sum(comments)//len(comments) if comments else 0
                avg_cmt_str = f"{avg_cmt//10000:.1f}万" if avg_cmt >= 10000 else str(avg_cmt)

                print(f"✅ {len(items)}个 | 我店{spec_str} | 竞品均¥{avg_per_kg:.1f}/kg | 评价{avg_cmt_str} | {icon}{pos}")

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
                print(f"⚠️ 无数据" + (f" | {err[:50]}" if err else ""))

            time.sleep(2)

        browser.close()

    out_path = 'competitor_analysis/jd_competitors_local.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({
            'crawled_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'source': 'wechat_products_normalized_v6',
            'total_products': len(wechat_products),
            'analyzed': all_results,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*65}")
    print(f"✅ 完成！分析了 {len(all_results)} 个商品")
    print(f"   保存到: {out_path}")
    if all_results:
        print(f"\n{'商品':<18} {'本店价':>10} {'竞品均/kg':>10} {'评价均值':>10} {'定位':>8}")
        print(f"   {'-'*62}")
        for r in all_results:
            t = r['wechat_title'][:16]
            my = f"¥{r['wechat_price']:.0f}({r['wechat_spec'] or '份'})" if r['wechat_spec'] else f"¥{r['wechat_price']:.0f}"
            avg = f"¥{r['avg_per_kg']:.1f}/kg" if r['avg_per_kg'] > 0 else "未知"
            comments = [c.get('comment_count', 0) for c in r['competitors'] if c.get('comment_count')]
            avg_c = sum(comments)//len(comments) if comments else 0
            avg_c_str = f"{avg_c//10000:.1f}万" if avg_c >= 10000 else str(avg_c)
            print(f"   {t:<18} {my:>10} {avg:>10} {avg_c_str:>10} {r['price_position']:>8}")
    print(f"{'='*65}")


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
                        # 提取评价数
                        raw_cnt = obj.get('commentCount', 0) or obj.get('comments', 0) or 0
                        try:
                            comment_count = int(str(raw_cnt).replace(',', ''))
                        except (ValueError, TypeError):
                            comment_count = 0
                        items.append({'title': title[:80], 'price': price_f, 'spec': spec, 'comment_count': comment_count})
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
