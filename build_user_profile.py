"""
用户需求配置脚本
交互式构建用户需求配置文件 (user.json)
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.user_profile_models import (
    UserDemandProfile,
    HardConstraints,
    SoftPreferences,
    StartPoint,
    EndPoint,
    Distribution,
    CategoryConstraint,
    InterestPreference,
    create_default_profile
)


class POICategoryManager:
    def __init__(self, categories_file: str):
        self.categories_file = categories_file
        self.categories: List[Dict[str, str]] = []
        self.hierarchy: Dict[str, Dict] = {}
        self._load_categories()
        self._build_hierarchy()

    def _load_categories(self):
        with open(self.categories_file, 'r', encoding='utf-8') as f:
            self.categories = json.load(f)

    def _build_hierarchy(self):
        for cat in self.categories:
            new_type = cat.get('NEW_TYPE', '')
            major = cat.get('大类', '')
            middle = cat.get('中类', '')
            small = cat.get('小类', '')

            if len(new_type) >= 2:
                major_code = new_type[:2] + '0000'
                if major_code not in self.hierarchy:
                    self.hierarchy[major_code] = {
                        'name': major,
                        'code': major_code,
                        'children': {}
                    }

                if len(new_type) >= 4:
                    middle_code = new_type[:4] + '00'
                    if middle_code not in self.hierarchy[major_code]['children']:
                        self.hierarchy[major_code]['children'][middle_code] = {
                            'name': middle,
                            'code': middle_code,
                            'children': {}
                        }

                    if len(new_type) == 6 and new_type != middle_code:
                        if new_type not in self.hierarchy[major_code]['children'][middle_code]['children']:
                            self.hierarchy[major_code]['children'][middle_code]['children'][new_type] = {
                                'name': small,
                                'code': new_type
                            }

    def get_major_categories(self) -> List[Tuple[str, str]]:
        result = []
        for code, data in self.hierarchy.items():
            result.append((code, data['name']))
        return sorted(result, key=lambda x: x[0])

    def get_middle_categories(self, major_code: str) -> List[Tuple[str, str]]:
        if major_code not in self.hierarchy:
            return []
        result = []
        for code, data in self.hierarchy[major_code]['children'].items():
            result.append((code, data['name']))
        return sorted(result, key=lambda x: x[0])

    def get_small_categories(self, middle_code: str) -> List[Tuple[str, str]]:
        major_code = middle_code[:2] + '0000'
        if major_code not in self.hierarchy:
            return []
        if middle_code not in self.hierarchy[major_code]['children']:
            return []
        result = []
        for code, data in self.hierarchy[major_code]['children'][middle_code]['children'].items():
            result.append((code, data['name']))
        return sorted(result, key=lambda x: x[0])

    def select_category_interactive(self) -> Optional[CategoryConstraint]:
        print("\n=== POI类别选择 ===")
        print("提示: 输入序号选择，输入 0 跳过当前层级")

        major_cats = self.get_major_categories()
        if not major_cats:
            print("未找到类别数据")
            return None

        print("\n【大类】")
        for i, (code, name) in enumerate(major_cats, 1):
            print(f"  {i}. {name} ({code})")
        print("  0. 跳过选择")

        try:
            choice = int(input("\n请选择大类序号: ").strip())
            if choice == 0:
                return CategoryConstraint()
            if choice < 1 or choice > len(major_cats):
                print("无效选择")
                return None
        except ValueError:
            print("请输入有效数字")
            return None

        major_code, major_name = major_cats[choice - 1]
        constraint = CategoryConstraint(major=major_code)

        middle_cats = self.get_middle_categories(major_code)
        if not middle_cats:
            print(f"大类 [{major_name}] 下没有子类别")
            return constraint

        print(f"\n【中类】 - {major_name}")
        for i, (code, name) in enumerate(middle_cats, 1):
            print(f"  {i}. {name} ({code})")
        print("  0. 不选择中类")

        try:
            choice = int(input("\n请选择中类序号: ").strip())
            if choice == 0:
                return constraint
            if choice < 1 or choice > len(middle_cats):
                print("无效选择，仅保存大类")
                return constraint
        except ValueError:
            print("输入无效，仅保存大类")
            return constraint

        middle_code, middle_name = middle_cats[choice - 1]
        constraint.middle = middle_code

        small_cats = self.get_small_categories(middle_code)
        if not small_cats:
            print(f"中类 [{middle_name}] 下没有小类")
            return constraint

        print(f"\n【小类】 - {middle_name}")
        for i, (code, name) in enumerate(small_cats, 1):
            print(f"  {i}. {name} ({code})")
        print("  0. 不选择小类")

        try:
            choice = int(input("\n请选择小类序号: ").strip())
            if choice == 0:
                return constraint
            if choice < 1 or choice > len(small_cats):
                print("无效选择，仅保存大类和中类")
                return constraint
        except ValueError:
            print("输入无效，仅保存大类和中类")
            return constraint

        small_code, small_name = small_cats[choice - 1]
        constraint.small = small_code
        return constraint


class UserProfileBuilder:
    INTEREST_TYPES = {
        "1": ("sight", "景点游览"),
        "2": ("dining", "餐饮美食"),
        "3": ("shopping", "购物"),
        "4": ("entertainment", "娱乐休闲"),
        "5": ("culture", "文化体验"),
        "6": ("nature", "自然风光")
    }

    PACE_OPTIONS = {
        "1": "relaxed",
        "2": "moderate",
        "3": "intense"
    }

    TRANSPORT_OPTIONS = {
        "1": "driving",
        "2": "transit",
        "3": "walking",
        "4": "mixed"
    }

    LEVEL_OPTIONS = {
        "1": "strict",
        "2": "preferred",
        "3": "optional"
    }

    def __init__(self, categories_file: str = "poi_categories.json"):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.categories_file = os.path.join(base_dir, categories_file)
        self.category_manager = POICategoryManager(self.categories_file)
        self.profile: Optional[UserDemandProfile] = None

    def _validate_date(self, date_str: str) -> Tuple[bool, str]:
        try:
            parsed = datetime.strptime(date_str, "%Y-%m-%d")
            if parsed.date() < datetime.now().date():
                return False, "日期不能早于今天"
            return True, date_str
        except ValueError:
            return False, "日期格式错误，请使用 YYYY-MM-DD 格式"

    def _parse_location(self, input_str: str) -> Optional[Tuple[str, List[float]]]:
        input_str = input_str.strip()
        if ',' in input_str:
            parts = input_str.split(',')
            if len(parts) == 2:
                try:
                    lon = float(parts[0].strip())
                    lat = float(parts[1].strip())
                    return f"坐标({lon}, {lat})", [lon, lat]
                except ValueError:
                    return None
        elif '，' in input_str:
            parts = input_str.split('，')
            if len(parts) == 2:
                try:
                    lon = float(parts[0].strip())
                    lat = float(parts[1].strip())
                    return f"坐标({lon}, {lat})", [lon, lat]
                except ValueError:
                    return None
        return (input_str, [116.397, 39.909])

    def _input_date(self) -> str:
        while True:
            date_str = input("请输入出行日期 (YYYY-MM-DD): ").strip()
            valid, result = self._validate_date(date_str)
            if valid:
                return result
            print(f"错误: {result}")

    def _input_start_point(self) -> StartPoint:
        print("\n=== 出发地设置 ===")
        print("支持输入方式:")
        print("  - 地名: 如 '五道口地铁站', '北京西站'")
        print("  - 坐标: 如 '116.338, 39.993' (经度, 纬度)")

        input_str = input("请输入出发地: ").strip()
        result = self._parse_location(input_str)

        if result:
            name, location = result
            return StartPoint(name=name, location=location)
        else:
            print("输入无效，使用默认位置")
            return StartPoint(name=input_str, location=[116.397, 39.909])

    def _input_end_point(self, start_point: StartPoint) -> EndPoint:
        print("\n=== 目的地设置 ===")
        print("1. 与出发地相同")
        print("2. 自定义目的地")

        choice = input("请选择 (1/2): ").strip()
        if choice == "1":
            return EndPoint(type="same_as_start")
        elif choice == "2":
            input_str = input("请输入目的地: ").strip()
            result = self._parse_location(input_str)
            if result:
                name, location = result
                return EndPoint(type="custom", name=name, location=location)
            else:
                return EndPoint(type="custom", name=input_str, location=[116.397, 39.909])
        else:
            print("无效选择，默认与出发地相同")
            return EndPoint(type="same_as_start")

    def _input_transport_mode(self) -> str:
        print("\n=== 交通方式 ===")
        print("1. 驾车 (driving)")
        print("2. 公共交通 (transit)")
        print("3. 步行 (walking)")
        print("4. 混合 (mixed)")

        choice = input("请选择交通方式 (1-4): ").strip()
        return self.TRANSPORT_OPTIONS.get(choice, "driving")

    def _input_distribution(self) -> Distribution:
        print("\n=== 游玩节奏配置 ===")
        print("设置各时段的POI数量 (0-10)")

        def get_count(period: str, default: int) -> int:
            while True:
                try:
                    value = input(f"{period}POI数量 (默认{default}): ").strip()
                    if not value:
                        return default
                    count = int(value)
                    if 0 <= count <= 10:
                        return count
                    print("数量必须在 0-10 之间")
                except ValueError:
                    print("请输入有效数字")

        morning = get_count("上午", 2)
        afternoon = get_count("下午", 2)
        evening = get_count("晚上", 1)

        return Distribution(morning=morning, afternoon=afternoon, evening=evening)

    def _input_interests(self) -> List[InterestPreference]:
        print("\n=== 兴趣偏好设置 ===")
        interests = []

        while True:
            print("\n选择兴趣类型:")
            for key, (type_code, type_name) in self.INTEREST_TYPES.items():
                print(f"  {key}. {type_name}")
            print("  0. 完成添加")

            choice = input("请选择兴趣类型 (0-6): ").strip()
            if choice == "0":
                break
            if choice not in self.INTEREST_TYPES:
                print("无效选择")
                continue

            type_code, type_name = self.INTEREST_TYPES[choice]
            print(f"\n--- 设置 [{type_name}] 偏好 ---")

            print("偏好级别:")
            print("  1. 必须满足 (strict)")
            print("  2. 优先满足 (preferred)")
            print("  3. 可选 (optional)")
            level_choice = input("请选择级别 (1-3, 默认2): ").strip()
            level = self.LEVEL_OPTIONS.get(level_choice, "preferred")

            meal = None
            if type_code == "dining":
                print("餐饮类型:")
                print("  1. 午餐 (lunch)")
                print("  2. 晚餐 (dinner)")
                print("  0. 不指定")
                meal_choice = input("请选择 (0-2): ").strip()
                if meal_choice == "1":
                    meal = "lunch"
                elif meal_choice == "2":
                    meal = "dinner"

            category_constraint = None
            add_category = input("是否添加类别约束? (y/n): ").strip().lower()
            if add_category == 'y':
                category_constraint = self.category_manager.select_category_interactive()

            interest = InterestPreference(
                type=type_code,
                level=level,
                meal=meal,
                category_constraint=category_constraint
            )
            interests.append(interest)
            print(f"已添加: {type_name} ({level})")

        return interests

    def _input_soft_preferences(self) -> SoftPreferences:
        print("\n=== 软性偏好设置 ===")

        print("\n游玩节奏:")
        print("  1. 轻松 (relaxed)")
        print("  2. 适中 (moderate)")
        print("  3. 紧凑 (intense)")
        pace_choice = input("请选择 (1-3, 默认1): ").strip()
        pace = self.PACE_OPTIONS.get(pace_choice, "relaxed")

        print("\n预算等级 (1-5, 1=经济, 5=豪华):")
        while True:
            try:
                budget = input("请输入预算等级 (默认3): ").strip()
                budget_level = int(budget) if budget else 3
                if 1 <= budget_level <= 5:
                    break
                print("预算等级必须在 1-5 之间")
            except ValueError:
                print("请输入有效数字")
                budget_level = 3

        interests = self._input_interests()

        print("\n负面关键词 (不感兴趣的类型):")
        print("示例: 博物馆, 爬山, 游乐场")
        negative_input = input("请输入，用逗号分隔 (可留空): ").strip()
        negative_keywords = []
        if negative_input:
            negative_keywords = [kw.strip() for kw in negative_input.replace('，', ',').split(',') if kw.strip()]

        return SoftPreferences(
            pace=pace,
            budget_level=budget_level,
            interests=interests,
            negative_keywords=negative_keywords
        )

    def build(self) -> UserDemandProfile:
        print("=" * 50)
        print("       用户需求配置向导")
        print("=" * 50)

        date = self._input_date()

        print("\n出行天数 (1-30, 默认1):")
        while True:
            try:
                days_input = input("请输入天数: ").strip()
                duration_days = int(days_input) if days_input else 1
                if 1 <= duration_days <= 30:
                    break
                print("天数必须在 1-30 之间")
            except ValueError:
                print("请输入有效数字")

        start_point = self._input_start_point()
        end_point = self._input_end_point(start_point)
        transport_mode = self._input_transport_mode()
        distribution = self._input_distribution()

        hard_constraints = HardConstraints(
            date=date,
            duration_days=duration_days,
            start_point=start_point,
            end_point=end_point,
            transport_mode=transport_mode,
            distribution=distribution
        )

        soft_preferences = self._input_soft_preferences()

        self.profile = UserDemandProfile(
            meta={
                "user_id": f"u_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "session_id": f"s_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "created_at": datetime.now().isoformat()
            },
            hard_constraints=hard_constraints,
            soft_preferences=soft_preferences
        )

        return self.profile

    def save(self, filepath: str = "modules/user.json"):
        if self.profile:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            full_path = os.path.join(base_dir, filepath) if not os.path.isabs(filepath) else filepath
            self.profile.to_json_file(full_path)
            print(f"\n配置已保存至: {full_path}")
            return True
        return False

    def preview(self):
        if self.profile:
            print("\n" + "=" * 50)
            print("       配置预览")
            print("=" * 50)
            hc = self.profile.hard_constraints
            sp = self.profile.soft_preferences

            print(f"\n【硬性约束】")
            print(f"  出行日期: {hc.date}")
            print(f"  出行天数: {hc.duration_days} 天")
            print(f"  出发地: {hc.start_point.name} {hc.start_point.location}")
            if hc.end_point.type == "same_as_start":
                print(f"  目的地: 与出发地相同")
            else:
                print(f"  目的地: {hc.end_point.name} {hc.end_point.location}")
            print(f"  交通方式: {hc.transport_mode}")
            print(f"  POI分布: 上午{hc.distribution.morning}个, 下午{hc.distribution.afternoon}个, 晚上{hc.distribution.evening}个")

            print(f"\n【软性偏好】")
            print(f"  游玩节奏: {sp.pace}")
            print(f"  预算等级: {sp.budget_level}")
            if sp.interests:
                print(f"  兴趣偏好:")
                for i, interest in enumerate(sp.interests, 1):
                    constraint_str = ""
                    if interest.category_constraint:
                        cc = interest.category_constraint
                        parts = []
                        if cc.major:
                            parts.append(f"大类:{cc.major}")
                        if cc.middle:
                            parts.append(f"中类:{cc.middle}")
                        if cc.small:
                            parts.append(f"小类:{cc.small}")
                        if parts:
                            constraint_str = f" [{', '.join(parts)}]"
                    meal_str = f", {interest.meal}" if interest.meal else ""
                    print(f"    {i}. {interest.type}{meal_str} ({interest.level}){constraint_str}")
            if sp.negative_keywords:
                print(f"  负面关键词: {', '.join(sp.negative_keywords)}")


def main():
    builder = UserProfileBuilder()

    try:
        profile = builder.build()
        builder.preview()

        confirm = input("\n确认保存配置? (y/n): ").strip().lower()
        if confirm == 'y':
            builder.save()
            print("\n配置完成!")
        else:
            print("\n已取消保存")

    except KeyboardInterrupt:
        print("\n\n已取消配置")
    except Exception as e:
        print(f"\n配置过程出错: {e}")
        raise


if __name__ == "__main__":
    main()
