# -*- coding: utf-8 -*-
"""
微信小店上架助手API
提供HTTP接口用于商品上架
"""
from flask import Blueprint, request, jsonify
from wechat_uploader import WechatShopUploader, quick_list_product

bp = Blueprint('uploader', __name__, url_prefix='/api/uploader')


@bp.route('/list', methods=['POST'])
def list_product():
    """
    上架商品到微信小店
    
    请求参数 (JSON):
    {
        "name": "商品名称",
        "price": 15.0,        # 售价（元）
        "original_price": 25.0, # 原价（元），可选
        "stock": 100,          # 库存，可选
        "category": "宠物营养膏",  # 类目名称，可选
        "sku_code": "xxx"      # SKU编码，可选
    }
    """
    data = request.get_json() or {}
    
    name = data.get('name')
    price = data.get('price')
    
    if not name or not price:
        return jsonify({
            "success": False,
            "message": "缺少必要参数：name, price"
        }), 400
    
    result = quick_list_product(
        name=name,
        price=price,
        original_price=data.get('original_price'),
        category=data.get('category', '宠物营养膏'),
        stock=data.get('stock', 100)
    )
    
    return jsonify(result)


@bp.route('/products', methods=['GET'])
def get_products():
    """获取微信小店商品列表"""
    uploader = WechatShopUploader()
    product_ids = uploader.get_product_list(limit=50)
    
    products = []
    for pid in product_ids:
        status = uploader.get_product_status(pid)
        if status.get('errcode') == 0:
            products.append(status)
    
    return jsonify({
        "total": len(products),
        "products": products
    })


@bp.route('/products/<product_id>', methods=['GET'])
def get_product(product_id):
    """获取商品详情"""
    uploader = WechatShopUploader()
    result = uploader.get_product_status(product_id)
    return jsonify(result)


# 本地商品上架
@bp.route('/sync', methods=['POST'])
def sync_local_product():
    """
    从本地数据库同步商品到微信小店
    
    请求参数 (JSON):
    {
        "product_id": 16  # 本地商品ID
    }
    """
    from app import app, db
    from models import Product
    
    data = request.get_json() or {}
    local_id = data.get('product_id')
    
    if not local_id:
        return jsonify({
            "success": False,
            "message": "缺少参数：product_id"
        }), 400
    
    with app.app_context():
        product = db.session.get(Product, local_id)
        
        if not product:
            return jsonify({
                "success": False,
                "message": f"本地商品不存在: {local_id}"
            }), 404
        
        uploader = WechatShopUploader()
        
        result = uploader.list_to_wechat_shop({
            'name': product.name,
            'price': product.sale_price,
            'original_price': product.original_price,
            'category': '宠物营养膏',  # TODO: 根据实际类目
            'stock': 100,
            'sku_code': product.sku_code
        })
        
        return jsonify(result)
