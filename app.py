from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import time
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, User, Role, Store, StoreViolation, Category, Product, Inventory, InventoryTransaction
from datetime import datetime, timedelta
import os
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ecommerce.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = '请先登录'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ==================== 初始化数据库和默认数据 ====================

def init_db():
    """初始化数据库和默认数据"""
    db.create_all()

    # 创建默认角色
    if Role.query.count() == 0:
        admin_role = Role(
            name='超级管理员',
            description='系统最高权限，可以管理所有功能',
            permissions=['all']
        )
        store_manager_role = Role(
            name='店铺管理员',
            description='可以管理店铺信息和库存',
            permissions=['store_manage', 'product_manage', 'inventory_manage']
        )
        staff_role = Role(
            name='普通员工',
            description='基本操作权限',
            permissions=['product_view', 'inventory_view']
        )
        db.session.add_all([admin_role, store_manager_role, staff_role])
        db.session.commit()

    # 创建默认管理员账户
    if User.query.filter_by(username='admin').first() is None:
        admin = User(
            username='admin',
            real_name='系统管理员',
            email='admin@example.com',
            status='active'
        )
        admin.set_password('admin123')
        admin.role = Role.query.filter_by(name='超级管理员').first()
        db.session.add(admin)
        db.session.commit()

    # 创建默认分类
    if Category.query.count() == 0:
        categories = [
            Category(name='服装鞋帽', level=1, sort_order=1),
            Category(name='食品饮料', level=1, sort_order=2),
            Category(name='家居用品', level=1, sort_order=3),
            Category(name='数码产品', level=1, sort_order=4),
            Category(name='美妆个护', level=1, sort_order=5),
        ]
        db.session.add_all(categories)
        db.session.commit()

    print("数据库初始化完成！")


# ==================== 路由：首页和登录 ====================

@app.route('/')
def index():
    """首页"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            if user.status != 'active':
                flash('账号已被禁用', 'error')
                return redirect(url_for('login'))

            login_user(user)
            user.last_login_at = datetime.utcnow()
            user.last_login_ip = request.remote_addr
            db.session.commit()

            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('用户名或密码错误', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """登出"""
    logout_user()
    flash('已成功登出', 'success')
    return redirect(url_for('login'))


# ==================== 路由：仪表盘 ====================

@app.route('/dashboard')
@login_required
def dashboard():
    """仪表盘"""
    # 统计数据
    stats = {
        'user_count': User.query.count(),
        'store_count': Store.query.count(),
        'product_count': Product.query.count(),
        'inventory_count': Inventory.query.count(),
    }

    # 如果是店铺管理员，只显示该店铺的统计数据
    if current_user.store_id:
        stats['product_count'] = Product.query.filter_by(store_id=current_user.store_id).count()
        stats['inventory_count'] = Inventory.query.filter_by(store_id=current_user.store_id).count()

    # 低库存预警
    low_stock_items = []
    inventory_query = Inventory.query.filter(Inventory.quantity <= Inventory.warning_threshold)
    if current_user.store_id:
        inventory_query = inventory_query.filter_by(store_id=current_user.store_id)
    low_stock_items = inventory_query.all()

    # 最近违规记录
    recent_violations = StoreViolation.query.order_by(
        StoreViolation.reported_at.desc()
    ).limit(5).all()

    return render_template('dashboard.html', stats=stats, low_stock_items=low_stock_items, recent_violations=recent_violations)


# ==================== 路由：用户管理 ====================

@app.route('/users')
@login_required
def users():
    """用户列表"""
    query = User.query

    # 如果是店铺管理员，只能看到本店铺的用户
    if current_user.store_id and not current_user.role or current_user.role.name != '超级管理员':
        query = query.filter_by(store_id=current_user.store_id)

    search = request.args.get('search', '')
    if search:
        query = query.filter(
            db.or_(
                User.username.contains(search),
                User.real_name.contains(search),
                User.phone.contains(search),
                User.email.contains(search)
            )
        )

    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    return render_template('users/list.html', pagination=pagination, search=search)


@app.route('/users/<int:user_id>')
@login_required
def user_detail(user_id):
    """用户详情"""
    user = User.query.get_or_404(user_id)
    return render_template('users/detail.html', user=user)


@app.route('/users/new', methods=['GET', 'POST'])
@login_required
def user_new():
    """新建用户"""
    if request.method == 'POST':
        data = request.form

        # 检查用户名是否已存在
        if User.query.filter_by(username=data.get('username')).first():
            flash('用户名已存在', 'error')
            return redirect(url_for('user_new'))

        user = User(
            username=data.get('username'),
            real_name=data.get('real_name'),
            phone=data.get('phone'),
            email=data.get('email'),
            status='active'
        )
        user.set_password(data.get('password'))

        # 设置角色
        role_id = data.get('role_id', type=int)
        if role_id:
            user.role_id = role_id

        # 设置所属店铺
        store_id = data.get('store_id', type=int)
        if store_id:
            user.store_id = store_id

        db.session.add(user)
        db.session.commit()

        flash('用户创建成功', 'success')
        return redirect(url_for('users'))

    roles = Role.query.all()
    stores = Store.query.filter_by(status='active').all()
    return render_template('users/form.html', user=None, roles=roles, stores=stores)


@app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def user_edit(user_id):
    """编辑用户"""
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        data = request.form

        user.real_name = data.get('real_name')
        user.phone = data.get('phone')
        user.email = data.get('email')
        user.status = data.get('status')

        # 只有超级管理员可以修改角色
        if current_user.role and current_user.role.name == '超级管理员':
            user.role_id = data.get('role_id', type=int)

        # 如果是超级管理员，可以修改所属店铺
        if current_user.role and current_user.role.name == '超级管理员':
            user.store_id = data.get('store_id', type=int)

        # 如果提供了新密码，则更新密码
        if data.get('password'):
            user.set_password(data.get('password'))

        db.session.commit()
        flash('用户更新成功', 'success')
        return redirect(url_for('user_detail', user_id=user_id))

    roles = Role.query.all()
    stores = Store.query.filter_by(status='active').all()
    return render_template('users/form.html', user=user, roles=roles, stores=stores)


@app.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def user_delete(user_id):
    """删除用户"""
    # 不能删除自己
    if user_id == current_user.id:
        flash('不能删除自己', 'error')
        return redirect(url_for('users'))

    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash('用户删除成功', 'success')
    return redirect(url_for('users'))


# ==================== 路由：店铺管理 ====================

@app.route('/stores')
@login_required
def stores():
    """店铺列表"""
    query = Store.query

    search = request.args.get('search', '')
    if search:
        query = query.filter(
            db.or_(
                Store.name.contains(search),
                Store.brand_name.contains(search),
                Store.contact_name.contains(search)
            )
        )

    # 如果是店铺管理员，只能看到自己的店铺
    if current_user.store_id:
        query = query.filter_by(id=current_user.store_id)

    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)

    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(Store.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    return render_template('stores/list.html', pagination=pagination, search=search, status=status)


@app.route('/stores/<int:store_id>')
@login_required
def store_detail(store_id):
    """店铺详情"""
    store = Store.query.get_or_404(store_id)
    return render_template('stores/detail.html', store=store)


@app.route('/stores/new', methods=['GET', 'POST'])
@login_required
def store_new():
    """新建店铺"""
    if request.method == 'POST':
        data = request.form

        store = Store(
            name=data.get('name'),
            platform=data.get('platform', 'wechat'),
            store_type=data.get('store_type'),
            logo=data.get('logo'),
            description=data.get('description'),
            banner=data.get('banner'),
            contact_name=data.get('contact_name'),
            contact_phone=data.get('contact_phone'),
            contact_email=data.get('contact_email'),
            status='active',
            brand_name=data.get('brand_name'),
            brand_logo=data.get('brand_logo'),
            brand_description=data.get('brand_description')
        )

        db.session.add(store)
        db.session.commit()

        flash('店铺创建成功', 'success')
        return redirect(url_for('stores'))

    return render_template('stores/form.html', store=None)


@app.route('/stores/<int:store_id>/edit', methods=['GET', 'POST'])
@login_required
def store_edit(store_id):
    """编辑店铺"""
    store = Store.query.get_or_404(store_id)

    if request.method == 'POST':
        data = request.form

        store.name = data.get('name')
        store.platform = data.get('platform')
        store.store_type = data.get('store_type')
        store.logo = data.get('logo')
        store.description = data.get('description')
        store.banner = data.get('banner')
        store.contact_name = data.get('contact_name')
        store.contact_phone = data.get('contact_phone')
        store.contact_email = data.get('contact_email')
        store.status = data.get('status')
        store.brand_name = data.get('brand_name')
        store.brand_logo = data.get('brand_logo')
        store.brand_description = data.get('brand_description')

        db.session.commit()
        flash('店铺更新成功', 'success')
        return redirect(url_for('store_detail', store_id=store_id))

    return render_template('stores/form.html', store=store)


@app.route('/stores/<int:store_id>/violations')
@login_required
def store_violations(store_id):
    """店铺违规记录"""
    store = Store.query.get_or_404(store_id)
    violations = StoreViolation.query.filter_by(store_id=store_id).order_by(
        StoreViolation.reported_at.desc()
    ).all()
    return render_template('stores/violations.html', store=store, violations=violations)


# ==================== 路由：库存管理 ====================

@app.route('/inventory')
@login_required
def inventory():
    """库存列表"""
    query = Inventory.query

    search = request.args.get('search', '')
    if search:
        query = query.join(Product).filter(
            db.or_(
                Product.name.contains(search),
                Product.sku_code.contains(search),
                Inventory.warehouse_name.contains(search)
            )
        )

    # 如果是店铺管理员，只能看到本店铺的库存
    if current_user.store_id:
        query = query.filter_by(store_id=current_user.store_id)

    # 低库存筛选
    low_stock = request.args.get('low_stock')
    if low_stock:
        query = query.filter(Inventory.quantity <= Inventory.warning_threshold)

    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(Inventory.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    return render_template('inventory/list.html', pagination=pagination, search=search, low_stock=low_stock)


@app.route('/inventory/<int:inventory_id>')
@login_required
def inventory_detail(inventory_id):
    """库存详情"""
    inventory = Inventory.query.get_or_404(inventory_id)

    # 获取该库存的历史变动记录
    transactions = InventoryTransaction.query.filter_by(
        inventory_id=inventory_id
    ).order_by(InventoryTransaction.created_at.desc()).limit(50).all()

    return render_template('inventory/detail.html', inventory=inventory, transactions=transactions)


@app.route('/inventory/adjust', methods=['GET', 'POST'])
@login_required
def inventory_adjust():
    """库存调整"""
    if request.method == 'POST':
        data = request.form

        # 获取或创建库存记录
        inventory = Inventory.query.filter_by(
            product_id=data.get('product_id', type=int),
            warehouse_code=data.get('warehouse_code')
        ).first()

        if not inventory:
            inventory = Inventory(
                store_id=data.get('store_id', type=int),
                product_id=data.get('product_id', type=int),
                quantity=0,
                warehouse_name=data.get('warehouse_name'),
                warehouse_code=data.get('warehouse_code'),
                warning_threshold=data.get('warning_threshold', type=int, default=10)
            )
            db.session.add(inventory)
            db.session.flush()

        quantity_before = inventory.quantity
        quantity_change = data.get('quantity_change', type=int)
        quantity_after = quantity_before + quantity_change

        # 更新库存
        inventory.quantity = quantity_after
        inventory.available_quantity = quantity_after - inventory.reserved_quantity

        # 记录变动
        transaction = InventoryTransaction(
            store_id=inventory.store_id,
            product_id=inventory.product_id,
            inventory_id=inventory.id,
            transaction_type=data.get('transaction_type', 'adjust'),
            quantity_change=quantity_change,
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            reason=data.get('reason'),
            reference_type=data.get('reference_type'),
            reference_id=data.get('reference_id'),
            operator_id=current_user.id,
            operator_name=current_user.real_name or current_user.username,
            note=data.get('note')
        )

        db.session.add(transaction)
        db.session.commit()

        flash('库存调整成功', 'success')
        return redirect(url_for('inventory_detail', inventory_id=inventory.id))

    # 获取可选的店铺和商品
    stores = Store.query.filter_by(status='active').all()
    if current_user.store_id:
        stores = [s for s in stores if s.id == current_user.store_id]

    return render_template('inventory/adjust.html', stores=stores)


# ==================== 路由：商品管理 ====================

@app.route('/products')
@login_required
def products():
    """商品列表 - 微信小店"""
    from wechat_uploader import SmartWechatUploader
    
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    
    try:
        uploader = SmartWechatUploader()
        product_ids = uploader.get_product_list(limit=100)
        
        all_products = []
        for pid in product_ids:
            status = uploader.get_product_status(pid)
            if status.get('errcode') == 0:
                all_products.append(status)
        
        # 搜索过滤
        if search:
            all_products = [p for p in all_products if search.lower() in (p.get('title') or '').lower()]
        
        # 分页
        per_page = 20
        total = len(all_products)
        start = (page - 1) * per_page
        end = start + per_page
        page_products = all_products[start:end]
        
        pagination = type('obj', (object,), {
            'items': page_products,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page,
            'has_prev': page > 1,
            'has_next': page < (total + per_page - 1) // per_page,
            'prev_num': page - 1,
            'next_num': page + 1
        })()
        
    except Exception as e:
        print(f"获取微信商品失败: {e}")
        pagination = type('obj', (object,), {
            'items': [],
            'total': 0,
            'page': 1,
            'per_page': 20,
            'pages': 0,
            'has_prev': False,
            'has_next': False,
            'prev_num': 1,
            'next_num': 1
        })()
    
    # 获取分类列表（本地）
    categories = Category.query.filter_by(status='active').order_by(Category.sort_order).all()

    return render_template('products/list.html', 
                           pagination=pagination, 
                           search=search, 
                           status='',
                           categories=categories,
                           category_id=0,
                           is_hot='',
                           is_new='',
                           is_recommend='',
                           is_wechat=True)


@app.route('/products/<int:product_id>')
@login_required
def product_detail(product_id):
    """商品详情"""
    product = Product.query.get_or_404(product_id)

    # 获取库存信息
    inventory = Inventory.query.filter_by(product_id=product_id).first()

    # 获取最近的销售记录（如果有）
    recent_transactions = InventoryTransaction.query.filter_by(
        product_id=product_id,
        transaction_type='out'
    ).order_by(InventoryTransaction.created_at.desc()).limit(10).all()

    return render_template('products/detail.html', 
                           product=product, 
                           inventory=inventory,
                           recent_transactions=recent_transactions)


@app.route('/products/new', methods=['GET', 'POST'])
@login_required
def product_new():
    """新建商品"""
    if request.method == 'POST':
        data = request.form

        # 检查SKU是否已存在
        if Product.query.filter_by(sku_code=data.get('sku_code')).first():
            flash('SKU编码已存在', 'error')
            return redirect(url_for('product_new'))

        product = Product(
            store_id=data.get('store_id', type=int) or current_user.store_id,
            category_id=data.get('category_id', type=int) or None,
            sku_code=data.get('sku_code'),
            name=data.get('name'),
            title=data.get('title'),
            subtitle=data.get('subtitle'),
            description=data.get('description'),
            short_description=data.get('short_description'),
            main_image=data.get('main_image'),
            original_price=data.get('original_price', type=float),
            sale_price=data.get('sale_price', type=float),
            cost_price=data.get('cost_price', type=float),
            unit=data.get('unit', '件'),
            weight=data.get('weight', type=float),
            volume=data.get('volume', type=float),
            keywords=data.get('keywords'),
            meta_title=data.get('meta_title'),
            meta_description=data.get('meta_description'),
            status=data.get('status', 'active'),
            is_hot=data.get('is_hot') == 'on',
            is_new=data.get('is_new') == 'on',
            is_recommend=data.get('is_recommend') == 'on'
        )

        db.session.add(product)
        db.session.commit()

        flash('商品创建成功', 'success')
        return redirect(url_for('products'))

    stores = Store.query.filter_by(status='active').all()
    categories = Category.query.filter_by(status='active').order_by(Category.sort_order).all()

    return render_template('products/form.html', 
                           product=None, 
                           stores=stores, 
                           categories=categories)


@app.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
def product_edit(product_id):
    """编辑商品"""
    product = Product.query.get_or_404(product_id)

    if request.method == 'POST':
        data = request.form

        product.category_id = data.get('category_id', type=int) or None
        product.name = data.get('name')
        product.title = data.get('title')
        product.subtitle = data.get('subtitle')
        product.description = data.get('description')
        product.short_description = data.get('short_description')
        product.main_image = data.get('main_image')
        product.original_price = data.get('original_price', type=float)
        product.sale_price = data.get('sale_price', type=float)
        product.cost_price = data.get('cost_price', type=float)
        product.unit = data.get('unit')
        product.weight = data.get('weight', type=float)
        product.volume = data.get('volume', type=float)
        product.keywords = data.get('keywords')
        product.meta_title = data.get('meta_title')
        product.meta_description = data.get('meta_description')
        product.status = data.get('status')
        product.is_hot = data.get('is_hot') == 'on'
        product.is_new = data.get('is_new') == 'on'
        product.is_recommend = data.get('is_recommend') == 'on'

        db.session.commit()
        flash('商品更新成功', 'success')
        return redirect(url_for('product_detail', product_id=product_id))

    stores = Store.query.filter_by(status='active').all()
    categories = Category.query.filter_by(status='active').order_by(Category.sort_order).all()

    return render_template('products/form.html', 
                           product=product, 
                           stores=stores, 
                           categories=categories)


@app.route('/products/<int:product_id>/delete', methods=['POST'])
@login_required
def product_delete(product_id):
    """删除商品"""
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash('商品删除成功', 'success')
    return redirect(url_for('products'))


@app.route('/products/<int:product_id>/status', methods=['POST'])
@login_required
def product_change_status(product_id):
    """修改商品状态（上架/下架/停售）"""
    product = Product.query.get_or_404(product_id)
    new_status = request.form.get('status')

    if new_status in ['active', 'inactive', 'out_of_stock']:
        product.status = new_status
        db.session.commit()
        flash(f'商品状态已更新为：{["上架", "下架", "停售"][["active", "inactive", "out_of_stock"].index(new_status)]}', 'success')
    else:
        flash('无效的状态', 'error')

    return redirect(url_for('product_detail', product_id=product_id))


# ==================== 路由：分类管理 ====================

@app.route('/categories')
@login_required
def categories():
    """分类列表"""
    query = Category.query

    search = request.args.get('search', '')
    if search:
        query = query.filter(Category.name.contains(search))

    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(Category.sort_order, Category.name).paginate(
        page=page, per_page=50, error_out=False
    )

    return render_template('categories/list.html', pagination=pagination, search=search)


@app.route('/categories/new', methods=['GET', 'POST'])
@login_required
def category_new():
    """新建分类"""
    if request.method == 'POST':
        data = request.form

        category = Category(
            name=data.get('name'),
            parent_id=data.get('parent_id', type=int) or None,
            level=data.get('level', 1, type=int),
            sort_order=data.get('sort_order', 0, type=int),
            icon=data.get('icon'),
            description=data.get('description'),
            status=data.get('status', 'active')
        )

        db.session.add(category)
        db.session.commit()

        flash('分类创建成功', 'success')
        return redirect(url_for('categories'))

    parent_categories = Category.query.filter_by(level=1).order_by(Category.sort_order).all()
    return render_template('categories/form.html', category=None, parent_categories=parent_categories)


@app.route('/categories/<int:category_id>/edit', methods=['GET', 'POST'])
@login_required
def category_edit(category_id):
    """编辑分类"""
    category = Category.query.get_or_404(category_id)

    if request.method == 'POST':
        data = request.form

        category.name = data.get('name')
        category.parent_id = data.get('parent_id', type=int) or None
        category.level = data.get('level', 1, type=int)
        category.sort_order = data.get('sort_order', 0, type=int)
        category.icon = data.get('icon')
        category.description = data.get('description')
        category.status = data.get('status')

        db.session.commit()
        flash('分类更新成功', 'success')
        return redirect(url_for('categories'))

    parent_categories = Category.query.filter_by(level=1).order_by(Category.sort_order).all()
    return render_template('categories/form.html', category=category, parent_categories=parent_categories)


# ==================== API: 商品管理 ====================

@app.route('/api/products', methods=['GET'])
@login_required
def api_products():
    """API: 获取商品列表"""
    query = Product.query

    if current_user.store_id:
        query = query.filter_by(store_id=current_user.store_id)

    search = request.args.get('search', '')
    if search:
        query = query.filter(
            db.or_(
                Product.name.contains(search),
                Product.sku_code.contains(search),
                Product.title.contains(search)
            )
        )

    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    pagination = query.order_by(Product.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'success': True,
        'data': [product.to_dict() for product in pagination.items],
        'pagination': {
            'page': page,
            'pages': pagination.pages,
            'total': pagination.total,
            'per_page': per_page
        }
    })


@app.route('/api/products/<int:product_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def api_product_detail(product_id):
    """API: 商品详情"""
    product = Product.query.get_or_404(product_id)

    if request.method == 'GET':
        return jsonify({'success': True, 'data': product.to_dict()})

    elif request.method == 'PUT':
        data = request.get_json()

        for key in ['name', 'title', 'sale_price', 'status', 'is_hot', 'is_new', 'is_recommend']:
            if key in data:
                setattr(product, key, data[key])

        db.session.commit()
        return jsonify({'success': True, 'data': product.to_dict()})

    elif request.method == 'DELETE':
        db.session.delete(product)
        db.session.commit()
        return jsonify({'success': True, 'message': '删除成功'})


# ==================== API: 库存管理 ====================

@app.route('/api/inventory', methods=['GET'])
@login_required
def api_inventory():
    """API: 获取库存列表"""
    query = Inventory.query

    if current_user.store_id:
        query = query.filter_by(store_id=current_user.store_id)

    search = request.args.get('search', '')
    if search:
        query = query.join(Product).filter(
            db.or_(
                Product.name.contains(search),
                Product.sku_code.contains(search)
            )
        )

    low_stock = request.args.get('low_stock')
    if low_stock:
        query = query.filter(Inventory.quantity <= Inventory.warning_threshold)

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    pagination = query.order_by(Inventory.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'success': True,
        'data': [inv.to_dict() for inv in pagination.items],
        'pagination': {
            'page': page,
            'pages': pagination.pages,
            'total': pagination.total,
            'per_page': per_page
        }
    })


@app.route('/api/inventory/<int:inventory_id>/adjust', methods=['POST'])
@login_required
def api_inventory_adjust(inventory_id):
    """API: 调整库存"""
    inventory = Inventory.query.get_or_404(inventory_id)
    data = request.get_json()

    quantity_before = inventory.quantity
    quantity_change = data.get('quantity_change')
    quantity_after = quantity_before + quantity_change

    inventory.quantity = quantity_after
    inventory.available_quantity = quantity_after - inventory.reserved_quantity

    transaction = InventoryTransaction(
        store_id=inventory.store_id,
        product_id=inventory.product_id,
        inventory_id=inventory.id,
        transaction_type=data.get('transaction_type', 'adjust'),
        quantity_change=quantity_change,
        quantity_before=quantity_before,
        quantity_after=quantity_after,
        reason=data.get('reason'),
        operator_id=current_user.id,
        operator_name=current_user.real_name or current_user.username,
        note=data.get('note')
    )

    db.session.add(transaction)
    db.session.commit()

    return jsonify({'success': True, 'data': inventory.to_dict()})


# ==================== 辅助API ====================

@app.route('/api/stores', methods=['GET'])
@login_required
def api_stores():
    """API: 获取店铺列表"""
    query = Store.query

    search = request.args.get('search', '')
    if search:
        query = query.filter(
            db.or_(
                Store.name.contains(search),
                Store.brand_name.contains(search)
            )
        )

    if current_user.store_id:
        query = query.filter_by(id=current_user.store_id)

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    pagination = query.order_by(Store.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'success': True,
        'data': [store.to_dict() for store in pagination.items],
        'pagination': {
            'page': page,
            'pages': pagination.pages,
            'total': pagination.total,
            'per_page': per_page
        }
    })


@app.route('/api/products/list', methods=['GET'])
@login_required
def api_products_list():
    """API: 获取商品列表（用于下拉选择）"""
    query = Product.query

    if current_user.store_id:
        query = query.filter_by(store_id=current_user.store_id)

    search = request.args.get('search', '')
    if search:
        query = query.filter(
            db.or_(
                Product.name.contains(search),
                Product.sku_code.contains(search)
            )
        )

    products = query.filter_by(status='active').all()

    return jsonify({
        'success': True,
        'data': [
            {
                'id': p.id,
                'sku_code': p.sku_code,
                'name': p.name,
                'sale_price': p.sale_price
            }
            for p in products
        ]
    })


@app.route('/api/categories', methods=['GET'])
@login_required
def api_categories():
    """API: 获取分类列表"""
    categories = Category.query.filter_by(status='active').order_by(
        Category.sort_order, Category.name
    ).all()

    return jsonify({
        'success': True,
        'data': [cat.to_dict() for cat in categories]
    })


# ==================== 微信小店API对接 ====================

from wechat_api import WechatConfig, WechatProduct, WechatOrder, register_wechat_routes
register_wechat_routes(app)


# ==================== AI上架助手API ====================
from wechat_uploader import smart_list_product, SmartWechatUploader

@app.route('/api/uploader/list', methods=['POST'])
def api_uploader_list():
    """AI智能上架商品 - 自动识别类目"""
    try:
        data = request.get_json() or {}
        
        name = data.get('name', '').strip()
        price = data.get('price')
        sku_code = data.get('sku_code', '')
        
        if not name:
            return jsonify({"success": False, "message": "请提供商品名称"}), 400
        if not price:
            return jsonify({"success": False, "message": "请提供商品价格"}), 400
        
        # 获取图片
        main_images = data.get('main_images', [])
        detail_images = data.get('detail_images', [])
        
        import os
        log_file = '/tmp/flask_debug.log'
        with open(log_file, 'a') as f:
            f.write(f"[APP.PY] 收到请求: name={name}, main_images={main_images}, detail_images={detail_images}\n")
        
        # 如果没有提供图片，使用模板图
        if len(main_images) == 0:
            with open(log_file, 'a') as f:
                f.write("[APP.PY] main_images为空，使用模板\n")
            try:
                uploader = SmartWechatUploader()
                config = uploader.get_template_config()
                main_images = config.get('head_imgs', [])[:5]
                detail_images = config.get('desc_info_imgs', [])[:10]
            except Exception as e:
                with open(log_file, 'a') as f:
                    f.write(f"[APP.PY] 获取模板失败: {e}\n")
        else:
            with open(log_file, 'a') as f:
                f.write("[APP.PY] 使用用户图片\n")
        
        # 调用智能上架助手
        result = smart_list_product(
            name=name,
            price=float(price),
            original_price=data.get('original_price'),
            stock=data.get('stock', 100),
            main_images=main_images,
            detail_images=detail_images,
            sku_code=sku_code
        )
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/uploader/products', methods=['GET'])
def api_uploader_products():
    """获取微信小店商品列表"""
    from wechat_uploader import SmartWechatUploader
    
    try:
        uploader = SmartWechatUploader()
        product_ids = uploader.get_product_list(limit=50)
        
        products = []
        for pid in product_ids:
            status = uploader.get_product_status(pid)
            if status.get('errcode') == 0:
                products.append(status)
        
        return jsonify({
            "success": True,
            "total": len(products),
            "products": products
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/uploader/sync/<int:product_id>', methods=['POST'])
def api_uploader_sync(product_id):
    """从本地商品智能同步到微信小店 - 自动识别类目"""
    from wechat_uploader import SmartWechatUploader
    
    try:
        product = db.session.get(Product, product_id)
        if not product:
            return jsonify({"success": False, "message": "商品不存在"}), 404
        
        uploader = SmartWechatUploader()
        
        result = uploader.smart_create_and_list({
            'name': product.name,
            'price': product.sale_price,
            'original_price': product.original_price,
            'stock': 100,
            'sku_code': product.sku_code
        })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ==================== 微信小店商品管理 ====================
from routes_shop import shop_api
from routes_uploader import bp as uploader_bp
from routes_strategy import strategy_bp
from routes_supply_chain import supply_chain_bp
app.register_blueprint(uploader_bp)
app.register_blueprint(strategy_bp)
app.register_blueprint(supply_chain_bp)

@app.route('/wxshop/products')
def wechat_shop_products():
    return render_template('shop_products.html')

@app.route('/api/shop/products')
def api_shop_products():
    try:
        limit = request.args.get('limit', 10, type=int)
        result = shop_api.get_product_list(limit=limit)
        
        if result.get("errcode") != 0:
            return jsonify({"success": False, "error": result.get("errmsg")}), 400
        
        product_ids = result.get("product_ids", [])
        products = []
        
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
                "total": result.get("total_num", 0)
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/shop/products/<product_id>')
def api_shop_product_detail(product_id):
    try:
        result = shop_api.get_product_detail(product_id)
        if result.get("errcode") != 0:
            return jsonify({"success": False, "error": result.get("errmsg")}), 400
        return jsonify({"success": True, "data": result.get("product", {})})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/shop/products/<product_id>/listing', methods=['POST'])
def api_shop_product_listing(product_id):
    """上架/下架商品"""
    try:
        data = request.get_json() or {}
        status = data.get('status', 3)  # 默认下架

        if status == 2:
            # 上架
            result = shop_api.list_product(product_id, status)
        else:
            # 下架 - 用 delisting 接口
            result = shop_api.delist_product(product_id)

        if result.get("errcode") != 0:
            return jsonify({"success": False, "error": result.get("errmsg", "操作失败")}), 400

        action = "上架" if status == 2 else "下架"
        return jsonify({"success": True, "message": f"商品已{action}"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/analysis')
def product_analysis():
    """店铺商品分析页面"""
    from wechat_shop_api import WechatShopAPI
    
    try:
        api = WechatShopAPI()
        products = api.get_all_products()
        
        # 基础统计
        total = len(products)
        on_sale = sum(1 for p in products if p.get('status') == 5)
        off_sale = total - on_sale
        total_sold = sum(p.get('total_sold_num', 0) for p in products)
        
        # 价格分析
        prices = []
        for p in products:
            for sku in p.get('skus', []):
                prices.append(sku.get('sale_price', 0) / 100)
        
        avg_price = sum(prices) / len(prices) if prices else 0
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0
        
        # 销量排行
        sales_rank = sorted(products, key=lambda x: x.get('total_sold_num', 0), reverse=True)[:5]
        
        # 分类统计
        cat_count = {}
        for p in products:
            for cat in p.get('cats', []):
                cat_id = cat.get('cat_id', 'unknown')
                cat_count[cat_id] = cat_count.get(cat_id, 0) + 1
        
        # 待优化商品（销量低 + 未上架）
        need_attention = [p for p in products if p.get('total_sold_num', 0) == 0 and p.get('status') != 5]
        
        # 建议
        suggestions = []
        if on_sale < total * 0.5:
            suggestions.append({
                "level": "high",
                "title": "上架率偏低",
                "content": f"当前仅 {on_sale}/{total} 个商品上架，建议检查未上架商品并尽快上架。"
            })
        if total_sold == 0:
            suggestions.append({
                "level": "high",
                "title": "销量为零",
                "content": "所有商品暂无销量，建议优化商品主图、标题或调整价格策略。"
            })
        if len(products) < 5:
            suggestions.append({
                "level": "medium",
                "title": "SKU不足",
                "content": "商品数量较少，建议根据市场需求增加更多SKU。"
            })
        for p in need_attention[:3]:
            suggestions.append({
                "level": "medium",
                "title": f"商品待优化: {p.get('title', '未命名')[:15]}",
                "content": "该商品销量为零且未上架，建议优化详情页或下架处理。"
            })
        if on_sale >= total * 0.8 and total_sold > 0:
            suggestions.append({
                "level": "low",
                "title": "运营状态良好",
                "content": "继续保持当前的运营节奏，关注数据分析优化细节。"
            })
        
        return render_template('analysis.html',
                             total=total,
                             on_sale=on_sale,
                             off_sale=off_sale,
                             total_sold=total_sold,
                             avg_price=round(avg_price, 2),
                             min_price=min_price,
                             max_price=max_price,
                             sales_rank=sales_rank,
                             cat_count=cat_count,
                             suggestions=suggestions,
                             products=products)
    
    except Exception as e:
        return f"分析失败: {str(e)}"


@app.route('/all_products')
def all_products():
    """综合商品页面 - 本地商品 + 微信小店商品"""
    # 获取本地商品
    local_products = Product.query.order_by(Product.created_at.desc()).limit(50).all()
    
    # 获取微信小店商品
    wechat_products = []
    try:
        from routes_shop import shop_api
        result = shop_api.get_product_list(limit=50)
        if result.get("errcode") == 0:
            for pid in result.get("product_ids", []):
                detail = shop_api.get_product_detail(pid)
                if detail.get("errcode") == 0:
                    product = detail.get("product", {})
                    formatted = shop_api.format_product_info(product)
                    wechat_products.append(formatted)
    except Exception as e:
        print(f"获取微信商品失败: {e}")
    
    return render_template('all_products.html', 
                         local_products=local_products,
                         wechat_products=wechat_products)


@app.route('/api/products/auto_sync', methods=['POST'])
def auto_sync_products():
    """自动从微信小店同步商品到本地并上架"""
    try:
        from routes_shop import shop_api
        synced_count = 0
        
        # 获取微信小店商品
        result = shop_api.get_product_list(limit=50)
        if result.get("errcode") != 0:
            return jsonify({"success": False, "error": result.get("errmsg")}), 400
        
        for pid in result.get("product_ids", []):
            detail = shop_api.get_product_detail(pid)
            if detail.get("errcode") != 0:
                continue
            
            product = detail.get("product", {})
            formatted = shop_api.format_product_info(product)
            
            # 检查是否已存在
            existing = Product.query.filter_by(sku_code=formatted.get("product_id")).first()
            if not existing:
                # 创建新商品
                # 获取默认店铺
                store = Store.query.first()
                if not store:
                    store = Store(name="默认店铺", code="default")
                    db.session.add(store)
                    db.session.flush()
                
                new_product = Product(
                    store_id=store.id,
                    name=formatted.get("name", "")[:200],
                    title=formatted.get("title", "")[:300],
                    sku_code=formatted.get("product_id", ""),
                    sale_price=formatted.get("min_price", 0),
                    status='active',
                    main_image=formatted.get("head_imgs", [""])[0] if formatted.get("head_imgs") else "",
                    description=formatted.get("short_title", "")
                )
                db.session.add(new_product)
                synced_count += 1
        
        db.session.commit()
        return jsonify({"success": True, "synced": synced_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== AI自动上架 ====================
import re

def parse_product_from_text(text: str) -> dict:
    """从自然语言解析商品信息"""
    text = text.strip()
    
    # 提取价格 - 更精确的匹配
    price = 0
    # 优先匹配"价格xxx元"或"xxx元"
    price_match = re.search(r'价格[是]?(\d+\.?\d*)|(\d+\.?\d*)元', text)
    if price_match:
        price = float(price_match.group(1) or price_match.group(2) or 0)
    # 匹配¥或￥符号
    yen_match = re.search(r'[¥￥](\d+\.?\d*)', text)
    if yen_match:
        price = float(yen_match.group(1))
    
    # 提取商品名称（去掉常见描述词）
    name = text
    # 去掉价格相关词
    name = re.sub(r'价?格?[是]?\d+\.?\d*\s*元?', '', name)
    # 去掉"上架"、"卖"等词
    name = re.sub(r'上?架?|出?售|卖', '', name)
    name = name.strip()[:100]
    
    # 默认值
    if not name:
        name = "未命名商品"
    if price == 0:
        price = 99.0
    
    return {
        "name": name,
        "title": name,
        "price": price,
        "description": text
    }


@app.route('/api/products/ai_listing', methods=['POST'])
def ai_product_listing():
    """AI一句话自动上架商品（本地 + 微信小店）"""
    try:
        data = request.get_json()
        user_text = data.get('text', '').strip()
        
        if not user_text:
            return jsonify({"success": False, "error": "请输入商品描述"}), 400
        
        # 解析商品信息
        product_info = parse_product_from_text(user_text)
        
        # 获取店铺
        store = Store.query.first()
        if not store:
            store = Store(name="默认店铺", code="default")
            db.session.add(store)
            db.session.flush()
        
        # 创建本地商品
        new_product = Product(
            store_id=store.id,
            name=product_info['name'],
            title=product_info['title'],
            sku_code=f"AI{int(time.time())}",
            sale_price=product_info['price'],
            status='active',
            description=product_info['description']
        )
        db.session.add(new_product)
        db.session.commit()
        
        # 尝试发布到微信小店
        wechat_product_id = None
        wechat_error = None
        try:
            from wechat_shop_api import WechatShopAPI
            shop_api = WechatShopAPI()
            
            # 使用正确的微信小店API添加商品（完整格式）
            import requests
            import json
            token = shop_api._get_access_token()
            
            # 添加商品（完整格式）
            add_url = f"https://api.weixin.qq.com/channels/ec/product/add?access_token={token}"
            
            # 解析价格获取商品规格
            price = int(product_info['price'] * 100)
            weight = "1kg"
            if "kg" in product_info['name']:
                import re
                w = re.search(r'(\d+\.?\d*)\s*kg', product_info['name'])
                if w:
                    weight = w.group(1) + "kg"
            
            add_data = {
                "product_info": {
                    "title": product_info['name'],
                    "head_imgs": [
                        "https://mmecimage.cn/p/wx304ca87183801402/Uw0bMXA-G2YRcgQfL2K3RQ"
                    ],
                    "cats": [
                        {"cat_id": 1208},  # 宠物生活
                        {"cat_id": 1209},  # 宠物主粮
                        {"cat_id": 1215}   # 猫干粮
                    ],
                    "attrs": [
                        {"attr_key": "产品产地", "attr_value": "国产"},
                        {"attr_key": "保质期(天/月/年)", "attr_value": "18个月"},
                        {"attr_key": "配方", "attr_value": "膨化粮"},
                        {"attr_key": "净含量（kg）", "attr_value": weight}
                    ],
                    "express_info": {
                        "template_id": "947963164004",
                        "weight": 0
                    },
                    "skus": [{
                        "price": price,
                        "stock_num": 100,
                        "sku_code": f"AI{int(time.time())}",
                        "sku_attrs": [{"attr_key": "重量", "attr_value": weight}]
                    }],
                    "brand_id": "2100000000",
                    "product_type": 1
                }
            }
            
            resp = requests.post(add_url, json=add_data, timeout=30)
            wechat_result = resp.json()
            
            if wechat_result.get("errcode") == 0:
                wechat_product_id = wechat_result.get("product_id")
                # 上架商品
                listing_url = f"https://api.weixin.qq.com/channels/ec/product/listing?access_token={token}"
                requests.post(listing_url, json={"product_id": wechat_product_id, "status": 2}, timeout=30)
            else:
                wechat_error = wechat_result.get("errmsg", "微信上传失败")
        except Exception as e:
            wechat_error = str(e)
        
        return jsonify({
            "success": True, 
            "product": {
                "id": new_product.id,
                "name": new_product.name,
                "price": new_product.sale_price,
                "local": "✅ 本地创建成功",
                "wechat": f"✅ 微信小店ID: {wechat_product_id}" if wechat_product_id else f"❌ 微信上传失败: {wechat_error}"
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/ai_listing')
def ai_listing_page():
    return render_template('ai_listing.html')

@app.route('/product/add')
def product_add_page():
    return render_template('product_add.html')

@app.route('/api/products/add', methods=['POST'])
def api_product_add():
    """商品上架API - 支持本地和微信小店"""
    try:
        data = request.get_json()
        
        name = data.get('name', '').strip()
        price = data.get('price', 0)
        
        if not name or price <= 0:
            return jsonify({"success": False, "error": "请填写商品名称和价格"}), 400
        
        result = {
            "local_id": None,
            "wechat_id": None,
            "wechat_error": None
        }
        
        # 上架到本地
        if data.get('publish_local', True):
            store = Store.query.first()
            if not store:
                store = Store(name="默认店铺", code="default")
                db.session.add(store)
                db.session.flush()
            
            product = Product(
                store_id=store.id,
                name=name[:200],
                title=data.get('title', name)[:300],
                sku_code=f"PROD{int(time.time())}",
                sale_price=price,
                status='active',
                description=data.get('description', ''),
                main_image=data.get('image_url', '')
            )
            db.session.add(product)
            db.session.commit()
            result['local_id'] = product.id
            result['name'] = product.name
            result['price'] = product.sale_price
        
        # 上架到微信小店
        if data.get('publish_wechat', True):
            try:
                from wechat_shop_api import WechatShopAPI
                shop_api = WechatShopAPI()
                
                wechat_data = {
                    "product_type": 0,
                    "name": name,
                    "sku_list": [{
                        "price": int(price * 100),
                        "stock_num": 100,
                        "sku_code": f"PROD{int(time.time())}"
                    }],
                    "category_id": int(data.get('category', 0)) if data.get('category') else 0
                }
                
                wx_result = shop_api.create_product(wechat_data)
                if wx_result.get("errcode") == 0:
                    result['wechat_id'] = wx_result.get("product_id")
                else:
                    result['wechat_error'] = wx_result.get("errmsg", "上传失败")
            except Exception as e:
                result['wechat_error'] = str(e)
        
        return jsonify({"success": True, "product": result})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500



if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
