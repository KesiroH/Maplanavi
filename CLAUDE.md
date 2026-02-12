# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an LLM-powered itinerary planning system (行程推荐系统) that generates optimized day-trip itineraries using POI data from OpenStreetMap and routing information from OSRM. The system uses LLM capabilities for intelligent POI selection, ranking, and itinerary optimization.

## Architecture

The system follows a modular pipeline architecture with 8 components:

### Data Flow Pipeline

1. **POIRoadNetworkFetcher** (`poi_road_network_fetcher.py`)
   - Fetches raw POI data from Overpass API (OpenStreetMap)
   - Retrieves travel time matrices from OSRM
   - Uses Haversine distance for pre-filtering nearest POIs

2. **POIFilterCleaner** (`poi_filter_cleaner.py`)
   - Cleans and validates raw POI data
   - Filters by name blacklist, coordinates, region boundaries
   - Maps OSM tags to Chinese categories using `poi_categories.json`
   - Validates time matrices for anomalies

3. **LLMConfigurator** (`llm_configurator.py`)
   - Unified LLM client supporting OpenAI and Tongyi Qianwen (通义千问)
   - Handles both domestic and international Tongyi endpoints
   - Provides `call_json()` and `call_text()` methods with retry logic
   - Strips markdown code blocks from JSON responses

4. **POIEnhancer** (`poi_enhancer.py`)
   - Uses LLM to enrich POI data with ratings, opening hours, crowd levels, etc.
   - Adds semantic information not available in OSM data

5. **BasicItineraryPlanner** (`basic_itinerary_planner.py`)
   - Generates initial 8-segment itinerary using LLM ranking + greedy algorithm
   - Each segment has time windows, category constraints, and max commute times
   - LLM ranks candidates based on time appropriateness and user preferences

6. **ItineraryOptimizer** (`itinerary_optimizer.py`)
   - Uses LLM to detect issues: time conflicts, theme jumps, crowd warnings, inefficient routes
   - Generates optimization suggestions (currently logs only, not implemented)

7. **ItineraryNarrator** (`itinerary_narrator.py`)
   - Generates natural language descriptions of the itinerary

8. **DataOutputHandler** (`data_output_handler.py`)
   - Exports results to JSON/CSV formats

### Data Models (`models.py`)

Core Pydantic models with type safety:
- **RawPOI** → **CleanedPOI** → **EnhancedPOI**: POI data transformation stages
- **TimeMatrix**: Travel time matrix with POI ID mapping
- **SegmentConfig**: Itinerary segment configuration from config.yaml
- **ItineraryStep** / **Itinerary**: Final itinerary structure
- **ProcessedData**: Container for all intermediate pipeline data

## Key Configuration

The system expects a `config.yaml` file (not present in this backup) with:
- `region`: Bounding box (min_lat, max_lat, min_lon, max_lon)
- `poi_categories`: List of OSM tags mapped to Chinese categories
- `llm`: LLM provider config (type, api_key, model, base_url, temperature, etc.)
- `itinerary`: 8-segment structure with time_range, category, stay_minutes, max_commute_minutes
- `data_fetching`: Overpass and OSRM endpoints
- `data_cleaning`: Filters and validation rules

## LLM Integration Patterns

### Tongyi International vs Domestic
- **Domestic**: Uses `dashscope` SDK, requires `result_format="message"`
- **International**: Uses OpenAI SDK with custom `base_url` containing "dashscope-intl"
- JSON mode: OpenAI uses `response_format={"type": "json_object"}`, Tongyi requires prompt instructions

### Common LLM Tasks
- **POI Ranking**: Scores candidates 0-10 based on time appropriateness, distance, user preferences
- **Itinerary Optimization**: Detects time conflicts, theme jumps, crowd levels
- **Narration**: Generates natural language summaries

## Data Files

- `poi_categories.json`: Maps POI type codes (e.g., "050100") to categories (餐饮服务 > 中餐厅)
- `haidian_poi.json`: Sample POI data for Haidian district (5.4MB)

## Development Notes

### Name Filtering
The system has an extensive blacklist in `POIFilterCleaner.NAME_BLACKLIST` to filter out:
- Commercial services (超市, 便利店, 理发, 美发)
- Infrastructure (医院, 加油, 停车, 充电)
- Sports facilities (操场, 球场, 游泳)
- Pure digit names

### Time Matrix Handling
- First row/column (index 0) represents the start point with POI ID = -1
- Uses `poi_to_matrix_idx` mapping to convert POI IDs to matrix indices
- Invalid times are set to `None` (unreachable)

### Greedy Selection Strategy
`BasicItineraryPlanner._greedy_select()` takes top 3 LLM-ranked candidates and selects the one with shortest travel time - balancing LLM intelligence with practical routing efficiency.

## Common Tasks

### Running the System
The main entry point is not included in this backup, but the typical flow would be:
```python
# 1. Initialize components
fetcher = POIRoadNetworkFetcher(config)
cleaner = POIFilterCleaner(config)
llm = LLMConfigurator(config['llm'])

# 2. Fetch and clean data
raw_pois = fetcher.fetch_pois()
cleaned_pois, report = cleaner.clean_pois(raw_pois)
time_matrix = fetcher.fetch_time_matrix(start_point, cleaned_pois)
validated_matrix = cleaner.validate_time_matrix(time_matrix, cleaned_pois)

# 3. Enhance and plan
enhancer = POIEnhancer(cleaned_pois, llm, config)
enhanced_pois = enhancer.enhance()
planner = BasicItineraryPlanner(enhanced_pois, validated_matrix, llm, config)
itinerary = planner.plan()

# 4. Optimize and output
optimizer = ItineraryOptimizer(enhanced_pois, validated_matrix, llm, config)
optimized, logs = optimizer.optimize(itinerary)
```

### Testing Individual Components
Each module is self-contained and can be tested independently by importing from `modules/`.

### Modifying POI Categories
Edit `poi_categories.json` to add/remove POI types. Each entry needs:
- `NEW_TYPE`: Category code
- `大类`, `中类`, `小类`: Hierarchical Chinese names
- Corresponding OSM tag mapping in config.yaml

### Adjusting Itinerary Structure
The 8-segment structure is defined in config.yaml's `itinerary.segments`. Each segment specifies:
- `segment`: Sequence number (1-8)
- `name`: Chinese name (e.g., "早餐", "上午景点")
- `time_range`: Time window (e.g., "08:00-09:00")
- `category`: Allowed POI categories
- `stay_minutes`: Duration at location
- `max_commute_minutes`: Maximum travel time from previous location

## Language

The codebase uses Chinese for:
- Comments and docstrings
- POI category names
- Segment names and descriptions
- Log messages

Code identifiers and data model fields use English.
