# 高德地图 Web 服务 API Python SDK

一个简洁、功能完整的 Python SDK，封装了高德地图 Web 服务 API 的常用接口。

## 功能特性

- **地理编码**: 地址 ⇄ 经纬度坐标转换
- **路径规划**: 驾车、步行、骑行、公交路线规划
- **POI 搜索**: 关键字搜索、周边搜索、多边形搜索、ID 查询
- **距离测量**: 直线距离、驾车距离、步行距离
- **行政区划**: 行政区划查询
- **IP 定位**: 根据 IP 地址定位
- **天气查询**: 实况天气和天气预报
- **输入提示**: 自动补全功能

## 安装

### 方式一：直接使用

```bash
pip install -r requirements.txt
```

### 方式二：手动安装

```bash
pip install requests>=2.28.0
```

## 获取 API Key

1. 访问 [高德开放平台](https://lbs.amap.com/)
2. 注册/登录账号
3. 进入「应用管理」→「我的应用」→「创建新应用」
4. 添加 Key，服务平台选择「Web 服务」
5. 复制生成的 Key 用于 SDK 初始化

## 快速开始

```python
from autoapi import GaodeMapClient

# 初始化客户端
client = GaodeMapClient("your_api_key_here")

# 地理编码
result = client.geocode("北京市朝阳区望京SOHO")
print(result["geocodes"][0]["location"])  # 输出: 116.481499,39.990475
```

## API 详细说明

### 1. 地理编码

#### 地理编码（地址 → 坐标）

```python
result = client.geocode(
    address="北京市朝阳区望京SOHO",
    city="北京"  # 可选，提高准确性
)

# 返回示例
{
    "geocodes": [{
        "location": "116.481499,39.990475",
        "province": "北京市",
        "city": "北京市",
        "district": "朝阳区",
        "adcode": "110105"
    }]
}
```

#### 逆地理编码（坐标 → 地址）

```python
result = client.reverse_geocode(
    location="116.481499,39.990475",
    radius=1000,  # 可选，查询半径（米）
    extensions="all"  # "base" 或 "all"
)

# 返回示例
{
    "regeocode": {
        "formatted_address": "北京市朝阳区望京街道方恒国际中心B座",
        "addressComponent": {
            "province": "北京市",
            "city": "北京市",
            "district": "朝阳区"
        }
    }
}
```

#### 批量逆地理编码

```python
result = client.batch_reverse_geocode(
    locations=["116.481499,39.990475", "116.386837,39.863673"],
    extensions="base"
)
```

### 2. 路径规划

#### 驾车路径规划

```python
result = client.driving_direction(
    origin="116.481499,39.990475",
    destination="116.386837,39.863673",
    strategy=10,  # 路径策略
    waypoints="116.450000,39.950000",  # 可选，途经点
    avoidroad="某道路名称"  # 可选，避让道路
)

# 路径策略说明:
# 0: 速度优先（时间）
# 1: 费用优先（不走收费路段）
# 2: 距离优先（最短）
# 10: 速度优先（推荐）
# 11: 躲避拥堵
# 12: 躲避拥堵且速度优先

# 获取路线信息
route = result["route"]["paths"][0]
print(f"距离: {route['distance']} 米")
print(f"时长: {route['duration']} 秒")
```

#### 步行路径规划

```python
result = client.walking_direction(
    origin="116.481499,39.990475",
    destination="116.386837,39.863673"
)
```

#### 骑行路径规划

```python
result = client.bicycling_direction(
    origin="116.481499,39.990475",
    destination="116.386837,39.863673"
)
```

#### 公交路径规划

```python
result = client.transit_direction(
    origin="116.481499,39.990475",
    destination="116.386837,39.863673",
    city="北京",
    cityd="北京",  # 可选，跨城时使用
    strategy=0,  # 换乘策略
    nightflag=0  # 是否计算夜班车
)

# 换乘策略说明:
# 0: 最快捷模式
# 1: 最经济模式
# 2: 最少换乘模式
# 3: 最少步行模式
# 5: 不乘地铁模式
```

### 3. POI 搜索

#### 关键字搜索

```python
result = client.poi_search_by_keyword(
    keywords="咖啡厅",
    types="060100",  # 可选，POI类型代码
    city="北京",
    citylimit=True,  # 是否限制城市范围
    page=1,
    offset=20,
    extensions="all"
)

# 遍历结果
for poi in result["pois"]:
    print(f"{poi['name']}: {poi['address']}")
```

#### 周边搜索

```python
result = client.poi_search_around(
    center="116.481499,39.990475",
    radius=3000,  # 搜索半径（米），最大50000
    keywords="餐厅",
    types="050000",  # 可选
    page=1,
    offset=20
)
```

#### 多边形搜索

```python
result = client.poi_search_by_polygon(
    polygon="116.460,39.990|116.500,39.990|116.500,39.970|116.460,39.970|116.460,39.990",
    keywords="超市",
    page=1,
    offset=20
)
```

#### ID 查询

```python
result = client.poi_search_by_id("B000A7HFVV")

# 或批量查询
result = client.poi_search_by_id(["B000A7HFVV", "B000A83MMC"])
```

### 4. 距离测量

```python
from autoapi import DistanceType

# 单点测量
result = client.distance(
    origins="116.481499,39.990475",
    destination="116.386837,39.863673",
    distance_type=DistanceType.DRIVING  # 驾车距离
)

# 多点测量
result = client.distance(
    origins=["116.481499,39.990475", "116.450000,39.950000"],
    destination="116.386837,39.863673",
    distance_type=DistanceType.STRAIGHT  # 直线距离
)

# 距离类型:
# DistanceType.STRAIGHT (0): 直线距离
# DistanceType.DRIVING (1): 驾车距离
# DistanceType.WALKING (3): 步行距离
```

### 5. 行政区划查询

```python
result = client.district_query(
    keywords="北京",  # 可选，支持名称/adcode/citycode
    subdistrict=1,  # 子级数量
    extensions="all"  # "base" 或 "all"（包含边界坐标）
)

# 返回示例
{
    "districts": [{
        "adcode": "110000",
        "name": "北京市",
        "center": "116.405285,39.904989",
        "level": "province",
        "districts": [...]  # 下级行政区
    }]
}
```

### 6. IP 定位

```python
# 自动获取请求者 IP
result = client.ip_location()

# 指定 IP
result = client.ip_location("114.114.114.114")

# 返回示例
{
    "province": "江苏",
    "city": "南京市",
    "adcode": "320100",
    "rectangle": "118.726...,32.036...;118.801...,32.106..."
}
```

### 7. 天气查询

```python
# 实况天气
result = client.weather(
    city="北京",
    extensions="base"
)

# 天气预报
result = client.weather(
    city="110000",  # 支持 adcode
    extensions="all"
)
```

### 8. 输入提示

```python
result = client.input_tips(
    keywords="望京",
    city="北京",
    citylimit=True,
    datatype="all"  # "all" 或 "poi"
)

# 返回示例
{
    "tips": [{
        "name": "望京SOHO",
        "address": "北京市朝阳区阜通东大街6号",
        "location": "116.481499,39.990475"
    }]
}
```

## 错误处理

SDK 提供了完善的异常处理机制：

```python
from autoapi import (
    GaodeMapClient,
    GaodeMapError,
    GaodeMapAPIError,
    GaodeMapConnectionError,
    GaodeMapTimeoutError
)

client = GaodeMapClient("your_api_key")

try:
    result = client.geocode("北京市朝阳区望京SOHO")
except GaodeMapAPIError as e:
    print(f"API 错误: {e.message}")
    print(f"错误码: {e.info_code}")
    print(f"响应数据: {e.response}")
except GaodeMapConnectionError as e:
    print(f"网络连接错误: {e.message}")
except GaodeMapTimeoutError as e:
    print(f"请求超时: {e.message}")
except GaodeMapError as e:
    print(f"通用错误: {e.message}")
```

## 错误码对照表

| 错误码 | 说明 |
|--------|------|
| 10000 | OK |
| 10001 | key 不正确或过期 |
| 10002 | 服务维护中 |
| 10003 | 服务不可用 |
| 10004 | 访问已超出日访问量 |
| 10005 | 用户访问过于频繁 |
| 10006 | 用户 IP 无效 |
| 10007 | 用户域名无效 |
| 20000 | 请求参数非法 |
| 20001 | 缺少必填参数 |
| 30000 | 服务端错误 |

## 日志配置

SDK 使用 Python 标准库 `logging` 进行日志记录：

```python
import logging

# 设置日志级别
logging.getLogger('GaodeMapClient').setLevel(logging.DEBUG)

# 或全局配置
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

## 高级配置

```python
client = GaodeMapClient(
    api_key="your_api_key",
    timeout=30,        # 请求超时时间（秒）
    max_retries=5,     # 最大重试次数
    retry_delay=2.0    # 重试间隔（秒）
)
```

## POI 类型代码参考

常用 POI 类型代码：

| 代码 | 类型 |
|------|------|
| 010000 | 美食 |
| 020000 | 购物 |
| 030000 | 生活服务 |
| 040000 | 体育休闲 |
| 050000 | 医疗保健 |
| 060000 | 住宿服务 |
| 070000 | 风景名胜 |
| 080000 | 商务住宅 |
| 090000 | 政府机构 |
| 100000 | 科教文化 |
| 110000 | 交通设施 |
| 120000 | 金融保险 |
| 130000 | 公司企业 |

完整类型代码请参考 [高德 POI 分类代码表](https://lbs.amap.com/api/webservice/download)

## 使用限制

- 每日调用量限制：根据账户等级不同
- 并发限制：根据账户等级不同
- 单次请求返回 POI 数量：最多 50 条

详细限制请参考 [高德开放平台配额说明](https://lbs.amap.com/faq/account/quotas)

## 官方文档

- [地理/逆地理编码](https://lbs.amap.com/api/webservice/guide/api/georegeo)
- [路径规划](https://lbs.amap.com/api/webservice/guide/api/direction)
- [POI 搜索](https://lbs.amap.com/api/webservice/guide/api-advanced/search)
- [新版 POI 搜索](https://lbs.amap.com/api/webservice/guide/api-advanced/newpoisearch)
- [距离测量](https://lbs.amap.com/api/webservice/guide/api/distance)
- [行政区划](https://lbs.amap.com/api/webservice/guide/api/district)

## 许可证

MIT License

## 更新日志

### v1.0.0
- 初始版本
- 支持地理编码、路径规划、POI 搜索等核心功能
- 添加日志记录和错误处理
- 支持请求重试机制
