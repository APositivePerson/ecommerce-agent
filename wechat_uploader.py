# -*- coding: utf-8 -*-
"""
微信小店AI上架助手 - 智能版
支持自动识别商品类目并上架到微信小店
"""
import requests
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional


class SmartWechatUploader:
    """微信小店智能上架助手"""
    
    # 智能类目映射表
    CATEGORY_RULES = {
        # 猫粮类
        "猫粮": {"cats": [{"cat_id": "1208"}, {"cat_id": "1209"}, {"cat_id": "1215"}], "attrs": [
            {"attr_key": "产品产地", "attr_value": "国产"},
            {"attr_key": "保质期(天/月/年)", "attr_value": "18个月"},
            {"attr_key": "配方", "attr_value": "膨化粮"},
            {"attr_key": "净含量（kg）", "attr_value": "2kg"}
        ]},
        "成猫粮": {"cats": [{"cat_id": "1208"}, {"cat_id": "1209"}, {"cat_id": "1215"}], "attrs": [
            {"attr_key": "产品产地", "attr_value": "国产"},
            {"attr_key": "保质期(天/月/年)", "attr_value": "18个月"},
            {"attr_key": "配方", "attr_value": "膨化粮"},
            {"attr_key": "净含量（kg）", "attr_value": "2kg"}
        ]},
        "幼猫粮": {"cats": [{"cat_id": "1208"}, {"cat_id": "1209"}, {"cat_id": "1215"}], "attrs": [
            {"attr_key": "产品产地", "attr_value": "国产"},
            {"attr_key": "保质期(天/月/年)", "attr_value": "18个月"},
            {"attr_key": "配方", "attr_value": "幼猫粮"},
            {"attr_key": "净含量（kg）", "attr_value": "2kg"}
        ]},
        
        # 狗粮类
        "狗粮": {"cats": [{"cat_id": "1208"}, {"cat_id": "1210"}, {"cat_id": "1212"}], "attrs": [
            {"attr_key": "产品产地", "attr_value": "国产"},
            {"attr_key": "保质期(天/月/年)", "attr_value": "18个月"},
            {"attr_key": "配方", "attr_value": "膨化粮"},
            {"attr_key": "净含量（kg）", "attr_value": "2kg"}
        ]},
        
        # 猫零食类
        "猫零食": {"cats": [{"cat_id": "1208"}, {"cat_id": "1216"}, {"cat_id": "1218"}], "attrs": [
            {"attr_key": "产品产地", "attr_value": "国产"},
            {"attr_key": "净含量（kg）", "attr_value": "0.1kg"},
            {"attr_key": "保质期(天/月/年)", "attr_value": "24个月"},
            {"attr_key": "猫零食种类", "attr_value": "其他"},
            {"attr_key": "包装方式", "attr_value": "袋装"},
            {"attr_key": "使用阶段", "attr_value": "全期"}
        ]},
        "猫条": {"cats": [{"cat_id": "1208"}, {"cat_id": "1216"}, {"cat_id": "1218"}], "attrs": [
            {"attr_key": "产品产地", "attr_value": "国产"},
            {"attr_key": "净含量（kg）", "attr_value": "0.05kg"},
            {"attr_key": "保质期(天/月/年)", "attr_value": "18个月"},
            {"attr_key": "猫零食种类", "attr_value": "猫条"},
            {"attr_key": "包装方式", "attr_value": "袋装"},
            {"attr_key": "使用阶段", "attr_value": "全期"}
        ]},
        "猫罐头": {"cats": [{"cat_id": "1208"}, {"cat_id": "1216"}, {"cat_id": "1218"}], "attrs": [
            {"attr_key": "产品产地", "attr_value": "国产"},
            {"attr_key": "净含量（kg）", "attr_value": "0.085kg"},
            {"attr_key": "保质期(天/月/年)", "attr_value": "24个月"},
            {"attr_key": "猫零食种类", "attr_value": "罐头/湿粮包"},
            {"attr_key": "包装方式", "attr_value": "罐装"},
            {"attr_key": "使用阶段", "attr_value": "全期"}
        ]},
        "罐头": {"cats": [{"cat_id": "1208"}, {"cat_id": "1216"}, {"cat_id": "1218"}], "attrs": [
            {"attr_key": "产品产地", "attr_value": "国产"},
            {"attr_key": "净含量（kg）", "attr_value": "0.085kg"},
            {"attr_key": "保质期(天/月/年)", "attr_value": "24个月"},
            {"attr_key": "猫零食种类", "attr_value": "罐头/湿粮包"},
            {"attr_key": "包装方式", "attr_value": "罐装"},
            {"attr_key": "使用阶段", "attr_value": "全期"}
        ]},
        "冻干": {"cats": [{"cat_id": "1208"}, {"cat_id": "1216"}, {"cat_id": "1218"}], "attrs": [
            {"attr_key": "产品产地", "attr_value": "国产"},
            {"attr_key": "净含量（kg）", "attr_value": "0.05kg"},
            {"attr_key": "保质期(天/月/年)", "attr_value": "24个月"},
            {"attr_key": "猫零食种类", "attr_value": "冻干"},
            {"attr_key": "包装方式", "attr_value": "袋装"},
            {"attr_key": "使用阶段", "attr_value": "全期"}
        ]},
        "K9": {"cats": [{"cat_id": "1208"}, {"cat_id": "1216"}, {"cat_id": "1218"}], "attrs": [
            {"attr_key": "产品产地", "attr_value": "进口"},
            {"attr_key": "净含量（kg）", "attr_value": "0.085kg"},
            {"attr_key": "保质期(天/月/年)", "attr_value": "24个月"},
            {"attr_key": "猫零食种类", "attr_value": "冻干"},
            {"attr_key": "包装方式", "attr_value": "罐装"},
            {"attr_key": "使用阶段", "attr_value": "全期"}
        ]},
        
        # 狗零食类
        "狗零食": {"cats": [{"cat_id": "1208"}, {"cat_id": "1217"}, {"cat_id": "1218"}], "attrs": [
            {"attr_key": "产品产地", "attr_value": "国产"},
            {"attr_key": "净含量（kg）", "attr_value": "0.1kg"},
            {"attr_key": "保质期(天/月/年)", "attr_value": "18个月"},
            {"attr_key": "包装方式", "attr_value": "袋装"}
        ]},
        
        # 猫砂类
        "猫砂": {"cats": [{"cat_id": "1208"}, {"cat_id": "1231"}, {"cat_id": "1238"}], "attrs": [
            {"attr_key": "产品产地", "attr_value": "国产"},
            {"attr_key": "产品净重（kg）", "attr_value": "2.5kg"},
            {"attr_key": "材质", "attr_value": "混合"}
        ]},
        "豆腐猫砂": {"cats": [{"cat_id": "1208"}, {"cat_id": "1231"}, {"cat_id": "1238"}], "attrs": [
            {"attr_key": "产品产地", "attr_value": "国产"},
            {"attr_key": "产品净重（kg）", "attr_value": "2.5kg"},
            {"attr_key": "材质", "attr_value": "豆腐"}
        ]},
        "混合猫砂": {"cats": [{"cat_id": "1208"}, {"cat_id": "1231"}, {"cat_id": "1238"}], "attrs": [
            {"attr_key": "产品产地", "attr_value": "国产"},
            {"attr_key": "产品净重（kg）", "attr_value": "2.5kg"},
            {"attr_key": "材质", "attr_value": "混合"}
        ]},
        
        # 宠物营养膏/保健品类
        "营养膏": {"cats": [{"cat_id": "1208"}, {"cat_id": "378042"}, {"cat_id": "378044"}], "attrs": [
            {"attr_key": "产品产地", "attr_value": "国产"},
            {"attr_key": "产品净重（kg）", "attr_value": "0.06kg"},
            {"attr_key": "保质期(天/月/年)", "attr_value": "24个月"},
            {"attr_key": "主要功能成分", "attr_value": "营养膏"},
            {"attr_key": "包装方式", "attr_value": "盒装"}
        ]},
        "化毛膏": {"cats": [{"cat_id": "1208"}, {"cat_id": "378042"}, {"cat_id": "378044"}], "attrs": [
            {"attr_key": "产品产地", "attr_value": "国产"},
            {"attr_key": "产品净重（kg）", "attr_value": "0.12kg"},
            {"attr_key": "保质期(天/月/年)", "attr_value": "24个月"},
            {"attr_key": "主要功能成分", "attr_value": "营养膏"},
            {"attr_key": "包装方式", "attr_value": "盒装"}
        ]},
        "洗耳液": {"cats": [{"cat_id": "1208"}, {"cat_id": "378042"}, {"cat_id": "378044"}], "attrs": [
            {"attr_key": "产品产地", "attr_value": "国产"},
            {"attr_key": "产品净重（kg）", "attr_value": "0.06kg"},
            {"attr_key": "保质期(天/月/年)", "attr_value": "24个月"},
            {"attr_key": "主要功能成分", "attr_value": "营养膏"},
            {"attr_key": "包装方式", "attr_value": "盒装"}
        ]},
        "耳部护理": {"cats": [{"cat_id": "1208"}, {"cat_id": "378042"}, {"cat_id": "378044"}], "attrs": [
            {"attr_key": "产品产地", "attr_value": "国产"},
            {"attr_key": "产品净重（kg）", "attr_value": "0.06kg"},
            {"attr_key": "保质期(天/月/年)", "attr_value": "24个月"},
            {"attr_key": "主要功能成分", "attr_value": "营养膏"},
            {"attr_key": "包装方式", "attr_value": "盒装"}
        ]},
        "保健品": {"cats": [{"cat_id": "1208"}, {"cat_id": "378042"}, {"cat_id": "378044"}], "attrs": [
            {"attr_key": "产品产地", "attr_value": "国产"},
            {"attr_key": "产品净重（kg）", "attr_value": "0.1kg"},
            {"attr_key": "保质期(天/月/年)", "attr_value": "24个月"},
            {"attr_key": "主要功能成分", "attr_value": "营养膏"},
            {"attr_key": "包装方式", "attr_value": "盒装"}
        ]},
        
        # 宠物药品/驱虫类
        "驱虫": {"cats": [{"cat_id": "1208"}, {"cat_id": "378042"}, {"cat_id": "378044"}], "attrs": [
            {"attr_key": "产品产地", "attr_value": "国产"},
            {"attr_key": "产品净重（kg）", "attr_value": "0.01kg"},
            {"attr_key": "保质期(天/月/年)", "attr_value": "24个月"},
            {"attr_key": "主要功能成分", "attr_value": "营养膏"},
            {"attr_key": "包装方式", "attr_value": "盒装"}
        ]},
        "体外驱虫": {"cats": [{"cat_id": "1208"}, {"cat_id": "378042"}, {"cat_id": "378044"}], "attrs": [
            {"attr_key": "产品产地", "attr_value": "国产"},
            {"attr_key": "产品净重（kg）", "attr_value": "0.01kg"},
            {"attr_key": "保质期(天/月/年)", "attr_value": "24个月"},
            {"attr_key": "主要功能成分", "attr_value": "营养膏"},
            {"attr_key": "包装方式", "attr_value": "盒装"}
        ]},
        
        # 宠物清洁用品
        "清洁用品": {"cats": [{"cat_id": "1208"}, {"cat_id": "378042"}, {"cat_id": "378044"}], "attrs": [
            {"attr_key": "产品产地", "attr_value": "国产"},
            {"attr_key": "产品净重（kg）", "attr_value": "0.2kg"},
            {"attr_key": "保质期(天/月/年)", "attr_value": "24个月"},
            {"attr_key": "包装方式", "attr_value": "瓶装"}
        ]},
        "沐浴": {"cats": [{"cat_id": "1208"}, {"cat_id": "378042"}, {"cat_id": "378044"}], "attrs": [
            {"attr_key": "产品产地", "attr_value": "国产"},
            {"attr_key": "产品净重（kg）", "attr_value": "0.2kg"},
            {"attr_key": "保质期(天/月/年)", "attr_value": "24个月"},
            {"attr_key": "包装方式", "attr_value": "瓶装"}
        ]},
    }
    
    # 默认类目（营养膏）
    DEFAULT_CATEGORY = {
        "cats": [{"cat_id": "1208"}, {"cat_id": "378042"}, {"cat_id": "378044"}],
        "attrs": [
            {"attr_key": "产品产地", "attr_value": "国产"},
            {"attr_key": "产品净重（kg）", "attr_value": "0.1kg"},
            {"attr_key": "保质期(天/月/年)", "attr_value": "24个月"},
            {"attr_key": "主要功能成分", "attr_value": "营养膏"},
            {"attr_key": "包装方式", "attr_value": "盒装"}
        ]
    }
    
    def __init__(self, appid: str = None, secret: str = None):
        self.appid = appid or "wx304ca87183801402"
        self.secret = secret or "d9560ed4c2782016fcccef4c3f009d9a"
        self.access_token = None
        self.token_expire_time = None
        self._template_config = None
    
    def _get_access_token(self) -> str:
        """获取access_token，带缓存"""
        if self.access_token and self.token_expire_time and datetime.now() < self.token_expire_time:
            return self.access_token
        
        url = f"https://api.weixin.qq.com/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": self.appid,
            "secret": self.secret
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if "access_token" in data:
                self.access_token = data["access_token"]
                expires_in = data.get("expires_in", 7200)
                self.token_expire_time = datetime.now() + timedelta(seconds=expires_in - 300)
                return self.access_token
            else:
                raise Exception(f"获取token失败: {data.get('errmsg', '未知错误')}")
        except Exception as e:
            raise Exception(f"获取access_token失败: {str(e)}")
    
    def get_template_config(self) -> Dict:
        """获取店铺配置模板"""
        if self._template_config:
            return self._template_config
        
        token = self._get_access_token()
        
        product_ids = ["10000538928235", "10000546265236", "10000546519816"]
        
        for product_id in product_ids:
            try:
                url = f"https://api.weixin.qq.com/channels/ec/product/get?access_token={token}"
                resp = requests.post(url, json={"product_id": product_id}, timeout=30)
                result = resp.json()
                
                if result.get("errcode") == 0:
                    p = result.get("product", {})
                    self._template_config = {
                        "express_info": p.get("express_info", {}),
                        "extra_service": p.get("extra_service", {}),
                        "after_sale_info": p.get("after_sale_info", {}),
                        "product_qua_infos": p.get("product_qua_infos", []),
                        "head_imgs": p.get("head_imgs", []),
                        "desc_info_imgs": p.get("desc_info", {}).get("imgs", []),
                    }
                    return self._template_config
            except:
                continue
        
        raise Exception("无法获取店铺配置模板")
    
    def _analyze_category(self, product_name: str) -> Dict:
        """
        智能分析商品名称，返回类目配置
        
        Args:
            product_name: 商品名称
            
        Returns:
            类目配置字典
        """
        name_lower = product_name.lower()
        
        # 匹配规则
        for keyword, category_config in self.CATEGORY_RULES.items():
            if keyword.lower() in name_lower or keyword in product_name:
                # 根据商品名称动态调整属性
                attrs = category_config["attrs"].copy()
                
                # 尝试从名称中提取重量
                weight_match = re.search(r'(\d+\.?\d*)\s*(kg|g|斤|公斤)', name_lower)
                if weight_match:
                    weight_value = float(weight_match.group(1))
                    unit = weight_match.group(2)
                    # 转换为kg
                    if unit == 'g':
                        weight_value = weight_value / 1000
                    elif unit == '斤':
                        weight_value = weight_value / 2
                    weight_str = f"{weight_value:.2f}kg"
                    
                    # 更新重量属性
                    for attr in attrs:
                        if "净重" in attr.get("attr_key", ""):
                            attr["attr_value"] = weight_str
                
                return {
                    "cats": category_config["cats"],
                    "attrs": attrs
                }
        
        # 返回默认类目
        return self.DEFAULT_CATEGORY.copy()
    
    def smart_create_and_list(self, product_info: Dict) -> Dict:
        """
        智能创建并上架商品
        
        Args:
            product_info: 商品信息，包含:
                - name: 商品名称 (必填)
                - price: 售价，元 (必填)
                - original_price: 原价，元 (可选)
                - stock: 库存 (可选)
                - sku_code: SKU编码 (可选)
                
        Returns:
            上架结果
        """
        # 智能分析类目
        category_info = self._analyze_category(product_info.get("name", ""))
        
        # 获取店铺配置
        config = self.get_template_config()
        
        # 价格转换
        sale_price = int(product_info.get("price", 0) * 100)
        original_price = product_info.get("original_price")
        market_price = int((original_price or product_info.get("price", 0) * 1.5) * 100)
        
        # 构建商品数据
        product_data = {
            "title": product_info.get("name", ""),
            "cats": category_info["cats"],
            "skus": [{
                "sale_price": sale_price,
                "market_price": market_price,
                "stock_num": product_info.get("stock", 100),
                "sku_code": product_info.get("sku_code", product_info.get("name", "")[:20])
            }],
            "head_imgs": config.get("head_imgs", [])[:5],
            "info_img": config.get("desc_info_imgs", [])[:10],
            "desc_info": {"imgs": config.get("desc_info_imgs", [])[:10]},
            "attrs": category_info["attrs"],
            "express_info": config.get("express_info", {}),
            "extra_service": config.get("extra_service", {"seven_day_return": 1}),
            "after_sale_info": config.get("after_sale_info", {}),
            "product_qua_infos": config.get("product_qua_infos", []),
        }
        
        # 调用创建API
        token = self._get_access_token()
        url = f"https://api.weixin.qq.com/channels/ec/product/add?access_token={token}"
        
        try:
            resp = requests.post(url, json=product_data, timeout=30)
            result = resp.json()
            
            if result.get("errcode") != 0:
                return {
                    "success": False,
                    "step": "create",
                    "message": result.get("errmsg", "创建失败"),
                    "details": result
                }
            
            product_id = result.get("data", {}).get("product_id")
            
            # 上架商品
            import time
            time.sleep(2)
            
            listing_url = f"https://api.weixin.qq.com/channels/ec/product/listing?access_token={token}"
            resp2 = requests.post(listing_url, json={"product_id": product_id}, timeout=30)
            listing_result = resp2.json()
            
            # 如果审核中，等待后重试
            if listing_result.get("errcode") == 10020049:
                time.sleep(10)
                resp2 = requests.post(listing_url, json={"product_id": product_id}, timeout=30)
                listing_result = resp2.json()
            
            if listing_result.get("errcode") == 0:
                return {
                    "success": True,
                    "product_id": product_id,
                    "category": category_info["cats"],
                    "message": "上架成功"
                }
            else:
                return {
                    "success": True,
                    "product_id": product_id,
                    "category": category_info["cats"],
                    "message": f"创建成功，上架: {listing_result.get('errmsg', '待审核')}",
                    "listing_result": listing_result
                }
                
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def get_product_status(self, product_id: str) -> Dict:
        """获取商品状态"""
        token = self._get_access_token()
        url = f"https://api.weixin.qq.com/channels/ec/product/get?access_token={token}"
        
        try:
            resp = requests.post(url, json={"product_id": product_id}, timeout=30)
            result = resp.json()
            
            if result.get("errcode") == 0:
                p = result.get("product", {})
                return {
                    "errcode": 0,
                    "product_id": p.get("product_id"),
                    "title": p.get("title"),
                    "status": p.get("status"),
                    "min_price": p.get("min_price", 0) / 100
                }
            return result
        except Exception as e:
            return {"errcode": -1, "errmsg": str(e)}
    
    def get_product_list(self, limit: int = 10) -> List[str]:
        """获取商品列表"""
        token = self._get_access_token()
        url = f"https://api.weixin.qq.com/channels/ec/product/list/get?access_token={token}"
        
        try:
            resp = requests.post(url, json={"limit": limit}, timeout=30)
            result = resp.json()
            
            if result.get("errcode") == 0:
                return result.get("product_ids", [])
            return []
        except:
            return []


# 便捷函数
def smart_list_product(name: str, price: float, original_price: float = None, 
                       stock: int = 100) -> Dict:
    """
    智能上架商品到微信小店
    
    Args:
        name: 商品名称（会自动识别类目）
        price: 售价（元）
        original_price: 原价（元），默认售价的1.5倍
        stock: 库存，默认100
        
    Returns:
        上架结果
    """
    uploader = SmartWechatUploader()
    
    product_info = {
        "name": name,
        "price": price,
        "original_price": original_price,
        "stock": stock
    }
    
    return uploader.smart_create_and_list(product_info)
