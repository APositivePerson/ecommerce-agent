from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
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
    """商品列表"""
    query = Product.query

    search = request.args.get('search', '')
    if search:
        query = query.filter(
            db.or_(
                Product.name.contains(search),
                Product.sku_code.contains(search),
                Product.title.contains(search),
                Product.keywords.contains(search)
            )
        )

    # 如果是店铺管理员，只能看到本店铺的商品
    if current_user.store_id:
        query = query.filter_by(store_id=current_user.store_id)

    # 按状态筛选
    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)

    # 按分类筛选
    category_id = request.args.get('category_id', type=int)
    if category_id:
        query = query.filter_by(category_id=category_id)

    # 筛选热门/新品/推荐
    is_hot = request.args.get('is_hot')
    if is_hot:
        query = query.filter_by(is_hot=True)

    is_new = request.args.get('is_new')
    if is_new:
        query = query.filter_by(is_new=True)

    is_recommend = request.args.get('is_recommend')
    if is_recommend:
        query = query.filter_by(is_recommend=True)

    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(Product.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    # 获取分类列表
    categories = Category.query.filter_by(status='active').order_by(Category.sort_order).all()

    return render_template('products/list.html', 
                           pagination=pagination, 
                           search=search, 
                           status=status,
                           categories=categories,
                           category_id=category_id,
                           is_hot=is_hot,
                           is_new=is_new,
                           is_recommend=is_recommend)


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


if __name__ == '__main__':
    with app.app_context():
        init_db()
        print("数据库初始化完成！")
    app.run(debug=True, host='0.0.0.0', port=5000)
