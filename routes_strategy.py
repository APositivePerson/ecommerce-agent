"""
电商决策助手路由
"""
from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required
import json
import re

strategy_bp = Blueprint('strategy', __name__)

# 系统提示词
SYSTEM_PROMPT = """你是一位专业的电商运营顾问，拥有8年以上电商行业经验，服务过数百个品牌，涵盖宠物用品、食品、数码、美妆等多个类目。

## 你的专业能力

**市场分析**
- 精通各大电商平台（京东、天猫、抖音、微信小店等）的运营规则和流量逻辑
- 擅长竞品分析和市场定位，能够识别细分市场的机会
- 熟悉消费者心理和购买决策链路

**运营策略**
- 商品定价策略：成本定价、竞争定价、价值定价等多种方法
- 流量获取：搜索优化、付费推广、内容营销、私域运营
- 转化提升：主图优化、详情页设计、活动策划、客服技巧

**数据分析**
- 解读销售数据、流量数据、用户行为数据
- 识别关键指标异常，给出优化建议
- A/B测试设计和效果评估

**供应链管理**
- 库存优化和补货策略
- 供应商谈判和成本控制
- 仓储物流规划

## 你的风格

1. **专业但不教条** - 用接地气的语言解释专业概念，避免满嘴行业黑话
2. **数据驱动** - 给出建议时会引用具体的数据指标和行业基准
3. **务实可行** - 优先考虑执行难度和投入产出比，给出可操作的建议
4. **坦诚直接** - 如果某个方向不可行，你会直接说明原因，而不是绕圈子

## 回复格式

当用户提出问题时，你会：
1. 先理解问题的核心诉求
2. 分析当前情况（可以追问数据）
3. 给出具体建议（分点说明，优先顺序）
4. 预估效果和风险
5. 给出下一步行动建议

## 注意事项

- 如果用户提供的数据不足，你会基于行业经验给出估计值，但会说明这是估计
- 如果问题超出电商运营范畴（如技术开发、法律咨询），你会坦诚说明并给出转介建议
- 对于涉及商业机密的问题，你会谨慎处理，不追问敏感信息

你现在的对话对象是一位微信小店卖家，店铺经营宠物用品（猫粮、猫砂、宠物营养品等），目前处于起步阶段。你应该用适合中小卖家的视角给出建议，避免只讲大品牌的玩法。
"""

def extract_product_context():
    """提取商品相关的上下文"""
    try:
        from wechat_shop_api import WechatShopAPI
        api = WechatShopAPI()
        products = api.get_all_products()
        
        context = {
            "total_products": len(products),
            "categories": {},
            "status_summary": {"on_sale": 0, "archived": 0},
            "total_sold": 0
        }
        
        for p in products:
            # 分类
            title = p.get('title', p.get('name', '')).lower()
            if '猫砂' in title:
                cat = '猫砂'
            elif '猫粮' in title or '猫食' in title:
                cat = '猫粮'
            elif '罐头' in title or '湿粮' in title:
                cat = '猫罐头'
            elif '营养膏' in title or '化毛膏' in title or '牙膏' in title:
                cat = '宠物营养品'
            elif '零食' in title or '冻干' in title or '零食' in title:
                cat = '猫零食'
            else:
                cat = '其他'
            
            context['categories'][cat] = context['categories'].get(cat, 0) + 1
            
            # 状态
            status = p.get('status', 0)
            if status == 5:
                context['status_summary']['on_sale'] += 1
            elif status == 11:
                context['status_summary']['archived'] += 1
            
            context['total_sold'] += p.get('total_sold_num', 0)
        
        return context
    except Exception as e:
        return {"error": str(e)}

@strategy_bp.route('/strategy')
@login_required
def strategy_page():
    """决策助手页面"""
    product_context = extract_product_context()
    return render_template('strategy.html', 
                          product_context=product_context,
                          system_prompt=SYSTEM_PROMPT)

@strategy_bp.route('/api/strategy/chat', methods=['POST'])
@login_required
def chat():
    """处理聊天请求"""
    data = request.get_json()
    user_message = data.get('message', '')
    
    if not user_message.strip():
        return jsonify({'error': '消息不能为空'})
    
    # 获取上下文
    context = extract_product_context()
    
    # 构建prompt
    full_prompt = f"""当前店铺状态：
{json.dumps(context, ensure_ascii=False, indent=2)}

用户问题：{user_message}

请根据以上店铺状态和用户问题，给出专业的电商运营建议。"""
    
    # 这里可以接入大模型API，为了演示先返回模拟响应
    # 实际使用时需要接入真实的AI服务
    
    return jsonify({
        'response': '好的，我收到了您的问题。让我分析一下您的店铺数据...（AI功能正在配置中）',
        'context': context,
        'status': 'pending_ai_config'
    })

@strategy_bp.route('/api/strategy/history', methods=['GET', 'POST'])
@login_required
def chat_history():
    """管理对话历史"""
    if 'strategy_history' not in session:
        session['strategy_history'] = []
    
    if request.method == 'POST':
        data = request.get_json()
        action = data.get('action')
        
        if action == 'clear':
            session['strategy_history'] = []
            return jsonify({'success': True})
        elif action == 'add':
            msg = data.get('message', '')
            msg_type = data.get('type', 'user')  # user or ai
            if msg:
                history = session.get('strategy_history', [])
                history.append({'type': msg_type, 'content': msg, 'time': str(datetime.now())})
                session['strategy_history'] = history[-50:]  # 保留最近50条
                return jsonify({'success': True})
    
    return jsonify({'history': session.get('strategy_history', [])})

from datetime import datetime