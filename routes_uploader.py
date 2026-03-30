# -*- coding: utf-8 -*-
"""
微信小店上架助手API
提供HTTP接口用于商品上架
"""
import os
import sys
import requests
import json
import logging
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from wechat_uploader import SmartWechatUploader

# 配置日志
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, format='%(message)s')
logger = logging.getLogger(__name__)

bp = Blueprint('uploader', __name__, url_prefix='/api/uploader')

# 允许的图片格式
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'webp'}

def allowed_file(filename):
    # 有扩展名的情况
    if '.' in filename:
        return filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    # 没有扩展名的情况，检查文件头
    return True  # 允许无扩展名的文件，由后端检查内容


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
        "sku_code": "xxx",     # SKU编码，必填
        "brand": "品牌",        # 品牌，可选
        "main_images": [],      # 主图URL列表
        "detail_images": []    # 详情图URL列表
    }
    """
    data = request.get_json() or {}
    
    name = data.get('name')
    price = data.get('price')
    sku_code = data.get('sku_code')
    
    if not name or not price:
        return jsonify({
            "success": False,
            "message": "缺少必要参数：name, price"
        }), 400
    
    if not sku_code:
        return jsonify({
            "success": False,
            "message": "请输入商品编码(SKU)"
        }), 400
    
    # 使用 SmartWechatUploader
    uploader = SmartWechatUploader()
    
    # 获取图片
    main_images = data.get('main_images', [])
    detail_images = data.get('detail_images', [])
    
    # 写入日志文件
    import os
    log_file = '/tmp/flask_debug.log'
    with open(log_file, 'a') as f:
        f.write(f"[ROUTES] 收到请求: name={name}, main_images={main_images}, detail_images={detail_images}\n")
    
    # 如果没有提供图片，使用模板图（明确检查列表长度）
    if len(main_images) == 0:
        with open(log_file, 'a') as f:
            f.write("[ROUTES] main_images为空，使用模板\n")
        try:
            config = uploader.get_template_config()
            main_images = config.get('head_imgs', [])[:5]
            detail_images = config.get('desc_info_imgs', [])[:10]
        except Exception as e:
            with open(log_file, 'a') as f:
                f.write(f"[ROUTES] 获取模板失败: {e}\n")
    else:
        with open(log_file, 'a') as f:
            f.write("[ROUTES] 使用用户图片\n")
    
    product_info = {
        "name": name,
        "price": price,
        "original_price": data.get('original_price'),
        "stock": data.get('stock', 100),
        "sku_code": sku_code,
        "brand": data.get('brand'),
        "main_images": main_images,
        "detail_images": detail_images
    }
    
    with open(log_file, 'a') as f:
        f.write(f"[ROUTES] 传递给smart_create_and_list: main_images={len(main_images)}, detail_images={len(detail_images)}\n")
    
    result = uploader.smart_create_and_list(product_info)
    
    return jsonify(result)


@bp.route('/upload', methods=['POST'])
def upload_image():
    """上传图片到微信服务器"""
    if 'file' not in request.files:
        return jsonify({
            "success": False,
            "message": "请选择文件"
        }), 400
    
    file = request.files['file']
    img_type = request.form.get('type', 'main')
    
    if file.filename == '':
        return jsonify({
            "success": False,
            "message": "请选择文件"
        }), 400
    
    if not allowed_file(file.filename):
        return jsonify({
            "success": False,
            "message": "不支持的图片格式"
        }), 400
    
    # 保存到临时文件
    filename = secure_filename(file.filename)
    upload_folder = current_app.config.get('UPLOAD_FOLDER', '/tmp/uploads')
    os.makedirs(upload_folder, exist_ok=True)
    filepath = os.path.join(upload_folder, filename)
    file.save(filepath)
    
    # 上传到微信图片服务器
    try:
        uploader = SmartWechatUploader()
        url = uploader.upload_image(filepath)
        
        # 删除临时文件
        os.remove(filepath)
        
        return jsonify({
            "success": True,
            "url": url
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


@bp.route('/ai_generate', methods=['POST'])
def ai_generate_image():
    """AI生成商品图片"""
    data = request.get_json() or {}
    
    prompt = data.get('prompt', '')
    img_type = data.get('type', 'main')  # main 或 detail
    service = data.get('service', 'pollinations')  # pollinations 或 dalle
    style = data.get('style', 'product')
    api_key = data.get('apiKey', '')
    
    if not prompt:
        return jsonify({
            "success": False,
            "message": "请输入商品描述"
        }), 400
    
    # 构建AI提示词
    if style == 'product':
        style_prompt = "Professional product photography, white background, clean and sharp"
    elif style == 'simple':
        style_prompt = "Minimalist product photo, simple light gray background"
    elif style == 'lifestyle':
        style_prompt = "Lifestyle product photography, natural lighting, cozy atmosphere"
    elif style == '3d':
        style_prompt = "3D rendered product, soft shadows, high quality"
    
    full_prompt = f"{prompt}, {style_prompt}"
    
    images = []
    
    if service == 'pollinations':
        # 使用 Pollinations.ai (免费)
        try:
            num_images = 3 if img_type == 'main' else 5
            
            for i in range(num_images):
                # 生成图片
                url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(full_prompt)}?width=800&height=800&nologo=true"
                
                # 下载图片并上传到微信服务器
                resp = requests.get(url, timeout=30)
                if resp.status_code == 200:
                    # 保存临时文件
                    tmp_path = f"/tmp/ai_gen_{i}.jpg"
                    with open(tmp_path, 'wb') as f:
                        f.write(resp.content)
                    
                    # 上传到微信
                    uploader = SmartWechatUploader()
                    wechat_url = uploader.upload_image(tmp_path)
                    images.append(wechat_url)
                    
                    # 删除临时文件
                    os.remove(tmp_path)
            
            return jsonify({
                "success": True,
                "images": images
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "message": f"生成失败: {str(e)}"
            }), 500
    
    elif service == 'dalle':
        # 使用 DALL-E
        if not api_key:
            return jsonify({
                "success": False,
                "message": "请提供 OpenAI API Key"
            }), 400
        
        try:
            import openai
            openai.api_key = api_key
            
            num_images = 3 if img_type == 'main' else 5
            size = "1024x1024"
            
            response = openai.Image.create(
                prompt=full_prompt,
                n=num_images,
                size=size
            )
            
            for item in response['data']:
                # 下载图片
                img_url = item['url']
                resp = requests.get(img_url, timeout=30)
                
                if resp.status_code == 200:
                    tmp_path = f"/tmp/dalle_{len(images)}.jpg"
                    with open(tmp_path, 'wb') as f:
                        f.write(resp.content)
                    
                    # 上传到微信
                    uploader = SmartWechatUploader()
                    wechat_url = uploader.upload_image(tmp_path)
                    images.append(wechat_url)
                    
                    os.remove(tmp_path)
            
            return jsonify({
                "success": True,
                "images": images
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "message": f"DALL-E生成失败: {str(e)}"
            }), 500
    
    return jsonify({
        "success": False,
        "message": "不支持的AI服务"
    }), 400


@bp.route('/template_images', methods=['GET'])
def get_template_images():
    """获取模板图片"""
    img_type = request.args.get('type', 'main')
    
    try:
        uploader = SmartWechatUploader()
        config = uploader.get_template_config()
        
        if img_type == 'main':
            images = config.get('head_imgs', [])[:5]
        else:
            images = config.get('desc_info_imgs', [])[:10]
        
        return jsonify({
            "success": True,
            "images": images
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


@bp.route('/products', methods=['GET'])
def get_products():
    """获取微信小店商品列表"""
    uploader = SmartWechatUploader()
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
    uploader = SmartWechatUploader()
    result = uploader.get_product_status(product_id)
    return jsonify(result)


# 本地商品上架
@bp.route('/sync', methods=['POST'])
def sync_local_product():
    """
    从本地数据库同步商品到微信小店
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
        
        uploader = SmartWechatUploader()
        
        result = uploader.smart_create_and_list({
            'name': product.name,
            'price': product.sale_price,
            'original_price': product.original_price,
            'stock': 100,
            'sku_code': product.sku_code
        })
        
        return jsonify(result)
