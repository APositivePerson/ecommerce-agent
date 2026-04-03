"""
供应链Agent模块 - Supply Chain Agent
提供供应链分析、库存优化、供应商管理、决策建议等功能
使用Mock数据，支持宠物用品电商场景
"""

import random
import math
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

# ==================== Mock数据生成器 ====================

class SupplyChainMockData:
    """供应链Mock数据生成器"""
    
    CATEGORIES = ["猫粮", "狗粮", "猫砂", "狗尿垫", "宠物零食", "宠物玩具", "宠物窝垫", "宠物洗护"]
    
    SUPPLIERS = [
        {"id": "S001", "name": "华东宠物食品供应商A", "category": "猫粮", "lead_time": 7, "moq": 100, "unit_cost": 25.0, "rating": 4.5, "reliability": 0.95, "location": "上海"},
        {"id": "S002", "name": "广州猫砂供应商B", "category": "猫砂", "lead_time": 5, "moq": 200, "unit_cost": 12.0, "rating": 4.2, "reliability": 0.92, "location": "广州"},
        {"id": "S003", "name": "山东宠物零食厂", "category": "宠物零食", "lead_time": 10, "moq": 50, "unit_cost": 8.5, "rating": 4.7, "reliability": 0.98, "location": "济南"},
        {"id": "S004", "name": "浙江宠物玩具厂", "category": "宠物玩具", "lead_time": 14, "moq": 30, "unit_cost": 15.0, "rating": 4.3, "reliability": 0.88, "location": "义乌"},
        {"id": "S005", "name": "河北狗粮供应商", "category": "狗粮", "lead_time": 8, "moq": 150, "unit_cost": 22.0, "rating": 4.1, "reliability": 0.90, "location": "石家庄"},
        {"id": "S006", "name": "江苏宠物窝垫厂", "category": "宠物窝垫", "lead_time": 12, "moq": 20, "unit_cost": 35.0, "rating": 4.6, "reliability": 0.93, "location": "苏州"},
        {"id": "S007", "name": "成都宠物洗护供应商", "category": "宠物洗护", "lead_time": 6, "moq": 80, "unit_cost": 18.0, "rating": 4.4, "reliability": 0.91, "location": "成都"},
        {"id": "S008", "name": "深圳宠物用品批发", "category": "狗尿垫", "lead_time": 4, "moq": 500, "unit_cost": 0.8, "rating": 4.0, "reliability": 0.87, "location": "深圳"},
    ]
    
    SKU_TEMPLATES = {
        "猫粮": [
            ("CAT_FOOD_001", "鸡肉味猫粮2kg", 25.0, "S001"),
            ("CAT_FOOD_002", "三文鱼猫粮1.5kg", 32.0, "S001"),
            ("CAT_FOOD_003", "海洋鱼猫粮5kg", 68.0, "S001"),
            ("CAT_FOOD_004", "幼猫奶糕1kg", 28.0, "S001"),
        ],
        "狗粮": [
            ("DOG_FOOD_001", "牛肉味狗粮10kg", 85.0, "S005"),
            ("DOG_FOOD_002", "鸡肉味狗粮5kg", 48.0, "S005"),
            ("DOG_FOOD_003", "大型犬专用粮15kg", 120.0, "S005"),
        ],
        "猫砂": [
            ("CAT_LITTER_001", "豆腐猫砂6L", 28.0, "S002"),
            ("CAT_LITTER_002", "膨润土猫砂10kg", 32.0, "S002"),
            ("CAT_LITTER_003", "水晶猫砂4L", 45.0, "S002"),
        ],
        "宠物零食": [
            ("SNACK_001", "鸡肉冻干50g", 35.0, "S003"),
            ("SNACK_002", "牛肉粒100g", 28.0, "S003"),
            ("SNACK_003", "猫条12支装", 22.0, "S003"),
            ("SNACK_004", "洁齿骨20根装", 38.0, "S003"),
        ],
        "宠物玩具": [
            ("TOY_001", "逗猫棒套装", 25.0, "S004"),
            ("TOY_002", "宠物飞盘", 18.0, "S004"),
            ("TOY_003", "猫爬架大型", 128.0, "S004"),
        ],
        "宠物窝垫": [
            ("BED_001", "圆形猫窝", 68.0, "S006"),
            ("BED_002", "狗窝中号", 88.0, "S006"),
            ("BED_003", "宠物凉席垫", 45.0, "S006"),
        ],
        "宠物洗护": [
            ("CARE_001", "宠物沐浴露500ml", 36.0, "S007"),
            ("CARE_002", "宠物护毛素300ml", 28.0, "S007"),
            ("CARE_003", "宠物牙膏套装", 42.0, "S007"),
        ],
        "狗尿垫": [
            ("PAD_001", "狗尿垫中号50片", 48.0, "S008"),
            ("PAD_002", "狗尿垫大号100片", 85.0, "S008"),
        ],
    }
    
    @classmethod
    def generate_inventory(cls, seed: int = 42) -> List[Dict]:
        """生成完整的库存数据"""
        random.seed(seed)
        inventory = []
        for category, skus in cls.SKU_TEMPLATES.items():
            for sku_code, name, unit_cost, supplier_id in skus:
                supplier = next(s for s in cls.SUPPLIERS if s["id"] == supplier_id)
                # 随机生成库存数据，添加一些预警情况
                demand_daily = random.randint(5, 30)
                safety_stock = int(demand_daily * supplier["lead_time"] * 0.5)
                reorder_point = int(demand_daily * supplier["lead_time"] * 0.8)
                
                # 随机生成库存量，约10%为预警或缺货
                roll = random.random()
                if roll < 0.05:
                    stock = random.randint(0, safety_stock // 2)  # 缺货
                elif roll < 0.12:
                    stock = random.randint(safety_stock // 2, safety_stock)  # 低于安全库存
                else:
                    stock = random.randint(reorder_point, reorder_point * 3)
                
                inventory.append({
                    "sku": sku_code,
                    "name": name,
                    "category": category,
                    "supplier_id": supplier_id,
                    "supplier_name": supplier["name"],
                    "stock": stock,
                    "safety_stock": safety_stock,
                    "reorder_point": reorder_point,
                    "demand_daily": demand_daily,
                    "unit_cost": unit_cost,
                    "lead_time": supplier["lead_time"],
                    "location": f"仓库{random.choice(['A', 'B', 'C'])}-{random.randint(1,20)}",
                })
        return inventory
    
    @classmethod
    def generate_logistics(cls, inventory: List[Dict], seed: int = 42) -> List[Dict]:
        """生成物流数据"""
        random.seed(seed)
        logistics = []
        statuses = ["运输中", "已发货", "配送中", "已到达", "清关中"]
        carriers = ["顺丰速运", "中通快递", "圆通速递", "京东物流", "德邦物流"]
        
        for item in inventory:
            supplier = next((s for s in cls.SUPPLIERS if s["id"] == item["supplier_id"]), None)
            moq = supplier["moq"] if supplier else 50
            if random.random() < 0.6:  # 60%有在途订单
                qty = random.randint(max(50, moq // 2), 300)
                order_date = datetime.now() - timedelta(days=random.randint(1, item["lead_time"] - 1))
                eta = order_date + timedelta(days=item["lead_time"])
                
                logistics.append({
                    "order_id": f"PO{int(random.random()*100000):05d}",
                    "sku": item["sku"],
                    "name": item["name"],
                    "supplier_id": item["supplier_id"],
                    "quantity": qty,
                    "order_date": order_date.strftime("%Y-%m-%d"),
                    "eta": eta.strftime("%Y-%m-%d"),
                    "status": random.choice(statuses),
                    "carrier": random.choice(carriers),
                    "cost": qty * item["unit_cost"] * 1.05,  # 含运费
                })
        return logistics
    
    @classmethod
    def generate_orders(cls, inventory: List[Dict], days: int = 30, seed: int = 42) -> List[Dict]:
        """生成历史订单数据"""
        random.seed(seed)
        orders = []
        for item in inventory:
            for d in range(days):
                if random.random() < 0.3:  # 30%天数有订单
                    qty = random.randint(1, 5)
                    date = datetime.now() - timedelta(days=days-d)
                    orders.append({
                        "date": date.strftime("%Y-%m-%d"),
                        "sku": item["sku"],
                        "name": item["name"],
                        "category": item["category"],
                        "quantity": qty,
                        "unit_price": item["unit_cost"] * 1.8,  # 售价是成本的1.8倍
                        "cost": qty * item["unit_cost"],
                    })
        return orders


# ==================== 供应链分析器 ====================

class SupplyChainAnalyzer:
    """供应链分析器"""
    
    def __init__(self, inventory: List[Dict], orders: List[Dict] = None, logistics: List[Dict] = None):
        self.inventory = inventory
        self.orders = orders or []
        self.logistics = logistics or []
        self.suppliers = SupplyChainMockData.SUPPLIERS
    
    # ---- 库存分析 ----
    
    def analyze_inventory_status(self) -> List[Dict]:
        """分析库存状态，返回预警列表"""
        alerts = []
        for item in self.inventory:
            status = "normal"
            alert_type = None
            
            if item["stock"] <= 0:
                status = "critical"
                alert_type = "stockout"
            elif item["stock"] < item["safety_stock"]:
                status = "danger"
                alert_type = "below_safety"
            elif item["stock"] < item["reorder_point"]:
                status = "warning"
                alert_type = "below_reorder"
            
            if alert_type:
                alerts.append({
                    "sku": item["sku"],
                    "name": item["name"],
                    "category": item["category"],
                    "status": status,
                    "alert_type": alert_type,
                    "stock": item["stock"],
                    "safety_stock": item["safety_stock"],
                    "reorder_point": item["reorder_point"],
                    "demand_daily": item["demand_daily"],
                    "days_until_stockout": item["stock"] / item["demand_daily"] if item["demand_daily"] > 0 else 0,
                    "suggestion": self._get_suggestion(item, alert_type),
                })
        
        return sorted(alerts, key=lambda x: (
            {"critical": 0, "danger": 1, "warning": 2}.get(x["status"], 3),
            -x["days_until_stockout"]
        ))
    
    def _get_suggestion(self, item: Dict, alert_type: str) -> str:
        if alert_type == "stockout":
            return f"⚠️ 立即补货！当前库存为0，建议联系{S[item['supplier_id']]['name']}紧急订货{item['moq'] if 'moq' in item else 100}件以上"
        elif alert_type == "below_safety":
            days_left = item["stock"] / item["demand_daily"] if item["demand_daily"] > 0 else 0
            return f"🔴 库存低于安全库存！剩余{days_left:.0f}天库存，建议立即下单补充"
        else:
            return f"🟡 库存接近补货点，建议在{item['lead_time']}天内完成补货"
    
    def calculate_eoq(self, item: Dict, ordering_cost: float = 50.0, holding_rate: float = 0.2) -> float:
        """计算经济订货量 EOQ = sqrt(2 * D * S / H)"""
        # D = 年需求量 (demand_daily * 365)
        D = item["demand_daily"] * 365
        S = ordering_cost  # 每次订货成本
        H = item["unit_cost"] * holding_rate  # 年持有成本率
        
        eoq = math.sqrt(2 * D * S / H)
        return round(eoq, 0)
    
    def calculate_safety_stock(self, item: Dict, service_level: float = 0.95) -> float:
        """计算安全库存（基于服务水平）"""
        # 使用简单公式: SS = z * sigma_demand * sqrt(lead_time)
        # 假设需求变异系数为30%，lead_time天
        z = {0.90: 1.28, 0.95: 1.65, 0.99: 2.33}.get(service_level, 1.65)
        sigma_demand = item["demand_daily"] * 0.3  # 30%需求波动
        ss = z * sigma_demand * math.sqrt(item["lead_time"])
        return round(ss, 0)
    
    def get_inventory_kpis(self) -> Dict:
        """计算库存KPI指标"""
        total_value = sum(item["stock"] * item["unit_cost"] for item in self.inventory)
        total_safety = sum(item["safety_stock"] * item["unit_cost"] for item in self.inventory)
        
        # 各类别库存价值
        by_category = {}
        for item in self.inventory:
            cat = item["category"]
            if cat not in by_category:
                by_category[cat] = {"count": 0, "value": 0, "items": 0}
            by_category[cat]["count"] += item["stock"]
            by_category[cat]["value"] += item["stock"] * item["unit_cost"]
            by_category[cat]["items"] += 1
        
        # 预警商品
        alerts = self.analyze_inventory_status()
        critical = sum(1 for a in alerts if a["status"] == "critical")
        danger = sum(1 for a in alerts if a["status"] == "danger")
        warning = sum(1 for a in alerts if a["status"] == "warning")
        
        # 在途订单
        in_transit_value = sum(l["cost"] for l in self.logistics)
        
        return {
            "total_inventory_value": round(total_value, 2),
            "total_safety_stock_value": round(total_safety, 2),
            "in_transit_value": round(in_transit_value, 2),
            "total_skus": len(self.inventory),
            "critical_items": critical,
            "danger_items": danger,
            "warning_items": warning,
            "healthy_items": len(self.inventory) - critical - danger - warning,
            "by_category": by_category,
        }
    
    # ---- 供应商分析 ----
    
    def analyze_suppliers(self) -> List[Dict]:
        """分析供应商绩效"""
        results = []
        
        for supplier in self.suppliers:
            # 找到该供应商的所有SKU
            supplier_items = [i for i in self.inventory if i["supplier_id"] == supplier["id"]]
            
            if not supplier_items:
                continue
            
            # 计算依赖度（该供应商SKU占总SKU的比例）
            dependency = len(supplier_items) / len(self.inventory) * 100
            
            # 计算库存占比
            stock_value = sum(i["stock"] * i["unit_cost"] for i in supplier_items)
            total_stock = sum(i["stock"] * i["unit_cost"] for i in self.inventory)
            stock_ratio = stock_value / total_stock * 100 if total_stock > 0 else 0
            
            # 预警风险
            risk_skus = [i for i in supplier_items if i["stock"] < i["reorder_point"]]
            
            # 综合评分
            score = (
                supplier["rating"] * 0.3 +
                supplier["reliability"] * 100 * 0.4 +
                (5 - min(supplier["lead_time"], 5)) * 10 * 0.2 +  # 交期越短越好
                (100 - min(dependency, 100)) * 0.1  # 依赖度越低越好
            )
            
            results.append({
                "id": supplier["id"],
                "name": supplier["name"],
                "category": supplier["category"],
                "location": supplier["location"],
                "lead_time": supplier["lead_time"],
                "unit_cost": supplier["unit_cost"],
                "rating": supplier["rating"],
                "reliability": supplier["reliability"],
                "moq": supplier["moq"],
                "sku_count": len(supplier_items),
                "dependency": round(dependency, 1),
                "stock_ratio": round(stock_ratio, 1),
                "risk_skus": len(risk_skus),
                "score": round(score, 1),
                "risk_level": "high" if dependency > 30 else "medium" if dependency > 15 else "low",
            })
        
        return sorted(results, key=lambda x: -x["score"])
    
    def get_supply_risks(self) -> List[Dict]:
        """识别供应链风险"""
        risks = []
        
        # 检查单一供应商依赖
        category_suppliers = {}
        for item in self.inventory:
            cat = item["category"]
            if cat not in category_suppliers:
                category_suppliers[cat] = set()
            category_suppliers[cat].add(item["supplier_id"])
        
        for cat, suppliers in category_suppliers.items():
            if len(suppliers) == 1:
                supplier = suppliers.pop()
                supplier_name = next((s["name"] for s in self.suppliers if s["id"] == supplier), supplier)
                risks.append({
                    "type": "single_source",
                    "category": cat,
                    "severity": "high",
                    "description": f"类别'{cat}'仅有一个供应商{supplier_name}，存在供应中断风险",
                    "suggestion": f"建议开发备用供应商，降低对单一供应商的依赖",
                })
        
        # 检查长交期供应商
        for supplier in self.suppliers:
            if supplier["lead_time"] > 10:
                risks.append({
                    "type": "long_lead_time",
                    "supplier": supplier["name"],
                    "severity": "medium",
                    "description": f"供应商{supplier["name"]}交期长达{supplier['lead_time']}天",
                    "suggestion": "建议保持更高安全库存或寻找交期更短的替代供应商",
                })
        
        return risks
    
    # ---- 物流分析 ----
    
    def analyze_logistics(self) -> Dict:
        """分析物流状态"""
        if not self.logistics:
            return {"total_orders": 0, "total_cost": 0, "avg_cost": 0, "by_status": {}}
        
        total_cost = sum(l["cost"] for l in self.logistics)
        total_qty = sum(l["quantity"] for l in self.logistics)
        
        by_status = {}
        for l in self.logistics:
            status = l["status"]
            if status not in by_status:
                by_status[status] = {"count": 0, "cost": 0, "quantity": 0}
            by_status[status]["count"] += 1
            by_status[status]["cost"] += l["cost"]
            by_status[status]["quantity"] += l["quantity"]
        
        # 检查即将到达的订单
        arriving = []
        today = datetime.now().date()
        for l in self.logistics:
            eta = datetime.strptime(l["eta"], "%Y-%m-%d").date()
            days_until = (eta - today).days
            if 0 <= days_until <= 3:
                arriving.append({**l, "days_until": days_until})
        
        return {
            "total_orders": len(self.logistics),
            "total_cost": round(total_cost, 2),
            "total_quantity": total_qty,
            "avg_cost_per_order": round(total_cost / len(self.logistics), 2),
            "by_status": by_status,
            "arriving_soon": arriving,
        }
    
    # ---- 成本分析 ----
    
    def analyze_costs(self) -> Dict:
        """分析供应链成本"""
        # 采购成本
        purchase_cost = sum(item["stock"] * item["unit_cost"] for item in self.inventory)
        
        # 在途采购成本
        transit_cost = sum(l["cost"] for l in self.logistics)
        
        # 持有成本（年销售额的20%估算）
        holding_cost = purchase_cost * 0.2
        
        # 缺货成本估算
        alerts = self.analyze_inventory_status()
        stockout_cost = sum(
            a["demand_daily"] * a["unit_cost"] * 3  # 假设每次缺货损失3天销量
            for a in alerts if a["alert_type"] == "stockout"
        )
        
        # 各类别成本分布
        by_category = {}
        for item in self.inventory:
            cat = item["category"]
            if cat not in by_category:
                by_category[cat] = {"purchase": 0, "holding": 0, "items": 0}
            by_category[cat]["purchase"] += item["stock"] * item["unit_cost"]
            by_category[cat]["holding"] += item["stock"] * item["unit_cost"] * 0.2
            by_category[cat]["items"] += 1
        
        return {
            "total_inventory_value": round(purchase_cost, 2),
            "in_transit_cost": round(transit_cost, 2),
            "estimated_annual_holding_cost": round(holding_cost, 2),
            "estimated_stockout_cost": round(stockout_cost, 2),
            "total_potential_cost": round(purchase_cost + holding_cost + stockout_cost, 2),
            "by_category": by_category,
        }


# ==================== 决策引擎 ====================

class SupplyChainDecisionEngine:
    """供应链决策引擎"""
    
    def __init__(self, inventory: List[Dict], orders: List[Dict], logistics: List[Dict]):
        self.analyzer = SupplyChainAnalyzer(inventory, orders, logistics)
        self.inventory = inventory
        self.orders = orders
        self.logistics = logistics
        self.suppliers = SupplyChainMockData.SUPPLIERS
    
    def get_reorder_recommendations(self) -> List[Dict]:
        """获取补货建议"""
        recommendations = []
        alerts = self.analyzer.analyze_inventory_status()
        
        for alert in alerts:
            item = next(i for i in self.inventory if i["sku"] == alert["sku"])
            supplier = next(s for s in self.suppliers if s["id"] == item["supplier_id"])
            
            # 计算建议补货量 (EOQ或MOQ，取较大值)
            eoq = self.analyzer.calculate_eoq(item)
            suggested_qty = max(eoq, supplier["moq"])
            
            # 如果库存为0，建议紧急补货
            urgency = "high" if alert["status"] == "critical" else "medium" if alert["status"] == "danger" else "normal"
            
            # 计算预期成本
            estimated_cost = suggested_qty * supplier["unit_cost"] * 1.05
            
            recommendations.append({
                "sku": item["sku"],
                "name": item["name"],
                "category": item["category"],
                "current_stock": item["stock"],
                "suggested_qty": int(suggested_qty),
                "urgency": urgency,
                "supplier_id": supplier["id"],
                "supplier_name": supplier["name"],
                "unit_cost": supplier["unit_cost"],
                "estimated_cost": round(estimated_cost, 2),
                "lead_time": supplier["lead_time"],
                "reason": alert["suggestion"],
                "priority": 1 if urgency == "high" else 2 if urgency == "medium" else 3,
            })
        
        return sorted(recommendations, key=lambda x: x["priority"])
    
    def get_supplier_recommendations(self, category: str = None) -> List[Dict]:
        """获取供应商推荐"""
        supplier_scores = self.analyzer.analyze_suppliers()
        
        recommendations = []
        for s in supplier_scores:
            if category and s["category"] != category:
                continue
            
            pros = []
            cons = []
            
            if s["rating"] >= 4.5:
                pros.append("供应商评分高(4.5+)")
            if s["reliability"] >= 0.95:
                pros.append("可靠性优秀(95%+)")
            if s["lead_time"] <= 7:
                pros.append("交期短(≤7天)")
            elif s["lead_time"] > 10:
                cons.append("交期较长")
            if s["risk_level"] == "high":
                cons.append("对该供应商依赖度过高")
            if s["unit_cost"] > 30:
                cons.append("单价较高")
            
            recommendations.append({
                **s,
                "pros": pros,
                "cons": cons,
                "overall_rating": "★★★★★" if s["score"] >= 80 else "★★★★☆" if s["score"] >= 60 else "★★★☆☆",
            })
        
        return sorted(recommendations, key=lambda x: -x["score"])
    
    def get_cost_optimization_suggestions(self) -> List[Dict]:
        """获取成本优化建议"""
        suggestions = []
        
        # 检查库存周转
        alerts = self.analyzer.analyze_inventory_status()
        
        # 高库存预警（库存超过90天销量）
        for item in self.inventory:
            days_of_stock = item["stock"] / item["demand_daily"] if item["demand_daily"] > 0 else 999
            if days_of_stock > 90:
                capital_occupied = item["stock"] * item["unit_cost"]
                suggestions.append({
                    "type": "overstock",
                    "severity": "medium",
                    "sku": item["sku"],
                    "name": item["name"],
                    "description": f"库存过高：当前库存可供{days_of_stock:.0f}天销售",
                    "capital_occupied": round(capital_occupied, 2),
                    "suggestion": "考虑促销清仓或减少后续采购量，释放占用资金",
                })
        
        # 低库存风险
        for alert in alerts:
            if alert["status"] in ["critical", "danger"]:
                item = next(i for i in self.inventory if i["sku"] == alert["sku"])
                suggestions.append({
                    "type": "stockout_risk",
                    "severity": "high" if alert["status"] == "critical" else "medium",
                    "sku": item["sku"],
                    "name": item["name"],
                    "description": f"库存不足，预计{alert['days_until_stockout']:.0f}天后缺货",
                    "at_risk_amount": round(alert["demand_daily"] * 3 * item["unit_cost"], 2),
                    "suggestion": "立即补充库存，避免缺货损失",
                })
        
        # 物流成本优化
        logistics_summary = self.analyzer.analyze_logistics()
        if logistics_summary["total_orders"] > 5:
            suggestions.append({
                "type": "logistics_consolidation",
                "severity": "low",
                "description": f"当前有{logistics_summary['total_orders']}个在途订单，建议整合发货以降低物流成本",
                "potential_savings": round(logistics_summary["total_cost"] * 0.1, 2),
                "suggestion": "与供应商协商合并发货计划",
            })
        
        return sorted(suggestions, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x["severity"], 3))
    
    def get_stockout_prediction(self, days_ahead: int = 14) -> List[Dict]:
        """预测未来可能缺货的商品"""
        predictions = []
        
        for item in self.inventory:
            days_until_stockout = item["stock"] / item["demand_daily"] if item["demand_daily"] > 0 else 999
            
            if days_until_stockout <= days_ahead:
                # 检查是否有在途订单
                in_transit = [l for l in self.logistics if l["sku"] == item["sku"]]
                
                predictions.append({
                    "sku": item["sku"],
                    "name": item["name"],
                    "category": item["category"],
                    "current_stock": item["stock"],
                    "demand_daily": item["demand_daily"],
                    "days_until_stockout": round(days_until_stockout, 1),
                    "stockout_date": (datetime.now() + timedelta(days=days_until_stockout)).strftime("%Y-%m-%d"),
                    "in_transit_qty": sum(l["quantity"] for l in in_transit),
                    "risk_level": "critical" if days_until_stockout < 3 else "high" if days_until_stockout < 7 else "medium",
                    "recommended_action": "立即下单" if days_until_stockout < 3 else f"未来{days_ahead}天内安排补货",
                })
        
        return sorted(predictions, key=lambda x: x["days_until_stockout"])
    
    def get_decision_summary(self) -> Dict:
        """获取决策摘要（用于Dashboard）"""
        reorder = self.get_reorder_recommendations()
        predictions = self.get_stockout_prediction()
        cost_opt = self.get_cost_optimization_suggestions()
        kpis = self.analyzer.get_inventory_kpis()
        supplier_scores = self.analyzer.analyze_suppliers()
        risks = self.analyzer.get_supply_risks()
        
        # 行动优先级
        actions = []
        for r in reorder[:5]:
            actions.append({"type": "reorder", "priority": r["priority"], "description": f"补货: {r['name']} x{r['suggested_qty']}", "urgency": r["urgency"]})
        for p in predictions[:3]:
            actions.append({"type": "stockout_alert", "priority": 0 if p["risk_level"] == "critical" else 1, "description": f"缺货预警: {p['name']}", "urgency": p["risk_level"]})
        for c in cost_opt[:2]:
            actions.append({"type": "cost_optimization", "priority": 2, "description": f"成本优化: {c.get('name', c['type'])}", "urgency": c["severity"]})
        
        return {
            "kpis": kpis,
            "pending_reorders": len(reorder),
            "stockout_risks": len(predictions),
            "cost_optimization_opportunities": len(cost_opt),
            "supply_risks": len(risks),
            "top_suppliers": supplier_scores[:3],
            "urgent_actions": sorted(actions, key=lambda x: x["priority"])[:8],
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }


# ==================== JD竞品数据处理器 ====================

class JDCompetitorProcessor:
    """JD竞品数据处理（用于供应链决策参考）"""
    
    def __init__(self, jd_products_path: str = None):
        self.jd_products_path = jd_products_path or "competitor_analysis/jd_products_v3.json"
    
    def load_jd_data(self) -> List[Dict]:
        """加载JD竞品数据"""
        import json
        import os
        
        path = os.path.join(os.path.dirname(__file__), self.jd_products_path)
        if not os.path.exists(path):
            return []
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "products" in data:
                return data["products"]
            return []
        except Exception:
            return []
    
    def get_price_positioning(self) -> Dict:
        """获取价格定位分析"""
        products = self.load_jd_data()
        if not products:
            return {"low": [], "mid": [], "high": [], "avg_price": 0}
        
        prices = [p.get("price", 0) for p in products if p.get("price", 0) > 0]
        if not prices:
            return {"low": [], "mid": [], "high": [], "avg_price": 0}
        
        avg_price = sum(prices) / len(prices)
        
        return {
            "low": [p for p in products if 0 < p.get("price", 0) < avg_price * 0.7],
            "mid": [p for p in products if avg_price * 0.7 <= p.get("price", 0) <= avg_price * 1.3],
            "high": [p for p in products if p.get("price", 0) > avg_price * 1.3],
            "avg_price": round(avg_price, 2),
            "total_products": len(products),
        }
    
    def get_competitive_insights(self) -> List[Dict]:
        """获取竞品洞察"""
        products = self.load_jd_data()
        insights = []
        
        # 按类别分析
        by_category = {}
        for p in products:
            cat = p.get("category", "未知")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(p)
        
        for cat, items in by_category.items():
            prices = [i.get("price", 0) for i in items if i.get("price", 0) > 0]
            if not prices:
                continue
            
            insights.append({
                "category": cat,
                "product_count": len(items),
                "avg_price": round(sum(prices) / len(prices), 2),
                "min_price": min(prices),
                "max_price": max(prices),
                "top_products": sorted(items, key=lambda x: x.get("price", 0), reverse=True)[:3],
            })
        
        return insights


# ==================== 便捷函数 ====================

def get_supply_chain_data():
    """获取完整的供应链数据（便捷入口）
    优先使用微信小店真实商品，mock数据仅用于补充供应链分析维度
    """
    # 尝试从微信小店获取真实商品作为库存基础
    wechat_inventory = _build_inventory_from_wechat()
    
    if wechat_inventory:
        inventory = wechat_inventory
    else:
        inventory = SupplyChainMockData.generate_inventory()
    
    # 加载竞品分析数据
    competitive_data = _load_competitive_analysis()
    
    # 为每个商品匹配竞品数据
    for item in inventory:
        comp = _match_competitor(item, competitive_data)
        item["competitor"] = comp
    
    logistics = SupplyChainMockData.generate_logistics(inventory)
    orders = SupplyChainMockData.generate_orders(inventory, days=30)
    
    analyzer = SupplyChainAnalyzer(inventory, orders, logistics)
    decision_engine = SupplyChainDecisionEngine(inventory, orders, logistics)
    
    return {
        "inventory": inventory,
        "logistics": logistics,
        "orders": orders,
        "suppliers": SupplyChainMockData.SUPPLIERS,
        "analyzer": analyzer,
        "decision_engine": decision_engine,
        "source": "wechat" if wechat_inventory else "mock",
        "competitive_data": competitive_data,
    }


def _load_competitive_analysis():
    """加载已有竞品分析数据
    优先级：jd_competitors_local.json（本地精准抓取） > decision_analysis.json
    """
    import json, os
    base = os.path.dirname(__file__)

    # 优先用本地抓取的精准数据（v4版本）
    local_path = os.path.join(base, "competitor_analysis", "jd_competitors_local.json")
    try:
        if os.path.exists(local_path):
            with open(local_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            # v4格式：直接有analyzed数组，每个元素含wechat_title和competitors
            if 'analyzed' in raw and raw['analyzed']:
                product_analysis = []
                for item in raw['analyzed']:
                    pa = {
                        'title': item.get('wechat_title', ''),
                        'keyword': item.get('search_kw', ''),
                        'price_score': item.get('price_position', ''),
                        'avg_price': item.get('avg_price', 0),
                        'competitors': [
                            {'name': c['title'], 'price': c['price']}
                            for c in item.get('competitors', []) if c.get('price')
                        ],
                    }
                    product_analysis.append(pa)
                if product_analysis:
                    return {'product_analysis': product_analysis}
    except Exception:
        pass

    # 备选：decision_analysis.json
    path = os.path.join(base, "competitor_analysis", "decision_analysis.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"product_analysis": []}


def _convert_local_to_analysis(local_data):
    """将本地抓取的JD数据转换为统一格式"""
    from .supply_chain_agent import _infer_category

    product_analysis = []
    for kw, items in local_data.get("by_keyword", {}).items():
        if not items:
            continue
        prices = [i['price'] for i in items if i['price'] > 0]
        avg = sum(prices) / len(prices) if prices else 0
        samples = sorted(prices)[:5]

        pa = {
            "keyword": kw,
            "category": kw,
            "competitors": [
                {"name": i['title'][:30], "price": i['price'], "sales": i.get('sales', '')}
                for i in items[:5]
            ],
            "price_range": f"¥{min(prices):.0f}-¥{max(prices):.0f}" if prices else "",
            "avg_price": round(avg, 2) if avg else 0,
        }

        # 判断价格定位（通过wechat inventory匹配）
        try:
            wechat_inv = _build_inventory_from_wechat() or []
        except Exception:
            wechat_inv = []
        for inv in wechat_inv:
            if kw in inv.get("name", ""):
                my_price = inv.get("price", 0)
                if my_price > 0 and avg > 0:
                    if my_price < avg * 0.8:
                        pa["price_score"] = "偏低"
                    elif my_price > avg * 1.2:
                        pa["price_score"] = "偏高"
                    else:
                        pa["price_score"] = "合理"
                pa["suggestion"] = (pa.get("price_score", "") + "建议参考竞品定价") if pa.get("price_score") else ""
                break

        product_analysis.append(pa)

    return {"product_analysis": product_analysis}


def _match_competitor(inventory_item, competitive_data):
    """根据商品名匹配竞品分析数据"""
    name = inventory_item.get("name", "").lower()
    sku = inventory_item.get("sku", "").lower()
    
    for pa in competitive_data.get("product_analysis", []):
        pa_title = pa.get("title", "").lower()
        # 关键词匹配
        keywords = _infer_category(name)  # 用品类做粗匹配
        if keywords in pa_title or any(k in name for k in [pa_title[:4]]):
            return {
                "category": pa.get("category", ""),
                "status": pa.get("status", ""),
                "price_range": pa.get("price_range", ""),
                "price_score": pa.get("price_score", ""),
                "market_leader": pa.get("market_leader", ""),
                "competitors": pa.get("competitors", []),
                "suggestion": pa.get("suggestion", ""),
            }
        # 精确匹配SKU
        if pa.get("product_id") and pa["product_id"] == sku:
            return {
                "category": pa.get("category", ""),
                "status": pa.get("status", ""),
                "price_range": pa.get("price_range", ""),
                "price_score": pa.get("price_score", ""),
                "market_leader": pa.get("market_leader", ""),
                "competitors": pa.get("competitors", []),
                "suggestion": pa.get("suggestion", ""),
            }
    
    # 没有匹配时返回空
    return None


def _build_inventory_from_wechat():
    """从微信小店API获取真实商品，构建库存分析数据"""
    try:
        from wechat_shop_api import WechatShopAPI
        api = WechatShopAPI()
        products = api.get_all_products()
        
        if not products:
            return None
        
        inventory = []
        for p in products:
            title = p.get("title") or p.get("name", "未命名商品")
            price = (p.get("min_price", 0) or 0) / 100  # 分为元
            sold = p.get("total_sold_num", 0)
            status = p.get("status", 0)
            product_id = str(p.get("product_id", ""))
            
            # 从标题推断品类
            category = _infer_category(title)
            
            # 基于销量估算日均需求
            daily_demand = max(1, int(sold / 30)) if sold > 0 else 2
            
            # 安全库存 = 日均需求 * 交期(默认7天) * 0.5
            lead_time = 7
            safety_stock = daily_demand * lead_time // 2
            reorder_point = daily_demand * lead_time
            
            # 微信API不返回实时库存，随机生成一个初始库存用于分析
            import random
            stock = p.get("stock_num", 0) if p.get("stock_num") else random.randint(0, 200)
            
            # 根据价格推断成本（成本约为售价的40-60%）
            unit_cost = price * random.uniform(0.4, 0.6)
            
            # 匹配供应商（按品类）
            supplier_map = {
                "猫粮": SupplyChainMockData.SUPPLIERS[0],
                "狗粮": SupplyChainMockData.SUPPLIERS[4],
                "猫砂": SupplyChainMockData.SUPPLIERS[1],
                "宠物零食": SupplyChainMockData.SUPPLIERS[2],
                "宠物玩具": SupplyChainMockData.SUPPLIERS[3],
                "宠物窝垫": SupplyChainMockData.SUPPLIERS[5],
                "宠物洗护": SupplyChainMockData.SUPPLIERS[6],
                "狗尿垫": SupplyChainMockData.SUPPLIERS[7],
            }
            supplier = supplier_map.get(category, SupplyChainMockData.SUPPLIERS[0])
            
            inventory.append({
                "sku": product_id or f"WX_{len(inventory)}",
                "name": title[:60],
                "category": category,
                "supplier_id": supplier["id"],
                "supplier_name": supplier["name"],
                "stock": stock,
                "safety_stock": safety_stock,
                "reorder_point": reorder_point,
                "demand_daily": daily_demand,
                "unit_cost": round(unit_cost, 2),
                "lead_time": supplier["lead_time"],
                "location": "微信小店仓库",
                "price": price,
                "sold": sold,
                "wechat_status": status,
                "status": "在售" if status == 5 else "已下架",
            })
        
        return inventory
        
    except Exception as e:
        import sys
        print(f"⚠️ 获取微信商品失败，使用Mock数据: {e}", file=sys.stderr)
        return None


def _infer_category(title: str) -> str:
    """从商品标题推断品类"""
    title_lower = title.lower()
    if any(k in title_lower for k in ["猫粮", "猫食", "幼猫", "成猫", "全猫"]):
        return "猫粮"
    if any(k in title_lower for k in ["狗粮", "犬粮"]):
        return "狗粮"
    if any(k in title_lower for k in ["猫砂", "膨润土", "豆腐砂", "水晶砂", "猫沙"]):
        return "猫砂"
    if any(k in title_lower for k in ["零食", "冻干", "猫条", "火腿肠", "肉干"]):
        return "宠物零食"
    if any(k in title_lower for k in ["玩具", "逗猫", "飞盘"]):
        return "宠物玩具"
    if any(k in title_lower for k in ["窝", "垫", "床"]):
        return "宠物窝垫"
    if any(k in title_lower for k in ["沐浴", "护毛", "洗毛", "牙膏", "洁齿"]):
        return "宠物洗护"
    if any(k in title_lower for k in ["尿垫"]):
        return "狗尿垫"
    return "其他"
