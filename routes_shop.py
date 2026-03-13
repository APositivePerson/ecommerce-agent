"""
微信小店商品管理路由
提供商品列表、商品详情等API接口
"""
from flask import Blueprint, jsonify, request
from wechat_shop_api import WechatShopAPI

shop_bp = Blueprint('shop', __name__)

# 初始化微信小店API
shop_api = WechatShopAPI()

@shop_bp.route('/products', methods=['GET'])
def get_products():
    """
    获取商品列表
    
    Query参数:
        limit: 返回数量，默认10
        
    Returns:
        {
            "success": true,
            "data": {
                "products": [...],
                "total": 4
            }
        }
    """
    try:
        limit = request.args.get('limit', 10, type=int)
        
        # 获取商品列表
        result = shop_api.get_product_list(limit=limit)
        
        if result.get("errcode") != 0:
            return jsonify({
                "success": False,
                "error": result.get("errmsg", "获取失败")
            }), 400
        
        product_ids = result.get("product_ids", [])
        products = []
        
        # 获取每个商品的详情
        for pid in product_ids:
            detail = shop_api.get_product_detail(pid)
            if detail.get("errcode") == 0:
                product = detail.get("product", {})
                formatted = shop_api.format_product_info(product)
                products.append(formatted)
        
        return jsonify({
            "success": True,
            "data": {
                "products": products,
                "total": result.get("total_num", 0),
                "next_key": result.get("next_key", "")
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@shop_bp.route('/products/<product_id>', methods=['GET'])
def get_product_detail(product_id):
    """
    获取商品详情
    
    Args:
        product_id: 商品ID
        
    Returns:
        {
            "success": true,
            "data": {商品详情}
        }
    """
    try:
        result = shop_api.get_product_detail(product_id)
        
        if result.get("errcode") != 0:
            return jsonify({
                "success": False,
                "error": result.get("errmsg", "获取失败")
            }), 400
        
        product = result.get("product", {})
        
        return jsonify({
            "success": True,
            "data": product
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
