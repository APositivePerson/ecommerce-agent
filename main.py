#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信小店商品上架工具
支持从Excel读取商品信息并上传图片
"""
import os
import sys
import json
import logging
import requests
import yaml
from typing import Dict, List, Optional, Any
from upload_img import WechatImageUploader, find_main_images, find_detail_images

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WechatProductUploader:
    """微信小店商品上传器"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.uploader = WechatImageUploader(
            access_token=self.config['wechat']['access_token'],
            upload_url=self.config['wechat'].get('img_upload_url')
        )
    
    def _load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        if not os.path.exists(config_path):
            logger.error(f"配置文件不存在: {config_path}")
            sys.exit(1)
        
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def upload_product_images(self, base_path: str) -> Dict[str, List[str]]:
        """
        上传商品图片（主图和详情图）
        
        Args:
            base_path: 图片文件夹路径
            
        Returns:
            包含主图URL和详情图URL的字典
        """
        from upload_img import get_all_images_in_folder
        
        # 获取所有图片
        all_images = get_all_images_in_folder(base_path)
        
        main_img_paths = all_images.get('main', [])
        detail_img_paths = all_images.get('detail', [])
        
        # 如果没有找到主图，尝试用配置查找
        if not main_img_paths:
            img_config = self.config.get('images', {})
            main_config = img_config.get('main_img', {})
            main_img_paths = find_main_images(base_path, main_config)
        
        # 如果没有找到详情图，尝试用配置查找
        if not detail_img_paths:
            img_config = self.config.get('images', {})
            detail_config = img_config.get('detail_img', {})
            detail_prefix = detail_config.get('prefix', '详情图')
            detail_extensions = detail_config.get('extensions', ['', '.jpg', '.jpeg', '.png', '.webp'])
            detail_img_paths = find_detail_images(base_path, detail_prefix, detail_extensions)
        
        if not main_img_paths:
            logger.warning(f"未找到主图文件，路径: {base_path}")
        else:
            logger.info(f"找到 {len(main_img_paths)} 张主图: {[os.path.basename(p) for p in main_img_paths]}")
        
        if not detail_img_paths:
            logger.warning(f"未找到详情图文件，路径: {base_path}")
        else:
            logger.info(f"找到 {len(detail_img_paths)} 张详情图: {[os.path.basename(p) for p in detail_img_paths[:3]]}...")
        
        # 上传主图
        logger.info("开始上传主图...")
        main_img_urls = self.uploader.upload_images(main_img_paths)
        
        # 上传详情图
        logger.info("开始上传详情图...")
        detail_img_urls = self.uploader.upload_images(detail_img_paths)
        
        return {
            'head_imgs': main_img_urls,
            'detail_imgs': detail_img_urls
        }
    
    def build_product_data(self, product_info: Dict, img_urls: Dict[str, List[str]]) -> Dict:
        """
        构建商品数据
        
        Args:
            product_info: 商品基本信息
            img_urls: 图片URL字典
            
        Returns:
            完整的商品数据字典
        """
        defaults = self.config.get('defaults', {})
        
        # 构建商品数据
        data = {
            # 必填字段
            'title': product_info.get('title', ''),
            'head_imgs': img_urls.get('head_imgs', []),
            'deliver_method': product_info.get('deliver_method', defaults.get('deliver_method', 0)),
            'cats': [
                {'cat_id': int(product_info.get('cat_id_1', 0))},
                {'cat_id': int(product_info.get('cat_id_2', 0))},
                {'cat_id': int(product_info.get('cat_id_3', 0))}
            ],
            'cats_v2': [
                {'cat_id': int(product_info.get('cat_id_1', 0))},
                {'cat_id': int(product_info.get('cat_id_2', 0))},
                {'cat_id': int(product_info.get('cat_id_3', 0))}
            ],
            'extra_service': {
                'seven_day_return': int(product_info.get('seven_day_return', defaults.get('seven_day_return', 1))),
                'freight_insurance': int(product_info.get('freight_insurance', defaults.get('freight_insurance', 0))),
                'damage_guarantee': int(product_info.get('damage_guarantee', defaults.get('damage_guarantee', 0))),
                'fake_one_pay_three': int(product_info.get('fake_one_pay_three', defaults.get('fake_one_pay_three', 0))),
                'exchange_support': int(product_info.get('exchange_support', defaults.get('exchange_support', 0)))
            },
            'skus': [{
                'sale_price': int(float(product_info.get('price', 0)) * 100),  # 转换为分
                'stock_num': int(product_info.get('stock', 0))
            }],
            
            # 可选字段
            'short_title': product_info.get('short_title', ''),
            'brand_id': product_info.get('brand_id', defaults.get('brand_id', '2100000000')),
            'listing': int(product_info.get('listing', defaults.get('listing', 0))),
        }
        
        # 添加发货账号类型（deliver_method=3时）
        if data['deliver_method'] == 3:
            deliver_acct_type = product_info.get('deliver_acct_type', defaults.get('deliver_acct_type', [3]))
            if isinstance(deliver_acct_type, str):
                deliver_acct_type = [int(x.strip()) for x in deliver_acct_type.split(',')]
            data['deliver_acct_type'] = deliver_acct_type
        
        # 添加运费信息
        template_id = product_info.get('template_id')
        weight = product_info.get('weight')
        if template_id or weight:
            data['express_info'] = {}
            if template_id:
                data['express_info']['template_id'] = str(template_id)
            if weight:
                data['express_info']['weight'] = int(weight)
        
        # 添加商品详情
        detail_imgs = img_urls.get('detail_imgs', [])
        if detail_imgs:
            data['desc_info'] = {
                'imgs': detail_imgs,
                'desc': product_info.get('desc', '')
            }
        
        # 添加SKU编码（如果有）
        sku_code = product_info.get('sku_code')
        if sku_code:
            data['skus'][0]['sku_code'] = str(sku_code)
        
        # 添加商家编码（如果有）
        spu_code = product_info.get('spu_code')
        if spu_code:
            data['spu_code'] = str(spu_code)
        
        # 添加商家自定义ID（如果有）
        out_product_id = product_info.get('out_product_id')
        if out_product_id:
            data['out_product_id'] = str(out_product_id)
        
        # 添加SKU自定义ID（如果有）
        out_sku_id = product_info.get('out_sku_id')
        if out_sku_id:
            data['skus'][0]['out_sku_id'] = str(out_sku_id)
        
        return data
    
    def add_product(self, product_data: Dict) -> Optional[Dict]:
        """
        调用微信小店API添加商品
        
        Args:
            product_data: 商品数据
            
        Returns:
            API响应结果
        """
        url = f"{self.config['wechat']['product_add_url']}?access_token={self.config['wechat']['access_token']}"
        
        try:
            headers = {'Content-Type': 'application/json'}
            response = requests.post(url, headers=headers, json=product_data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('errcode') == 0:
                logger.info(f"商品添加成功: {result}")
                return result.get('data')
            else:
                logger.error(f"商品添加失败: {result.get('errmsg')} (errcode: {result.get('errcode')})")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求异常: {e}")
            return None
        except Exception as e:
            logger.error(f"添加商品时发生错误: {e}")
            return None
    
    def upload_product_from_folder(self, img_folder: str, product_info: Dict = None) -> Optional[Dict]:
        """
        从图片文件夹上传商品
        
        Args:
            img_folder: 图片文件夹路径
            product_info: 商品基本信息（可选）
            
        Returns:
            API响应结果
        """
        if not os.path.exists(img_folder):
            logger.error(f"图片文件夹不存在: {img_folder}")
            return None
        
        # 上传图片
        logger.info(f"开始处理文件夹: {img_folder}")
        img_urls = self.upload_product_images(img_folder)
        
        # 检查主图数量
        head_imgs = img_urls.get('head_imgs', [])
        min_main_imgs = 3  # 默认最少3张，食品饮料和生鲜类目需要4张
        if len(head_imgs) < min_main_imgs:
            logger.error(f"主图数量不足，至少需要{min_main_imgs}张，当前只有 {len(head_imgs)} 张")
            logger.error(f"请将更多主图放入文件夹，或使用 '主图1', '主图2' 等命名方式")
            return None
        
        # 检查详情图数量
        detail_imgs = img_urls.get('detail_imgs', [])
        min_detail_imgs = 1  # 默认最少1张，食品饮料和生鲜类目需要3张
        if len(detail_imgs) < min_detail_imgs:
            logger.error(f"详情图数量不足，至少需要{min_detail_imgs}张，当前只有 {len(detail_imgs)} 张")
            return None
        
        # 构建商品数据
        if product_info is None:
            # 如果没有提供商品信息，使用默认值
            product_info = {
                'title': input("请输入商品标题: "),
                'price': float(input("请输入商品价格（元）: ")),
                'stock': int(input("请输入库存数量: ")),
                'cat_id_1': int(input("请输入一级类目ID: ")),
                'cat_id_2': int(input("请输入二级类目ID: ")),
                'cat_id_3': int(input("请输入三级类目ID: ")),
            }
        
        product_data = self.build_product_data(product_info, img_urls)
        
        # 打印商品数据（用于调试）
        logger.info("商品数据:")
        logger.info(json.dumps(product_data, ensure_ascii=False, indent=2))
        
        # 调用API添加商品
        return self.add_product(product_data)


def main():
    """主函数"""
    # 初始化上传器
    uploader = WechatProductUploader()
    
    # 图片文件夹路径
    img_folder = uploader.config.get('images', {}).get('base_path', '/home/wangziyi/桌面/上架商品图')
    
    # 收集商品信息
    print("=" * 50)
    print("微信小店商品上架工具")
    print("=" * 50)
    
    product_info = {
        'title': input("请输入商品标题: ").strip(),
        'short_title': input("请输入商品短标题（可选）: ").strip() or None,
        'price': float(input("请输入商品价格（元）: ")),
        'stock': int(input("请输入库存数量: ")),
        'cat_id_1': int(input("请输入一级类目ID: ")),
        'cat_id_2': int(input("请输入二级类目ID: ")),
        'cat_id_3': int(input("请输入三级类目ID: ")),
    }
    
    # 可选字段
    brand_id = input("请输入品牌ID（默认无品牌2100000000）: ").strip()
    if brand_id:
        product_info['brand_id'] = brand_id
    
    template_id = input("请输入运费模板ID（可选）: ").strip()
    if template_id:
        product_info['template_id'] = template_id
    
    weight = input("请输入商品重量（克，可选）: ").strip()
    if weight:
        product_info['weight'] = int(weight)
    
    listing = input("是否立即上架？1-是，0-否（默认0）: ").strip()
    if listing:
        product_info['listing'] = int(listing)
    
    # 上传商品
    print("\n开始上传商品...")
    result = uploader.upload_product_from_folder(img_folder, product_info)
    
    if result:
        print(f"\n✅ 商品添加成功！")
        print(f"商品ID: {result.get('product_id')}")
        print(f"创建时间: {result.get('create_time')}")
    else:
        print("\n❌ 商品添加失败，请检查日志")


if __name__ == '__main__':
    main()
