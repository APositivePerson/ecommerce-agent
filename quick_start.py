#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速上架示例 - 使用默认配置和交互式输入
"""
import sys
sys.path.insert(0, '/home/wangziyi/.openclaw/workspace/ecommerce_agent')

from main import WechatProductUploader

# 初始化上传器
uploader = WechatProductUploader('/home/wangziyi/.openclaw/workspace/ecommerce_agent/config.yaml')

# 图片文件夹路径
img_folder = '/home/wangziyi/桌面/上架商品图'

# 收集商品信息
print("=" * 50)
print("微信小店商品上架工具")
print("=" * 50)
print(f"图片文件夹: {img_folder}")
print("-" * 50)

product_info = {
    'title': input("请输入商品标题: ").strip(),
    'short_title': input("请输入商品短标题（可选，直接回车跳过）: ").strip() or None,
    'price': float(input("请输入商品价格（元）: ")),
    'stock': int(input("请输入库存数量: ")),
    'cat_id_1': int(input("请输入一级类目ID: ")),
    'cat_id_2': int(input("请输入二级类目ID: ")),
    'cat_id_3': int(input("请输入三级类目ID: ")),
}

# 可选字段
brand_id = input("请输入品牌ID（默认无品牌2100000000，直接回车跳过）: ").strip()
if brand_id:
    product_info['brand_id'] = brand_id

template_id = input("请输入运费模板ID（可选，直接回车跳过）: ").strip()
if template_id:
    product_info['template_id'] = template_id

weight = input("请输入商品重量（克，可选，直接回车跳过）: ").strip()
if weight:
    product_info['weight'] = int(weight)

listing = input("是否立即上架？1-是，0-否（默认0）: ").strip()
if listing:
    product_info['listing'] = int(listing)

# 上传商品
print("\n开始上传商品...")
print("-" * 50)

result = uploader.upload_product_from_folder(img_folder, product_info)

if result:
    print("\n" + "=" * 50)
    print("✅ 商品添加成功！")
    print(f"商品ID: {result.get('product_id')}")
    print(f"创建时间: {result.get('create_time')}")
    print("=" * 50)
else:
    print("\n" + "=" * 50)
    print("❌ 商品添加失败，请检查日志")
    print("=" * 50)
