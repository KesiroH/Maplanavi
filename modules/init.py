"""
EzTrip 行程推荐系统模块包
"""

__version__ = "1.0.0"

from .models import (
    RawPOI,
    CleanedPOI,
    EnhancedPOI,
    TimeMatrix,
    ItineraryStep,
    Itinerary,
    ProcessedData
)

from .poi_road_network_fetcher import POIRoadNetworkFetcher
from .poi_filter_cleaner import POIFilterCleaner
from .llm_configurator import LLMConfigurator
from .poi_enhancer import POIEnhancer
from .basic_itinerary_planner import BasicItineraryPlanner
from .itinerary_optimizer import ItineraryOptimizer
from .itinerary_narrator import ItineraryNarrator
from .data_output_handler import DataOutputHandler
from .itinerary_adjuster import (
    ItineraryAdjuster,
    AdjustmentRecord,
    AdjustmentError,
    POINotFoundError,
    NoCandidateError,
    swap_poi,
    skip_poi,
    insert_poi,
    reorder_pois
)
from .route_planner import (
    GeoClusterer,
    TSPSolver,
    MultiModalRouter,
    TimeValidator,
    RoutePlanner,
    RoutePlanResult
)

__all__ = [
    # Models
    "RawPOI",
    "CleanedPOI",
    "EnhancedPOI",
    "TimeMatrix",
    "ItineraryStep",
    "Itinerary",
    "ProcessedData",
    
    # Components
    "POIRoadNetworkFetcher",
    "POIFilterCleaner",
    "LLMConfigurator",
    "POIEnhancer",
    "BasicItineraryPlanner",
    "ItineraryOptimizer",
    "ItineraryNarrator",
    "DataOutputHandler",
    
    # Itinerary Adjuster
    "ItineraryAdjuster",
    "AdjustmentRecord",
    "AdjustmentError",
    "POINotFoundError",
    "NoCandidateError",
    "swap_poi",
    "skip_poi",
    "insert_poi",
    "reorder_pois",
    
    # Route Planner
    "GeoClusterer",
    "TSPSolver",
    "MultiModalRouter",
    "TimeValidator",
    "RoutePlanner",
    "RoutePlanResult",
]