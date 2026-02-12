"""
组件8: 数据存储与输出模块

核心职责:
- 将各环节结果持久化存储
- 格式化输出最终行程

输入:
- 所有中间结果及最终行程
- 配置参数

输出:
- CSV/JSON/TXT文件
- 控制台输出
"""

from __future__ import annotations
import os
import json
import logging
from typing import Dict, List
from pathlib import Path
import pandas as pd
from .models import ProcessedData

logger = logging.getLogger(__name__)

class DataOutputHandler:
    """数据存储与输出处理器"""
    
    def __init__(self, config: Dict):
        """
        Args:
            config: 输出配置
        """
        self.output_path = Path(config['output']['path'])
        self.formats = config['output']['formats']
        self.overwrite = config['output']['overwrite']
        self.encoding = config['output']['encoding']
        
        # 创建输出目录
        self.output_path.mkdir(parents=True, exist_ok=True)
    
    def save_all(self, data: ProcessedData):
        """
        保存所有数据
        
        Args:
            data: 完整的处理后数据
        """
        logger.info("开始保存数据...")
        
        # 1. 保存增强后的POI
        if data.enhanced_pois:
            self._save_enhanced_pois(data.enhanced_pois)
        
        # 2. 保存行程（结构化）
        if data.optimized_itinerary:
            self._save_itinerary_structured(data.optimized_itinerary)
        
        # 3. 保存行程（自然语言）
        if data.narration:
            self._save_itinerary_narration(data.narration)
        
        # 4. 保存优化日志
        if data.optimization_logs:
            self._save_optimization_logs(data.optimization_logs)
        
        logger.info(f"✅ 所有数据已保存至: {self.output_path}")
    
    def _save_enhanced_pois(self, pois: List):
        """保存增强后的POI数据"""
        filename = self.output_path / "enhanced_pois"
        
        # 转换为DataFrame
        records = []
        for poi in pois:
            record = {
                "id": poi.id,
                "osmid": poi.osmid,
                "name": poi.name,
                "category": poi.category,
                "lat": poi.lat,
                "lon": poi.lon,
                "llm_processed": poi.llm_processed,
                **{f"enhanced_{k}": v for k, v in poi.enhanced_info.items()}
            }
            records.append(record)
        
        df = pd.DataFrame(records)
        
        # 保存
        if "csv" in self.formats:
            csv_path = filename.with_suffix(".csv")
            df.to_csv(csv_path, index=False, encoding=self.encoding)
            logger.info(f"  ✓ 保存CSV: {csv_path.name}")
        
        if "json" in self.formats:
            json_path = filename.with_suffix(".json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump([poi.dict() for poi in pois], f, ensure_ascii=False, indent=2)
            logger.info(f"  ✓ 保存JSON: {json_path.name}")
    
    def _save_itinerary_structured(self, itinerary):
        """保存结构化行程"""
        filename = self.output_path / "itinerary_structured"
        
        # 转换为DataFrame
        records = [step.dict() for step in itinerary.steps]
        df = pd.DataFrame(records)
        
        # 保存
        if "csv" in self.formats:
            csv_path = filename.with_suffix(".csv")
            df.to_csv(csv_path, index=False, encoding=self.encoding)
            logger.info(f"  ✓ 保存CSV: {csv_path.name}")
        
        if "json" in self.formats:
            json_path = filename.with_suffix(".json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(itinerary.dict(), f, ensure_ascii=False, indent=2)
            logger.info(f"  ✓ 保存JSON: {json_path.name}")
    
    def _save_itinerary_narration(self, narration: Dict[str, str]):
        """保存自然语言行程"""
        if "txt" not in self.formats:
            return
        
        txt_path = self.output_path / "itinerary_narration.txt"
        
        content = f"""
{'='*80}
行程推荐 - 自然语言描述
{'='*80}

【行程总览】
{narration.get('summary', '')}

【精华体验】
{narration.get('highlights', '')}

【分环节详情】
{narration.get('segment_details', '')}

【实用提示】
{narration.get('tips', '')}

{'='*80}
"""
        
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(content.strip())
        
        logger.info(f"  ✓ 保存TXT: {txt_path.name}")
    
    def _save_optimization_logs(self, logs: List):
        """保存优化日志"""
        if not logs:
            return
        
        filename = self.output_path / "optimization_logs"
        
        records = [log.dict() for log in logs]
        df = pd.DataFrame(records)
        
        if "csv" in self.formats:
            csv_path = filename.with_suffix(".csv")
            df.to_csv(csv_path, index=False, encoding=self.encoding)
            logger.info(f"  ✓ 保存CSV: {csv_path.name}")
    
    def print_summary(self, data: ProcessedData):
        """在控制台打印行程摘要"""
        if not data.optimized_itinerary:
            logger.warning("无行程数据可输出")
            return
        
        itinerary = data.optimized_itinerary
        
        print("\n" + "="*80)
        print("📅 行程推荐摘要")
        print("="*80)
        
        print(f"\n📍 基本信息")
        print(f"   日期: {itinerary.date}")
        print(f"   起点: {itinerary.start_point}")
        print(f"   总时长: {itinerary.total_time:.0f} 分钟 ({itinerary.total_time/60:.1f} 小时)")
        print(f"   通勤: {itinerary.total_travel_time:.0f} 分钟")
        print(f"   停留: {itinerary.total_stay_time} 分钟")
        
        if data.narration:
            print(f"\n✨ {data.narration.get('summary', '')}")
        
        print(f"\n📋 详细行程")
        print("-"*80)
        
        # 构造表格
        table_data = []
        for step in itinerary.steps:
            table_data.append({
                "环节": f"{step.segment}. {step.segment_name}",
                "时间": f"{step.time_start}-{step.time_end}",
                "地点": step.poi_name[:20],
                "类别": step.poi_category,
                "通勤(分)": f"{step.travel_time_min:.0f}",
                "停留(分)": step.stay_time_min
            })
        
        df = pd.DataFrame(table_data)
        print(df.to_string(index=False))
        
        if data.optimization_logs:
            print(f"\n🔄 优化记录 ({len(data.optimization_logs)} 项)")
            for log in data.optimization_logs[:5]:  # 只显示前5条
                print(f"   • {log.reason}")
        
        if data.narration and data.narration.get('tips'):
            print(f"\n💡 实用提示")
            print(data.narration['tips'])
        
        print("\n" + "="*80)