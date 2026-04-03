"""
供应链管理路由 - Supply Chain Routes
提供供应链管理平台的全部页面和API接口
"""

from flask import Blueprint, render_template, jsonify, request
from datetime import datetime
import json

# 创建蓝图
supply_chain_bp = Blueprint('supply_chain', __name__, url_prefix='/supply_chain')

# 懒加载供应链数据
_supply_chain_data = None

def get_data():
    global _supply_chain_data
    if _supply_chain_data is None:
        from supply_chain_agent import get_supply_chain_data
        _supply_chain_data = get_supply_chain_data()
    return _supply_chain_data


def refresh_data():
    """强制刷新数据"""
    global _supply_chain_data
    from supply_chain_agent import get_supply_chain_data
    _supply_chain_data = get_supply_chain_data()
    return _supply_chain_data


# ==================== 页面路由 ====================

@supply_chain_bp.route('/dashboard')
def dashboard():
    """供应链总览仪表盘"""
    data = get_data()
    decision_engine = data["decision_engine"]
    summary = decision_engine.get_decision_summary()
    kpis = summary["kpis"]
    alerts = data["analyzer"].analyze_inventory_status()
    
    # 供应链风险
    risks = data["analyzer"].get_supply_risks()
    
    # 获取真实微信小店商品
    wechat_products = []
    wechat_error = None
    try:
        from wechat_shop_api import WechatShopAPI
        shop_api = WechatShopAPI()
        raw_products = shop_api.get_all_products()
        for p in raw_products[:20]:
            price = p.get("min_price", 0) / 100 if p.get("min_price") else 0
            sold = p.get("total_sold_num", 0)
            status = p.get("status", 0)
            wechat_products.append({
                "title": (p.get("title") or p.get("name", "未命名"))[:40],
                "price": price,
                "sold": sold,
                "status": "在售" if status == 5 else "已下架" if status == 11 else "未知",
                "stock": p.get("stock_num", "未知"),
            })
    except Exception as e:
        err_msg = str(e)
        wechat_error = err_msg
        # 截取关键信息
        if "ip" in err_msg.lower() and "whitelist" in err_msg.lower():
            wechat_error = "IP未在微信后台白名单"
        elif "access_token" in err_msg:
            wechat_error = "access_token无效或已过期"
        elif "invalid" in err_msg:
            wechat_error = "微信API调用权限不足"
        else:
            wechat_error = err_msg[:80]
    
    return render_template(
        "supply_chain/dashboard.html",
        kpis=kpis,
        alerts=alerts[:10],
        risks=risks,
        urgent_actions=summary["urgent_actions"],
        top_suppliers=summary["top_suppliers"],
        summary=summary,
        now=datetime.now(),
        wechat_products=wechat_products,
        wechat_error=wechat_error,
        competitive_data=data.get("competitive_data", {}),
        inventory=data["inventory"],
    )


@supply_chain_bp.route('/inventory')
def inventory_page():
    """库存分析页面"""
    data = get_data()
    analyzer = data["analyzer"]
    inventory = data["inventory"]
    kpis = analyzer.get_inventory_kpis()
    alerts = analyzer.analyze_inventory_status()
    
    return render_template(
        "supply_chain/inventory.html",
        inventory=inventory,
        kpis=kpis,
        alerts=alerts,
        categories=SupplyChainMockData.CATEGORIES if hasattr(SupplyChainMockData, 'CATEGORIES') else list(set(i["category"] for i in inventory)),
    )


@supply_chain_bp.route('/suppliers')
def suppliers_page():
    """供应商管理页面"""
    data = get_data()
    analyzer = data["analyzer"]
    suppliers = analyzer.analyze_suppliers()
    risks = analyzer.get_supply_risks()
    recommendations = data["decision_engine"].get_supplier_recommendations()
    
    return render_template(
        "supply_chain/suppliers.html",
        suppliers=suppliers,
        recommendations=recommendations,
        risks=risks,
        total_suppliers=len(suppliers),
    )


@supply_chain_bp.route('/decisions')
def decisions_page():
    """AI决策建议页面"""
    data = get_data()
    engine = data["decision_engine"]
    
    reorder = engine.get_reorder_recommendations()
    predictions = engine.get_stockout_prediction()
    cost_opt = engine.get_cost_optimization_suggestions()
    supplier_rec = engine.get_supplier_recommendations()
    
    return render_template(
        "supply_chain/decisions.html",
        reorder=reorder,
        predictions=predictions,
        cost_optimizations=cost_opt,
        supplier_recommendations=supplier_rec,
        total_recommendations=len(reorder) + len(predictions) + len(cost_opt),
    )


@supply_chain_bp.route('/analysis')
def analysis_page():
    """供应链深度分析页面"""
    data = get_data()
    analyzer = data["analyzer"]
    
    kpis = analyzer.get_inventory_kpis()
    costs = analyzer.analyze_costs()
    logistics = analyzer.analyze_logistics()
    supplier_analysis = analyzer.analyze_suppliers()
    
    return render_template(
        "supply_chain/analysis.html",
        kpis=kpis,
        costs=costs,
        logistics=logistics,
        suppliers=supplier_analysis,
    )


@supply_chain_bp.route('/logistics')
def logistics_page():
    """物流跟踪页面"""
    data = get_data()
    logistics = data["analyzer"].analyze_logistics()
    all_logistics = data["logistics"]
    
    return render_template(
        "supply_chain/logistics.html",
        logistics_summary=logistics,
        all_logistics=all_logistics,
    )


# ==================== API接口 ====================

@supply_chain_bp.route('/api/dashboard')
def api_dashboard():
    """仪表盘数据API"""
    data = get_data()
    summary = data["decision_engine"].get_decision_summary()
    return jsonify({"success": True, "data": summary})


@supply_chain_bp.route('/api/inventory')
def api_inventory():
    """库存数据API"""
    data = get_data()
    category = request.args.get("category")
    inventory = data["inventory"]
    
    if category:
        inventory = [i for i in inventory if i["category"] == category]
    
    return jsonify({
        "success": True,
        "data": inventory,
        "total": len(inventory),
    })


@supply_chain_bp.route('/api/inventory/alerts')
def api_inventory_alerts():
    """库存预警API"""
    data = get_data()
    alerts = data["analyzer"].analyze_inventory_status()
    return jsonify({
        "success": True,
        "data": alerts,
        "total": len(alerts),
    })


@supply_chain_bp.route('/api/kpis')
def api_kpis():
    """KPI指标API"""
    data = get_data()
    kpis = data["analyzer"].get_inventory_kpis()
    return jsonify({"success": True, "data": kpis})


@supply_chain_bp.route('/api/suppliers')
def api_suppliers():
    """供应商数据API"""
    data = get_data()
    suppliers = data["analyzer"].analyze_suppliers()
    return jsonify({
        "success": True,
        "data": suppliers,
        "total": len(suppliers),
    })


@supply_chain_bp.route('/api/logistics')
def api_logistics():
    """物流数据API"""
    data = get_data()
    logistics = data["analyzer"].analyze_logistics()
    return jsonify({"success": True, "data": logistics})


@supply_chain_bp.route('/api/decisions/reorder')
def api_reorder():
    """补货建议API"""
    data = get_data()
    reorder = data["decision_engine"].get_reorder_recommendations()
    return jsonify({
        "success": True,
        "data": reorder,
        "total": len(reorder),
    })


@supply_chain_bp.route('/api/decisions/stockout')
def api_stockout():
    """缺货预测API"""
    days = int(request.args.get("days", 14))
    data = get_data()
    predictions = data["decision_engine"].get_stockout_prediction(days_ahead=days)
    return jsonify({
        "success": True,
        "data": predictions,
        "total": len(predictions),
    })


@supply_chain_bp.route('/api/decisions/cost_optimization')
def api_cost_optimization():
    """成本优化建议API"""
    data = get_data()
    suggestions = data["decision_engine"].get_cost_optimization_suggestions()
    return jsonify({
        "success": True,
        "data": suggestions,
        "total": len(suggestions),
    })


@supply_chain_bp.route('/api/risks')
def api_risks():
    """供应链风险API"""
    data = get_data()
    risks = data["analyzer"].get_supply_risks()
    return jsonify({
        "success": True,
        "data": risks,
        "total": len(risks),
    })


@supply_chain_bp.route('/api/costs')
def api_costs():
    """成本分析API"""
    data = get_data()
    costs = data["analyzer"].analyze_costs()
    return jsonify({"success": True, "data": costs})


@supply_chain_bp.route('/api/refresh', methods=['POST'])
def api_refresh():
    """强制刷新数据"""
    data = refresh_data()
    return jsonify({"success": True, "message": "数据已刷新", "timestamp": datetime.now().isoformat()})


# ==================== 导出功能 ====================

@supply_chain_bp.route('/export/decisions')
def export_decisions():
    """导出决策建议（JSON格式）"""
    data = get_data()
    engine = data["decision_engine"]
    
    export_data = {
        "export_time": datetime.now().isoformat(),
        "reorder_recommendations": engine.get_reorder_recommendations(),
        "stockout_predictions": engine.get_stockout_prediction(),
        "cost_optimization": engine.get_cost_optimization_suggestions(),
        "supplier_recommendations": engine.get_supplier_recommendations(),
        "kpis": data["analyzer"].get_inventory_kpis(),
    }
    
    response = jsonify(export_data)
    response.headers["Content-Disposition"] = "attachment; filename=supply_chain_decisions.json"
    return response


@supply_chain_bp.route('/export/inventory')
def export_inventory():
    """导出现有库存（JSON格式）"""
    data = get_data()
    response = jsonify({
        "export_time": datetime.now().isoformat(),
        "inventory": data["inventory"],
        "alerts": data["analyzer"].analyze_inventory_status(),
    })
    response.headers["Content-Disposition"] = "attachment; filename=inventory_status.json"
    return response


# 临时引用，避免循环导入问题
from supply_chain_agent import SupplyChainMockData
