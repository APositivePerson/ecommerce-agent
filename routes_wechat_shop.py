"""
微信小店商品管理路由
提供商品列表、商品详情等API接口
"""
from flask import Blueprint, jsonify, request
from wechat_shop_api import WechatShopAPI

wechat_shop_bp = Blueprint('wechat_shop', __name__, url_prefix='/api/shop')

# 初始化微信小店API
shop_api = WechatShopAPI()

@wechat_shop_bp.route('/products', methods=['GET'])
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

@wechat_shop_bp.route('/products/<product_id>', methods=['GET'])
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

@wechat_shop_bp.route('/products/sync', methods=['POST'])
def sync_products():
    """
    同步所有商品到本地数据库
    
    Returns:
        {
            "success": true,
            "data": {
                "synced_count": 4,
                "products": [...]
            }
        }
    """
    try:
        # 获取所有商品
        products = shop_api.get_all_products()
        
        # 格式化商品信息
        formatted_products = [shop_api.format_product_info(p) for p in products]
        
        # TODO: 保存到数据库
        # for product in formatted_products:
        #     db.session.add(Product(**product))
        # db.session.commit()
        
        return jsonify({
            "success": True,
            "data": {
                "synced_count": len(formatted_products),
                "products": formatted_products
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@wechat_shop_bp.route('/products/<product_id>/listing', methods=['POST'])
def update_product_listing(product_id):
    """
    上架/下架商品
    
    POST参数:
        status: 2=上架, 3=下架
        
    Returns:
        {
            "success": true,
            "message": "商品已下架"
        }
    """
    try:
        data = request.get_json() or {}
        status = data.get('status', 3)  # 默认下架
        
        result = shop_api.list_product(product_id, status)
        
        if result.get("errcode") != 0:
            return jsonify({
                "success": False,
                "error": result.get("errmsg", "操作失败")
            }), 400
        
        action = "上架" if status == 2 else "下架"
        return jsonify({
            "success": True,
            "message": f"商品已{action}"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
