"""
Prompt 模板管理器
================

集中管理所有LLM Prompt模板，实现逻辑与文本解耦。
"""

from __future__ import annotations
from typing import Dict, Optional, Any, List
import re


class PromptManager:
    """Prompt 模板管理器"""
    
    POI_SCORING_SYSTEM = """你是一个专业的旅行规划助手，擅长评估景点与用户需求的匹配程度。
请根据以下信息评估用户对每个景点的兴趣程度。

评分标准：
- 10分：完全符合用户需求，非常想去
- 7-9分：比较符合用户需求
- 4-6分：一般符合
- 1-3分：不太符合
- 0分：完全不符合

请返回JSON格式的评分结果。"""

    POI_SCORING_USER_TEMPLATE = """用户需求：
- 兴趣类型：{interests}
- 偏好描述：{preferences}
- 预算等级：{budget_level}

请评估以下景点与用户需求的匹配程度：

{poi_list}

请返回JSON格式的评分结果，格式如下：
{{
    "scores": [
        {{"poi_id": "xxx", "score": 8.5, "reason": "原因说明"}},
        ...
    ]
}}"""

    CATEGORY_MAPPING_SYSTEM = """你是一个POI分类专家，擅长将景点分类到正确的类别。"""

    CATEGORY_MAPPING_USER_TEMPLATE = """请将以下POI分类到最合适的大类：

POI列表：
{poi_list}

可选类别：景点游览, 餐饮美食, 购物, 娱乐休闲, 文化体验, 自然风光

请返回JSON格式的分类结果。"""

    ITINERARY_NARRATOR_SYSTEM = """你是一个专业的旅行作家，擅长撰写生动有趣的旅行行程介绍。"""

    ITINERARY_NARRATOR_USER_TEMPLATE = """请为以下旅行行程撰写一段介绍文字：

行程信息：
- 出发地：{start_location}
- 目的地数量：{poi_count}
- 旅行类型：{travel_type}

行程安排：
{itinerary_details}

请用优美的文字描述这段旅程，字数约200字。"""

    PREFERENCE_PARSING_SYSTEM = """你是一个用户需求分析专家，擅长从用户的自然语言描述中提取旅行偏好。"""

    PREFERENCE_PARSING_USER_TEMPLATE = """请从以下用户描述中提取旅行偏好：

用户描述：{user_input}

请返回JSON格式的偏好分析结果，包括：
- 兴趣类型（景点/美食/购物/休闲/文化/自然）
- 偏好关键词
- 预算倾向（经济/中等/豪华）
- 旅行节奏（轻松/适中/紧凑）"""

    @classmethod
    def get_poi_scoring_prompt(
        cls,
        interests: str,
        preferences: str,
        budget_level: int,
        poi_list: List[Dict[str, Any]]
    ) -> tuple:
        """
        获取POI评分Prompt
        
        Args:
            interests: 兴趣类型
            preferences: 偏好描述
            budget_level: 预算等级 (1-5)
            poi_list: POI列表
            
        Returns:
            (system_prompt, user_prompt)
        """
        poi_text = "\n".join([
            f"- {poi.get('name', '未知')} ({poi.get('type', '未知')}): {poi.get('address', '地址未知')}"
            for poi in poi_list[:10]  # 限制数量
        ])
        
        user_prompt = cls.POI_SCORING_USER_TEMPLATE.format(
            interests=interests,
            preferences=preferences,
            budget_level=budget_level,
            poi_list=poi_text
        )
        
        return cls.POI_SCORING_SYSTEM, user_prompt

    @classmethod
    def get_preference_parsing_prompt(cls, user_input: str) -> tuple:
        """获取偏好解析Prompt"""
        user_prompt = cls.PREFERENCE_PARSING_USER_TEMPLATE.format(
            user_input=user_input
        )
        return cls.PREFERENCE_PARSING_SYSTEM, user_prompt

    @classmethod
    def get_itinerary_narrator_prompt(
        cls,
        start_location: str,
        poi_count: int,
        travel_type: str,
        itinerary_details: str
    ) -> tuple:
        """获取行程解说Prompt"""
        user_prompt = cls.ITINERARY_NARRATOR_USER_TEMPLATE.format(
            start_location=start_location,
            poi_count=poi_count,
            travel_type=travel_type,
            itinerary_details=itinerary_details
        )
        return cls.ITINERARY_NARRATOR_SYSTEM, user_prompt


def sanitize_prompt_input(text: str, max_length: int = 2000) -> str:
    """
    清洗用户输入，防止Prompt注入
    
    Args:
        text: 用户输入文本
        max_length: 最大长度限制
        
    Returns:
        清洗后的文本
    """
    if not text:
        return ""
    
    # 限制长度
    text = text[:max_length]
    
    # 移除可能导致注入的特殊字符序列
    dangerous_patterns = [
        r'\bignore\b',
        r'\bforget\b',
        r'\boverride\b',
        r'```',
        r'\bsystem\b.*?:',
    ]
    
    for pattern in dangerous_patterns:
        text = re.sub(pattern, '[FILTERED]', text, flags=re.IGNORECASE)
    
    # 移除多余空白
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text
