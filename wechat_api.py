"""
微信小店API对接模块
需要先在微信公众平台注册小程序/小游戏账号获取AppID和AppSecret
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Store
import requests
import time
import json
from datetime import datetime, timedelta


class WechatConfig(db.Model):
    """微信配置表"""
    __tablename__ = 'wechat_config'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)

    # 微信开放平台配置
    app_id = db.Column(db.String(50), comment='AppID')
    app_secret = db.Column(db.String(100), comment='AppSecret')

    # 授权信息
    access_token = db.Column(db.String(500), comment='Access Token')
    token_expires_at = db.Column(db.DateTime, comment='Token过期时间')
    refresh_token = db.Column(db.String(200), comment='刷新Token')

    # 授权状态
    is_authorized = db.Column(db.Boolean, default=False, comment='是否已授权')
    authorized_at = db.Column(db.DateTime, comment='授权时间')

    # 状态
    status = db.Column(db.String(20), default='inactive', comment='状态')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    store = db.relationship('Store', backref='wechat_config', uselist=False)

    def to_dict(self):
        return {
            'id': self.id,
            'store_id': self.store_id,
            'store_name': self.store.name if self.store else None,
            'app_id': self.app_id,
            'is_authorized': self.is_authorized,
            'status': self.status,
            'authorized_at': self.authorized_at.isoformat() if self.authorized_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class WechatProduct(db.Model):
    """微信小店商品表"""
    __tablename__ = 'wechat_products'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    product_id = db.Column(db.String(50), comment='微信商品ID')
    local_product_id = db.Column(db.Integer, db.ForeignKey('products.id'), comment='本地商品ID')

    # 商品信息
    name = db.Column(db.String(200), comment='商品名称')
    main_image = db.Column(db.String(500), comment='主图')
    category_id = db.Column(db.String(50), comment='微信分类ID')
    category_name = db.Column(db.String(100), comment='微信分类名称')

    # 价格
    original_price = db.Column(db.Float, comment='原价')
    sale_price = db.Column(db.Float, comment='售价')

    # 状态
    status = db.Column(db.String(20), comment='微信商品状态')
    quality_status = db.Column(db.String(20), comment='商品质量状态')

    # 同步信息
    last_synced_at = db.Column(db.DateTime, comment='最后同步时间')
    sync_status = db.Column(db.String(20), default='pending', comment='同步状态: pending/synced/error')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    store = db.relationship('Store', backref='wechat_products', lazy='select')

    def to_dict(self):
        return {
            'id': self.id,
            'store_id': self.store_id,
            'product_id': self.product_id,
            'local_product_id': self.local_product_id,
            'name': self.name,
            'main_image': self.main_image,
            'category_name': self.category_name,
            'original_price': self.original_price,
            'sale_price': self.sale_price,
            'status': self.status,
            'quality_status': self.quality_status,
            'last_synced_at': self.last_synced_at.isoformat() if self.last_synced_at else None,
            'sync_status': self.sync_status
        }


class WechatOrder(db.Model):
    """微信小店订单表"""
    __tablename__ = 'wechat_orders'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    order_id = db.Column(db.String(50), unique=True, nullable=False, comment='微信订单ID')

    # 订单信息
    order_type = db.Column(db.String(20), comment='订单类型')
    order_status = db.Column(db.String(20), comment='订单状态')
    pay_type = db.Column(db.String(20), comment='支付方式')

    # 金额
    total_price = db.Column(db.Float, comment='订单总价')
    actual_price = db.Column(db.Float, comment='实际支付')

    # 商品信息
    product_id = db.Column(db.String(50), comment='微信商品ID')
    product_name = db.Column(db.String(200), comment='商品名称')
    sku_id = db.Column(db.String(50), comment='SKU ID')
    quantity = db.Column(db.Integer, comment='数量')

    # 用户信息
    openid = db.Column(db.String(100), comment='用户OpenID')

    # 时间
    create_time = db.Column(db.DateTime, comment='创建时间')
    pay_time = db.Column(db.DateTime, comment='支付时间')
    deliver_time = db.Column(db.DateTime, comment='发货时间')
    finish_time = db.Column(db.DateTime, comment='完成时间')

    # 同步信息
    last_synced_at = db.Column(db.DateTime, comment='最后同步时间')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    store = db.relationship('Store', backref='wechat_orders', lazy='select')

    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order_id,
            'order_type': self.order_type,
            'order_status': self.order_status,
            'pay_type': self.pay_type,
            'total_price': self.total_price,
            'actual_price': self.actual_price,
            'product_name': self.product_name,
            'quantity': self.quantity,
            'create_time': self.create_time.isoformat() if self.create_time else None,
            'order_status_text': self.get_status_text()
        }

    def get_status_text(self):
        status_map = {
            '10': '待支付',
            '20': '已支付',
            '30': '已发货',
            '40': '已收货',
            '50': '已完成',
            '60': '已取消'
        }
        return status_map.get(str(self.order_status), '未知')


# ==================== 微信API工具类 ====================

class WechatAPI:
    """微信API调用工具类"""

    BASE_URL = 'https://api.weixin.qq.com'

    def __init__(self, app_id, app_secret, access_token=None):
        self.app_id = app_id
        self.app_secret = app_secret
        self.access_token = access_token

    def get_access_token(self):
        """获取Access Token"""
        if self.access_token:
            return self.access_token

        url = f'{self.BASE_URL}/cgi-bin/token'
        params = {
            'grant_type': 'client_credential',
            'appid': self.app_id,
            'secret': self.app_secret
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if 'access_token' in data:
                return data['access_token']
            else:
                raise Exception(f"获取Token失败: {data.get('errmsg', '未知错误')}")
        except Exception as e:
            raise Exception(f"请求失败: {str(e)}")

    def call_api(self, endpoint, method='GET', data=None, use_token=True):
        """调用微信API"""
        url = f'{self.BASE_URL}{endpoint}'

        params = {}
        if use_token and self.access_token:
            params['access_token'] = self.access_token

        try:
            if method == 'GET':
                response = requests.get(url, params=params, timeout=10)
            else:
                response = requests.post(url, params=params, json=data, timeout=10)

            result = response.json()

            # 检查错误码
            if 'errcode' in result and result['errcode'] != 0:
                # 如果是token过期，尝试刷新
                if result['errcode'] in [40001, 40014]:
                    raise TokenExpiredError('Access Token已过期')
                raise Exception(f"API调用失败: {errcode_to_msg(result.get('errcode'))}")

            return result
        except TokenExpiredError:
            raise
        except Exception as e:
            raise Exception(f"API请求失败: {str(e)}")

    def get_product_list(self, status=None, page=1, page_size=20):
        """获取商品列表"""
        endpoint = '/wxaapp/v3/shop/spu/get_list'
        data = {
            'status': status,
            'page': page,
            'page_size': page_size
        }
        return self.call_api(endpoint, method='POST', data=data)

    def get_product_detail(self, product_id):
        """获取商品详情"""
        endpoint = '/wxaapp/v3/shop/spu/get'
        data = {'product_id': product_id}
        return self.call_api(endpoint, method='POST', data=data)

    def add_product(self, product_data):
        """添加商品"""
        endpoint = '/wxaapp/v3/shop/spu/add'
        return self.call_api(endpoint, method='POST', data=product_data)

    def update_product(self, product_id, product_data):
        """更新商品"""
        endpoint = '/wxaapp/v3/shop/spu/update'
        data = {'product_id': product_id, **product_data}
        return self.call_api(endpoint, method='POST', data=data)

    def get_order_list(self, status=None, start_time=None, end_time=None, page=1, page_size=20):
        """获取订单列表"""
        endpoint = '/wxaapp/v3/shop/order/get_list'
        data = {
            'status': status,
            'start_time': start_time,
            'end_time': end_time,
            'page': page,
            'page_size': page_size
        }
        return self.call_api(endpoint, method='POST', data=data)

    def get_order_detail(self, order_id):
        """获取订单详情"""
        endpoint = '/wxaapp/v3/shop/order/get'
        data = {'order_id': order_id}
        return self.call_api(endpoint, method='POST', data=data)

    def update_order_status(self, order_id, status, data=None):
        """更新订单状态"""
        endpoint = '/wxaapp/v3/shop/order/update'
        payload = {'order_id': order_id, 'status': status}
        if data:
            payload.update(data)
        return self.call_api(endpoint, method='POST', data=payload)


class TokenExpiredError(Exception):
    """Token过期异常"""
    pass


def errcode_to_msg(errcode):
    """错误码转错误信息"""
    errcode_map = {
        -1: '系统繁忙',
        0: '成功',
        40001: 'Access Token无效',
        40002: 'refresh_token无效',
        40013: 'AppID无效',
        40125: 'AppSecret无效',
        41002: '缺少AppID参数',
        41004: '缺少AppSecret参数',
        41008: '缺少access_token参数',
        42001: 'Access Token已过期',
        43002: '需要GET请求',
        43004: '需要POST请求',
        44002: 'POST数据为空',
        47001: 'POST数据格式错误',
        49000: '商品ID错误',
        49001: '商品不存在',
        49002: '商品已下架',
        50001: '接口未授权'
    }
    return errcode_map.get(errcode, f'未知错误({errcode})')


# ==================== 路由：微信小店管理 ====================

def register_wechat_routes(app):
    """注册微信小店路由"""

    @app.route('/wechat/config/<int:store_id>', methods=['GET', 'POST'])
    @login_required
    def wechat_config(store_id):
        """微信小店配置"""
        store = Store.query.get_or_404(store_id)
        config = WechatConfig.query.filter_by(store_id=store_id).first()

        if request.method == 'POST':
            data = request.form

            if not config:
                config = WechatConfig(store_id=store_id)
                db.session.add(config)

            config.app_id = data.get('app_id')
            config.app_secret = data.get('app_secret')
            config.status = 'active'

            db.session.commit()
            flash('微信配置保存成功', 'success')
            return redirect(url_for('wechat_config', store_id=store_id))

        return render_template('wechat/config.html', store=store, config=config)

    @app.route('/wechat/authorize/<int:store_id>')
    @login_required
    def wechat_authorize(store_id):
        """发起微信授权"""
        config = WechatConfig.query.filter_by(store_id=store_id).first()

        if not config or not config.app_id:
            flash('请先配置AppID和AppSecret', 'error')
            return redirect(url_for('wechat_config', store_id=store_id))

        # 微信授权回调地址（需要在微信开放平台配置）
        redirect_uri = url_for('wechat_callback', store_id=store_id, _external=True)
        redirect_uri = requests.utils.quote(redirect_uri)

        auth_url = (
            f"https://open.weixin.qq.com/connect/oauth2/authorize?"
            f"appid={config.app_id}&"
            f"redirect_uri={redirect_uri}&"
            f"response_type=code&"
            f"scope=snsapi_base&"
            f"state=STATE#wechat_redirect"
        )

        return redirect(auth_url)

    @app.route('/wechat/callback/<int:store_id>')
    @login_required
    def wechat_callback(store_id):
        """微信授权回调"""
        code = request.args.get('code')
        state = request.args.get('state')

        if not code:
            flash('授权失败：未获取到授权码', 'error')
            return redirect(url_for('wechat_config', store_id=store_id))

        config = WechatConfig.query.filter_by(store_id=store_id).first()

        try:
            # 通过code获取授权信息
            url = f'{WechatAPI.BASE_URL}/sns/oauth2/access_token'
            params = {
                'appid': config.app_id,
                'secret': config.app_secret,
                'code': code,
                'grant_type': 'authorization_code'
            }

            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if 'access_token' in data:
                config.access_token = data['access_token']
                config.refresh_token = data.get('refresh_token')
                config.token_expires_at = datetime.utcnow() + timedelta(seconds=data.get('expires_in', 7200))
                config.is_authorized = True
                config.authorized_at = datetime.utcnow()
                db.session.commit()
                flash('微信授权成功！', 'success')
            else:
                flash(f'授权失败：{data.get("errmsg", "未知错误")}', 'error')

        except Exception as e:
            flash(f'授权过程出错：{str(e)}', 'error')

        return redirect(url_for('wechat_config', store_id=store_id))

    @app.route('/wechat/sync/products/<int:store_id>')
    @login_required
    def wechat_sync_products(store_id):
        """同步微信小店商品"""
        config = WechatConfig.query.filter_by(store_id=store_id, is_authorized=True).first()

        if not config:
            flash('请先完成微信授权', 'error')
            return redirect(url_for('wechat_config', store_id=store_id))

        try:
            # 检查token是否过期
            if config.token_expires_at and config.token_expires_at < datetime.utcnow():
                flash('Access Token已过期，请重新授权', 'error')
                return redirect(url_for('wechat_config', store_id=store_id))

            wechat = WechatAPI(config.app_id, config.app_secret, config.access_token)

            # 获取商品列表
            result = wechat.get_product_list(status=0, page=1, page_size=50)
            products = result.get('data', {}).get('spus', [])

            synced_count = 0
            for product in products:
                # 检查是否已存在
                existing = WechatProduct.query.filter_by(
                    store_id=store_id,
                    product_id=str(product.get('product_id'))
                ).first()

                if existing:
                    # 更新
                    existing.name = product.get('name')
                    existing.main_image = product.get('main_img')
                    existing.sale_price = product.get('price_info', {}).get('min_price')
                    existing.original_price = product.get('price_info', {}).get('max_price')
                    existing.status = str(product.get('status'))
                    existing.quality_status = product.get('quality_status')
                    existing.last_synced_at = datetime.utcnow()
                    existing.sync_status = 'synced'
                else:
                    # 新建
                    wp = WechatProduct(
                        store_id=store_id,
                        product_id=str(product.get('product_id')),
                        name=product.get('name'),
                        main_image=product.get('main_img'),
                        sale_price=product.get('price_info', {}).get('min_price'),
                        original_price=product.get('price_info', {}).get('max_price'),
                        status=str(product.get('status')),
                        quality_status=product.get('quality_status'),
                        last_synced_at=datetime.utcnow(),
                        sync_status='synced'
                    )
                    db.session.add(wp)

                synced_count += 1

            db.session.commit()
            flash(f'商品同步成功！共同步 {synced_count} 个商品', 'success')

        except Exception as e:
            flash(f'同步失败：{str(e)}', 'error')

        return redirect(url_for('wechat_products', store_id=store_id))

    @app.route('/wechat/orders/<int:store_id>')
    @login_required
    def wechat_orders(store_id):
        """微信订单列表"""
        store = Store.query.get_or_404(store_id)
        config = WechatConfig.query.filter_by(store_id=store_id).first()

        query = WechatOrder.query.filter_by(store_id=store_id)

        # 筛选状态
        status = request.args.get('status')
        if status:
            query = query.filter_by(order_status=status)

        page = request.args.get('page', 1, type=int)
        pagination = query.order_by(WechatOrder.create_time.desc()).paginate(
            page=page, per_page=20, error_out=False
        )

        return render_template('wechat/orders.html', 
 store=store,                             
                             config=config,
                             pagination=pagination,
                             status=status)

    @app.route('/wechat/sync/orders/<int:store_id>')
    @login_required
    def wechat_sync_orders(store_id):
        """同步微信订单"""
        config = WechatConfig.query.filter_by(store_id=store_id, is_authorized=True).first()

        if not config:
            flash('请先完成微信授权', 'error')
            return redirect(url_for('wechat_config', store_id=store_id))

        try:
            wechat = WechatAPI(config.app_id, config.app_secret, config.access_token)

            # 获取最近7天的订单
            end_time = int(time.time())
            start_time = end_time - 7 * 24 * 60 * 60

            result = wechat.get_order_list(
                status=0,
                start_time=start_time,
                end_time=end_time,
                page=1,
                page_size=50
            )

            orders = result.get('data', {}).get('orders', [])

            synced_count = 0
            for order in orders:
                # 检查是否已存在
                existing = WechatOrder.query.filter_by(order_id=order.get('order_id')).first()

                if not existing:
                    order_info = order.get('order_info', {})
                    product_info = order.get('product_info', {})

                    wo = WechatOrder(
                        store_id=store_id,
                        order_id=order.get('order_id'),
                        order_type=order_info.get('order_type'),
                        order_status=str(order_info.get('status')),
                        pay_type=order_info.get('pay_type'),
                        total_price=order_info.get('total_price') / 100,
                        actual_price=order_info.get('actual_price') / 100,
                        product_id=product_info.get('product_id'),
                        product_name=product_info.get('product_name'),
                        sku_id=product_info.get('sku_id'),
                        quantity=product_info.get('quantity'),
                        openid=order_info.get('openid'),
                        create_time=datetime.fromtimestamp(order_info.get('create_time', 0)),
                        last_synced_at=datetime.utcnow()
                    )

                    # 处理支付时间
                    if order_info.get('pay_time'):
                        wo.pay_time = datetime.fromtimestamp(order_info.get('pay_time'))

                    db.session.add(wo)
                    synced_count += 1

            db.session.commit()
            flash(f'订单同步成功！共同步 {synced_count} 个新订单', 'success')

        except Exception as e:
            flash(f'同步失败：{str(e)}', 'error')

        return redirect(url_for('wechat_orders', store_id=store_id))

    @app.route('/wechat/products/<int:store_id>')
    @login_required
    def wechat_products(store_id):
        """微信商品列表"""
        store = Store.query.get_or_404(store_id)
        config = WechatConfig.query.filter_by(store_id=store_id).first()

        query = WechatProduct.query.filter_by(store_id=store_id)

        page = request.args.get('page', 1, type=int)
        pagination = query.order_by(WechatProduct.last_synced_at.desc()).paginate(
            page=page, per_page=20, error_out=False
        )

        return render_template('wechat/products.html', 
                             store=store, 
                             config=config,
                             pagination=pagination)

    # API接口
    @app.route('/api/wechat/config/<int:store_id>', methods=['GET', 'PUT', 'DELETE'])
    @login_required
    def api_wechat_config(store_id):
        """API: 微信配置"""
        config = WechatConfig.query.filter_by(store_id=store_id).first()

        if request.method == 'GET':
            if not config:
                return jsonify({'success': False, 'message': '配置不存在'}), 404
            return jsonify({'success': True, 'data': config.to_dict()})

        elif request.method == 'PUT':
            data = request.get_json()

            if not config:
                config = WechatConfig(store_id=store_id)
                db.session.add(config)

            config.app_id = data.get('app_id')
            config.app_secret = data.get('app_secret')
            config.status = data.get('status', 'active')

            db.session.commit()
            return jsonify({'success': True, 'data': config.to_dict()})

        elif request.method == 'DELETE':
            if config:
                db.session.delete(config)
                db.session.commit()
            return jsonify({'success': True, 'message': '删除成功'})

    @app.route('/api/wechat/products/<int:store_id>', methods=['GET'])
    @login_required
    def api_wechat_products(store_id):
        """API: 微信商品列表"""
        query = WechatProduct.query.filter_by(store_id=store_id)

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        pagination = query.order_by(WechatProduct.last_synced_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify({
            'success': True,
            'data': [p.to_dict() for p in pagination.items],
            'pagination': {
                'page': page,
                'pages': pagination.pages,
                'total': pagination.total
            }
        })

    @app.route('/api/wechat/orders/<int:store_id>', methods=['GET'])
    @login_required
    def api_wechat_orders(store_id):
        """API: 微信订单列表"""
        query = WechatOrder.query.filter_by(store_id=store_id)

        status = request.args.get('status')
        if status:
            query = query.filter_by(order_status=status)

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        pagination = query.order_by(WechatOrder.create_time.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify({
            'success': True,
            'data': [o.to_dict() for o in pagination.items],
            'pagination': {
                'page': page,
                'pages': pagination.pages,
                'total': pagination.total
            }
        })
