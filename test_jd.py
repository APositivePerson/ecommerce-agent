#!/usr/bin/env python3
from playwright.sync_api import sync_playwright

JD_COOKIES = [
    {'name': '__jda', 'value': '181111935.17746064027131028945616.1774606403.1775020011.1775023794.7', 'domain': '.jd.com', 'path': '/'},
    {'name': '__jdb', 'value': '181111935.5.17746064027131028945616|7.1775023794', 'domain': '.jd.com', 'path': '/'},
    {'name': '__jdc', 'value': '181111935', 'domain': '.jd.com', 'path': '/'},
    {'name': '__jdu', 'value': '17746064027131028945616', 'domain': '.jd.com', 'path': '/'},
    {'name': '__jdv', 'value': '178324346|www.google.com|-|referral|-|1774606402713', 'domain': '.jd.com', 'path': '/'},
    {'name': '_pst', 'value': 'jd_KfxUghHQpPMK', 'domain': '.jd.com', 'path': '/'},
    {'name': '_tp', 'value': 'XqZmFh00R1lVjeFI3mGFdw%3D%3D', 'domain': '.jd.com', 'path': '/'},
    {'name': '3AB9D23F7A4B3C9B', 'value': 'YGHZYCMZ2EJ2XR3RSVZHRFE26MMUPDTMRILWIMPASJZMQYZJT3VR47TQIPBWD5O4AVOI3A5UQPF7PD6MO4XABNF7EQ', 'domain': '.jd.com', 'path': '/'},
    {'name': '3AB9D23F7A4B3CSS', 'value': 'jdd03YGHZYCMZ2EJ2XR3RSVZHRFE26MMUPDTMRILWIMPASJZMQYZJT3VR47TQIPBWD5O4AVOI3A5UQPF7PD6MO4XABNF7EQAAAAM5I6XEKRQAAAAADXRLUXYYKHNIBQX', 'domain': '.jd.com', 'path': '/'},
    {'name': 'shshshfpa', 'value': '845e995f-bb31-70c5-dfba-5e1c82d8c81c-1774607035', 'domain': '.jd.com', 'path': '/'},
    {'name': 'pin', 'value': 'jd_KfxUghHQpPMK', 'domain': '.jd.com', 'path': '/'},
    {'name': 'light_key', 'value': 'AASBKE7rOxgWQziEhC_QY6yaMZWW08n2tHtB-O6ym8WHSwwbMrdUd4JfiZHb8gtSVU9EwGxP', 'domain': '.jd.com', 'path': '/'},
]

KEYWORDS = ['猫粮', '猫砂', '猫罐头', '猫零食', '猫冻干', '猫条', '化毛膏', '猫窝']

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path='/usr/bin/google-chrome',
        headless=True,
        proxy={'server': 'socks5://127.0.0.1:7897'},
        args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-blink-features=AutomationControlled']
    )
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        locale='zh-CN',
        timezone_id='Asia/Shanghai',
    )
    context.add_cookies(JD_COOKIES)
    page = context.new_page()

    # 先去jd.com建立会话
    page.goto('https://www.jd.com/', timeout=15000)
    page.wait_for_timeout(2000)
    print(f'jd.com: {page.url}')

    all_results = []

    for kw in KEYWORDS:
        import urllib.parse
        encoded_kw = urllib.parse.quote(kw)
        search_url = f'https://search.jd.com/Search?keyword={encoded_kw}&enc=utf-8'

        page.goto(search_url, timeout=15000)
        page.wait_for_timeout(4000)

        text = page.inner_text('body')
        if 'login' in page.url.lower() or '登录' in text[:200]:
            print(f'[{kw}] ❌ 跳转到登录页，跳过')
            continue

        # 提取商品
        items = page.eval_on_selector_all(
            'li.gl-item',
            '''els => els.slice(0, 10).map(el => {
                const sku = el.getAttribute('data-sku') || '';
                const titleEl = el.querySelector('em');
                const priceEl = el.querySelector('.p-price i');
                const title = titleEl ? titleEl.innerText.trim() : '';
                const price = priceEl ? priceEl.innerText.replace(/[^0-9.]/g,'') : '0';
                return { sku, title: title.substring(0,60), price, keyword: arguments[0] };
            })''',
            kw
        )

        print(f'[{kw}] ✅ {len(items)} items')
        for item in items[:3]:
            print(f'    {item["title"][:40]} | ¥{item["price"]}')
        all_results.extend(items)

    browser.close()

    # 保存结果
    import json
    with open('competitor_analysis/jd_cookie_products.json', 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f'\n总共抓取: {len(all_results)} 条，保存到 jd_cookie_products.json')
