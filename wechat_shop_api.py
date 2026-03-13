"""
微信小店商品管理模块
提供商品列表获取、商品详情查询等功能
"""
import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional

class WechatShopAPI:
    """微信小店API封装"""
    
    def __init__(self, appid: str = None, secret: str = None):
        self.appid = appid or "wx304ca87183801402"
        self.secret = secret or "d9560ed4c2782016fcccef4c3f009d9a"
        self.access_token = None
        self.token_expire_time = None
    
    def _get_access_token(self) -> str:
        """获取access_token，带缓存"""
        # 如果token未过期，直接返回
        if self.access_token and self.token_expire_time and datetime.now() < self.token_expire_time:
            return self.access_token
        
        # 重新获取token
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
                # token有效期7200秒，提前300秒过期
                expires_in = data.get("expires_in", 7200)
                self.token_expire_time = datetime.now() + timedelta(seconds=expires_in - 300)
                return self.access_token
            else:
                raise Exception(f"获取token失败: {data.get('errmsg', '未知错误')}")
        except Exception as e:
            raise Exception(f"获取access_token失败: {str(e)}")
    
    def get_product_list(self, limit: int = 10, next_key: str = "") -> Dict:
        """
        获取商品列表
        
        Args:
            limit: 返回商品数量，默认10
            next_key: 分页参数，第一次调用传空
            
        Returns:
            {
                "errcode": 0,
                "errmsg": "ok",
                "product_ids": ["10000546519816", ...],
                "next_key": "xxx",
                "total_num": 4
            }
        """
        token = self._get_access_token()
        url = f"https://api.weixin.qq.com/channels/ec/product/list/get?access_token={token}"
        
        payload = {
            "limit": limit
        }
        if next_key:
            payload["next_key"] = next_key
        
        try:
            response = requests.post(url, json=payload, timeout=15)
            return response.json()
        except Exception as e:
            return {"errcode": -1, "errmsg": f"请求失败: {str(e)}"}
    
    def get_product_detail(self, product_id: str) -> Dict:
        """
        获取商品详情
        
        Args:
            product_id: 商品ID
            
        Returns:
            商品详细信息
        """
        token = self._get_access_token()
        url = f"https://api.weixin.qq.com/channels/ec/product/get?access_token={token}"
        
        payload = {
            "product_id": product_id
        }
        
        try:
            response = requests.post(url, json=payload, timeout=15)
            return response.json()
        except Exception as e:
            return {"errcode": -1, "errmsg": f"请求失败: {str(e)}"}
    
    def get_all_products(self) -> List[Dict]:
        """
        获取所有商品详情
        
        Returns:
            商品详情列表
        """
        products = []
        next_key = ""
        
        while True:
            result = self.get_product_list(limit=100, next_key=next_key)
            
            if result.get("errcode") != 0:
                break
            
            product_ids = result.get("product_ids", [])
            
            # 获取每个商品的详情
            for pid in product_ids:
                detail = self.get_product_detail(pid)
                if detail.get("errcode") == 0:
                    products.append(detail.get("product", {}))
            
            # 检查是否还有下一页
            next_key = result.get("next_key", "")
            if not next_key:
                break
        
        return products
    
    def format_product_info(self, product: Dict) -> Dict:
        """
        格式化商品信息，提取关键字段
        
        Args:
            product: 原始商品数据
            
        Returns:
            格式化后的商品信息
        """
        if not product:
            return {}
        
        # 提取SKU价格
        skus = product.get("skus", [])
        prices = []
        for sku in skus:
            price = sku.get("sale_price", 0)
            if price > 0:
                prices.append(price / 100)  # 转换为元
        
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0
        
        return {
            "product_id": product.get("product_id"),
            "name": product.get("title", "") or product.get("short_title", ""),
            "title": product.get("title", ""),
            "short_title": product.get("short_title", ""),
            "head_imgs": product.get("head_imgs", []),
            "min_price": min_price,
            "max_price": max_price,
            "status": product.get("status"),
            "total_sold_num": product.get("total_sold_num", 0),
            "edit_time": product.get("edit_time")
        }


# 使用示例

    def create_product(self, product_data: Dict) -> Dict:
        """创建微信小店商品"""
        access_token = self._get_access_token()
        url = f"https://api.weixin.qq.com/wxopen/shop/product/add?access_token={access_token}"
        
        try:
            response = requests.post(url, json=product_data, timeout=30)
            result = response.json()
            
            if result.get("errcode") == 0:
                return {"errcode": 0, "product_id": result.get("product_id")}
            else:
                return {"errcode": result.get("errcode"), "errmsg": result.get("errmsg", "创建失败")}
        except Exception as e:
            return {"errcode": -1, "errmsg": str(e)}

if __name__ == "__main__":
    # 初始化API
    api = WechatShopAPI()
    
    # 获取商品列表
    print("=== 获取商品列表 ===")
    result = api.get_product_list(limit=10)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # 如果有商品，获取第一个商品的详情
    if result.get("errcode") == 0 and result.get("product_ids"):
        first_id = result["product_ids"][0]
        print(f"\n=== 获取商品 {first_id} 详情 ===")
        detail = api.get_product_detail(first_id)
        
        if detail.get("errcode") == 0:
            product = detail.get("product", {})
            formatted = api.format_product_info(product)
            print(json.dumps(formatted, indent=2, ensure_ascii=False))
        else:
            print(f"获取详情失败: {detail.get('errmsg')}")

    def create_product(self, product_data: Dict) -> Dict:
        """创建微信小店商品"""
        access_token = self._get_access_token()
        url = f"https://api.weixin.qq.com/wxopen/shop/product/add?access_token={access_token}"
        
        try:
            response = requests.post(url, json=product_data, timeout=30)
            result = response.json()
            
            if result.get("errcode") == 0:
                return {"errcode": 0, "product_id": result.get("product_id")}
            else:
                return {"errcode": result.get("errcode"), "errmsg": result.get("errmsg", "创建失败")}
        except Exception as e:
            return {"errcode": -1, "errmsg": str(e)}

    def add_product_sku(self, product_data: Dict) -> Dict:
        """添加商品SKU"""
        access_token = self._get_access_token()
        url = f"https://api.weixin.qq.com/wxopen/shop/product/add?access_token={access_token}"
        
        try:
            response = requests.post(url, json=product_data, timeout=30)
            result = response.json()
            
            if result.get("errcode") == 0:
                return {"errcode": 0, "product_id": result.get("product_id")}
            else:
                return {"errcode": result.get("errcode"), "errmsg": result.get("errmsg")}
        except Exception as e:
            return {"errcode": -1, "errmsg": str(e)}

    def list_product(self, product_id: str, status: int = 2) -> Dict:
        """上架/下架微信小店商品
        status: 2=上架, 3=下架
        """
        access_token = self._get_access_token()
        url = f"https://api.weixin.qq.com/channels/ec/product/listing?access_token={access_token}"
        
        data = {
            "product_id": product_id,
            "status": status
        }
        
        try:
            response = requests.post(url, json=data, timeout=30)
            result = response.json()
            
            if result.get("errcode") == 0:
                return {"errcode": 0, "msg": "success"}
            else:
                return {"errcode": result.get("errcode"), "errmsg": result.get("errmsg")}
        except Exception as e:
            return {"errcode": -1, "errmsg": str(e)}
