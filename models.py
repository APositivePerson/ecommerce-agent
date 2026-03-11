from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# ==================== 用户管理模块 ====================

class Role(db.Model):
    """角色表：定义用户角色"""
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, comment='角色名称')
    description = db.Column(db.String(200), comment='角色描述')
    permissions = db.Column(db.JSON, comment='权限列表')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    users = db.relationship('User', backref='role', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'permissions': self.permissions,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class User(UserMixin, db.Model):
    """用户表：系统用户"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, comment='用户名')
    password_hash = db.Column(db.String(255), nullable=False, comment='密码哈希')
    real_name = db.Column(db.String(50), comment='真实姓名')
    phone = db.Column(db.String(20), comment='手机号')
    email = db.Column(db.String(120), comment='邮箱')
    avatar = db.Column(db.String(255), comment='头像URL')
    status = db.Column(db.String(20), default='active', comment='状态: active/inactive/locked')

    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), comment='角色ID')
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), comment='所属店铺ID')

    last_login_at = db.Column(db.DateTime, comment='最后登录时间')
    last_login_ip = db.Column(db.String(50), comment='最后登录IP')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    store = db.relationship('Store', backref='users', lazy='select')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'real_name': self.real_name,
            'phone': self.phone,
            'email': self.email,
            'avatar': self.avatar,
            'status': self.status,
            'role': self.role.name if self.role else None,
            'store_id': self.store_id,
            'store_name': self.store.name if self.store else None,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# ==================== 店铺管理模块 ====================

class Store(db.Model):
    """店铺表：微信小店等电商平台店铺"""
    __tablename__ = 'stores'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, comment='店铺名称')
    platform = db.Column(db.String(50), default='wechat', comment='平台: wechat/taobao/jd/pinduoduo')
    store_type = db.Column(db.String(50), comment='店铺类型')
    logo = db.Column(db.String(255), comment='店铺logo')
    description = db.Column(db.Text, comment='店铺描述')
    banner = db.Column(db.String(255), comment='店铺横幅')

    # 联系信息
    contact_name = db.Column(db.String(50), comment='联系人姓名')
    contact_phone = db.Column(db.String(20), comment='联系电话')
    contact_email = db.Column(db.String(120), comment='联系邮箱')

    # 状态信息
    status = db.Column(db.String(20), default='active', comment='状态: active/inactive/suspended')
    health_score = db.Column(db.Float, default=100.0, comment='健康度评分')
    health_score_updated_at = db.Column(db.DateTime, comment='健康度更新时间')

    # 合规信息
    is_compliant = db.Column(db.Boolean, default=True, comment='是否合规')
    violation_count = db.Column(db.Integer, default=0, comment='违规次数')
    last_violation_at = db.Column(db.DateTime, comment='最后一次违规时间')
    violation_points = db.Column(db.Integer, default=0, comment='违规积分')

    # 品牌信息
    brand_name = db.Column(db.String(100), comment='品牌名称')
    brand_logo = db.Column(db.String(255), comment='品牌logo')
    brand_description = db.Column(db.Text, comment='品牌描述')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    products = db.relationship('Product', backref='store', lazy='dynamic')
    inventory_records = db.relationship('Inventory', backref='store', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'platform': self.platform,
            'store_type': self.store_type,
            'logo': self.logo,
            'description': self.description,
            'banner': self.banner,
            'contact_name': self.contact_name,
            'contact_phone': self.contact_phone,
            'contact_email': self.contact_email,
            'status': self.status,
            'health_score': self.health_score,
            'is_compliant': self.is_compliant,
            'violation_count': self.violation_count,
            'violation_points': self.violation_points,
            'brand_name': self.brand_name,
            'brand_logo': self.brand_logo,
            'product_count': self.products.count(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class StoreViolation(db.Model):
    """店铺违规记录表"""
    __tablename__ = 'store_violations'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    violation_type = db.Column(db.String(50), comment='违规类型')
    violation_reason = db.Column(db.Text, comment='违规原因')
    penalty = db.Column(db.String(200), comment='处罚措施')
    points = db.Column(db.Integer, default=0, comment='扣分')
    status = db.Column(db.String(20), default='pending', comment='状态: pending/resolved/ignored')

    reported_at = db.Column(db.DateTime, default=datetime.utcnow, comment='上报时间')
    resolved_at = db.Column(db.DateTime, comment='解决时间')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    store = db.relationship('Store', backref='violations', lazy='select')

    def to_dict(self):
        return {
            'id': self.id,
            'store_id': self.store_id,
            'store_name': self.store.name if self.store else None,
            'violation_type': self.violation_type,
            'violation_reason': self.violation_reason,
            'penalty': self.penalty,
            'points': self.points,
            'status': self.status,
            'reported_at': self.reported_at.isoformat() if self.reported_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }


# ==================== 库存管理模块 ====================

class Category(db.Model):
    """商品分类表"""
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, comment='分类名称')
    parent_id = db.Column(db.Integer, db.ForeignKey('categories.id'), comment='父分类ID')
    level = db.Column(db.Integer, default=1, comment='层级')
    sort_order = db.Column(db.Integer, default=0, comment='排序')
    icon = db.Column(db.String(255), comment='图标')
    description = db.Column(db.String(500), comment='分类描述')
    status = db.Column(db.String(20), default='active', comment='状态: active/inactive')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    children = db.relationship('Category', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')
    products = db.relationship('Product', backref='category', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'parent_id': self.parent_id,
            'level': self.level,
            'sort_order': self.sort_order,
            'icon': self.icon,
            'description': self.description,
            'status': self.status,
            'product_count': self.products.count(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Product(db.Model):
    """商品表"""
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), comment='分类ID')

    # 基本信息
    sku_code = db.Column(db.String(50), unique=True, nullable=False, comment='SKU编码')
    name = db.Column(db.String(200), nullable=False, comment='商品名称')
    title = db.Column(db.String(300), comment='商品标题')
    subtitle = db.Column(db.String(200), comment='副标题')
    description = db.Column(db.Text, comment='商品描述')
    short_description = db.Column(db.String(500), comment='简短描述')

    # 图片
    main_image = db.Column(db.String(500), comment='主图')
    images = db.Column(db.JSON, comment='图片列表')

    # 价格和规格
    original_price = db.Column(db.Float, comment='原价')
    sale_price = db.Column(db.Float, comment='售价')
    cost_price = db.Column(db.Float, comment='成本价')
    unit = db.Column(db.String(20), default='件', comment='单位')
    weight = db.Column(db.Float, comment='重量(kg)')
    volume = db.Column(db.Float, comment='体积(m³)')

    # 状态
    status = db.Column(db.String(20), default='active', comment='状态: active/inactive/out_of_stock')
    is_hot = db.Column(db.Boolean, default=False, comment='是否热门')
    is_new = db.Column(db.Boolean, default=False, comment='是否新品')
    is_recommend = db.Column(db.Boolean, default=False, comment='是否推荐')

    # SEO
    keywords = db.Column(db.String(500), comment='关键词')
    meta_title = db.Column(db.String(200), comment='SEO标题')
    meta_description = db.Column(db.String(500), comment='SEO描述')

    # 统计
    view_count = db.Column(db.Integer, default=0, comment='浏览次数')
    sales_count = db.Column(db.Integer, default=0, comment='销售数量')
    favorite_count = db.Column(db.Integer, default=0, comment='收藏次数')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    inventory_records = db.relationship('Inventory', backref='product', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'store_id': self.store_id,
            'store_name': self.store.name if self.store else None,
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else None,
            'sku_code': self.sku_code,
            'name': self.name,
            'title': self.title,
            'subtitle': self.subtitle,
            'description': self.description,
            'short_description': self.short_description,
            'main_image': self.main_image,
            'images': self.images,
            'original_price': self.original_price,
            'sale_price': self.sale_price,
            'cost_price': self.cost_price,
            'unit': self.unit,
            'weight': self.weight,
            'volume': self.volume,
            'status': self.status,
            'is_hot': self.is_hot,
            'is_new': self.is_new,
            'is_recommend': self.is_recommend,
            'keywords': self.keywords,
            'view_count': self.view_count,
            'sales_count': self.sales_count,
            'favorite_count': self.favorite_count,
            'current_stock': self.get_current_stock(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def get_current_stock(self):
        """获取当前库存数量"""
        latest_inventory = self.inventory_records.order_by(Inventory.created_at.desc()).first()
        return latest_inventory.quantity if latest_inventory else 0


class Inventory(db.Model):
    """库存记录表"""
    __tablename__ = 'inventory'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)

    quantity = db.Column(db.Integer, default=0, comment='库存数量')
    reserved_quantity = db.Column(db.Integer, default=0, comment='预留数量')
    available_quantity = db.Column(db.Integer, default=0, comment='可用数量')
    warning_threshold = db.Column(db.Integer, default=10, comment='预警阈值')

    # 仓库信息
    warehouse_name = db.Column(db.String(100), comment='仓库名称')
    warehouse_code = db.Column(db.String(50), comment='仓库编码')
    location = db.Column(db.String(100), comment='库位')

    # 批次信息
    batch_number = db.Column(db.String(50), comment='批次号')
    production_date = db.Column(db.Date, comment='生产日期')
    expiry_date = db.Column(db.Date, comment='过期日期')

    # 成本
    cost_price = db.Column(db.Float, comment='成本单价')
    total_cost = db.Column(db.Float, comment='总成本')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'store_id': self.store_id,
            'store_name': self.store.name if self.store else None,
            'product_id': self.product_id,
            'product_name': self.product.name if self.product else None,
            'sku_code': self.product.sku_code if self.product else None,
            'quantity': self.quantity,
            'reserved_quantity': self.reserved_quantity,
            'available_quantity': self.available_quantity,
            'warning_threshold': self.warning_threshold,
            'is_low_stock': self.quantity <= self.warning_threshold,
            'warehouse_name': self.warehouse_name,
            'warehouse_code': self.warehouse_code,
            'location': self.location,
            'batch_number': self.batch_number,
            'production_date': self.production_date.isoformat() if self.production_date else None,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'cost_price': self.cost_price,
            'total_cost': self.total_cost,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class InventoryTransaction(db.Model):
    """库存变动记录表"""
    __tablename__ = 'inventory_transactions'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.id'), nullable=False)

    transaction_type = db.Column(db.String(50), nullable=False, comment='变动类型: in/out/transfer/adjust')
    quantity_change = db.Column(db.Integer, nullable=False, comment='变动数量（正数增加，负数减少）')
    quantity_before = db.Column(db.Integer, comment='变动前数量')
    quantity_after = db.Column(db.Integer, comment='变动后数量')

    reason = db.Column(db.String(200), comment='变动原因')
    reference_type = db.Column(db.String(50), comment='关联类型: order/purchase/loss/gain/adjust')
    reference_id = db.Column(db.String(100), comment='关联ID')

    # 操作人
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'), comment='操作人ID')
    operator_name = db.Column(db.String(50), comment='操作人姓名')

    # 备注
    note = db.Column(db.Text, comment='备注')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship('Product', backref='transactions', lazy='select')
    inventory = db.relationship('Inventory', backref='transactions', lazy='select')

    def to_dict(self):
        return {
            'id': self.id,
            'store_id': self.store_id,
            'product_id': self.product_id,
            'product_name': self.product.name if self.product else None,
            'sku_code': self.product.sku_code if self.product else None,
            'transaction_type': self.transaction_type,
            'quantity_change': self.quantity_change,
            'quantity_before': self.quantity_before,
            'quantity_after': self.quantity_after,
            'reason': self.reason,
            'reference_type': self.reference_type,
            'reference_id': self.reference_id,
            'operator_id': self.operator_id,
            'operator_name': self.operator_name,
            'note': self.note,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
