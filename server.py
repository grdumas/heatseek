"""
HeatSeek Real-time Coverage Dashboard API

Provides REST endpoints for querying RHEL performance test coverage data
from OpenSearch with intelligent caching for real-time updates.
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from functools import lru_cache
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict
from typing import Optional
import os
import logging

from opensearchpy import OpenSearch
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="HeatSeek Coverage API",
    description="Real-time RHEL performance test coverage analysis",
    version="2.0.0"
)

# ============ Configuration ============
OPENSEARCH_CONFIG = {
    "host": os.getenv("OPENSEARCH_HOST"),
    "port": int(os.getenv("OPENSEARCH_PORT", 443)),
    "username": os.getenv("OPENSEARCH_USERNAME"),
    "password": os.getenv("OPENSEARCH_PASSWORD"),
    "index": os.getenv("OPENSEARCH_INDEX", "zathras-results")
}

def get_opensearch_client():
    """Create OpenSearch client with configuration from environment"""
    # Validate required configuration
    if not OPENSEARCH_CONFIG["host"]:
        raise ValueError("OPENSEARCH_HOST environment variable is required")
    if not OPENSEARCH_CONFIG["username"]:
        raise ValueError("OPENSEARCH_USERNAME environment variable is required")
    if not OPENSEARCH_CONFIG["password"]:
        raise ValueError("OPENSEARCH_PASSWORD environment variable is required")

    return OpenSearch(
        hosts=[{"host": OPENSEARCH_CONFIG["host"], "port": OPENSEARCH_CONFIG["port"]}],
        http_auth=(OPENSEARCH_CONFIG["username"], OPENSEARCH_CONFIG["password"]),
        use_ssl=os.getenv("OPENSEARCH_USE_SSL", "true").lower() == "true",
        verify_certs=os.getenv("OPENSEARCH_VERIFY_CERTS", "true").lower() == "true",
        ssl_show_warn=False
    )

# ============ Data Models ============
@dataclass
class CoverageCell:
    """Represents test coverage for a specific system×benchmark combination"""
    platform: str
    system: str
    benchmark: str
    os_builds: set[str]
    cpu_info: str
    architecture: str

    @property
    def build_count(self) -> int:
        """Number of distinct OS builds tested"""
        return len(self.os_builds)

    @property
    def viable_for_regression(self) -> bool:
        """Need 2+ OS builds to compare for regression detection"""
        return self.build_count >= 2

    @property
    def color_code(self) -> str:
        """Color coding based on coverage quality"""
        count = self.build_count
        if count == 0: return "#E0E0E0"  # Gray - no data
        if count == 1: return "#FFF59D"  # Yellow - insufficient
        if count == 2: return "#A5D6A7"  # Light green - minimal viable
        if count <= 4: return "#66BB6A"  # Green - good
        return "#2E7D32"                 # Dark green - excellent

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict"""
        return {
            "platform": self.platform,
            "system": self.system,
            "benchmark": self.benchmark,
            "os_builds": sorted(list(self.os_builds)),
            "build_count": self.build_count,
            "cpu_info": self.cpu_info,
            "architecture": self.architecture,
            "color": self.color_code,
            "viable": self.viable_for_regression
        }

# ============ Data Layer ============
class CoverageQuery:
    """Encapsulate all OpenSearch queries"""

    def __init__(self, client: OpenSearch):
        self.client = client
        self.index = OPENSEARCH_CONFIG["index"]

    def get_all_results(self, days_back: Optional[int] = None) -> list:
        """
        Fetch all test results (optionally filtered by date range)

        Args:
            days_back: If provided, only fetch results from last N days.
                      If None, fetch all historical data.
        """
        query = {
            "size": 10000,
            "_source": [
                "metadata.cloud_provider",
                "metadata.instance_type",
                "system_under_test.hardware.cpu.model",
                "system_under_test.hardware.cpu.architecture",
                "system_under_test.operating_system.version",
                "test.name"
            ]
        }

        # Optionally filter by date range
        if days_back is not None:
            query["query"] = {
                "range": {
                    "metadata.test_timestamp": {
                        "gte": f"now-{days_back}d/d"
                    }
                }
            }

        try:
            response = self.client.search(index=self.index, body=query)
            logger.info(f"Fetched {len(response['hits']['hits'])} results from OpenSearch")
            return response["hits"]["hits"]
        except Exception as e:
            logger.error(f"OpenSearch query failed: {e}")
            raise HTTPException(status_code=500, detail=f"OpenSearch query failed: {str(e)}")

# ============ Business Logic ============
def build_coverage_matrix(results: list) -> dict[str, list[CoverageCell]]:
    """Transform raw OpenSearch hits into coverage matrix grouped by platform"""

    # Group by (platform, system, benchmark)
    grouped = defaultdict(lambda: {
        "os_builds": set(),
        "cpu_info": None,
        "platform": None,
        "architecture": None
    })

    for hit in results:
        try:
            src = hit["_source"]
            platform = src.get("metadata", {}).get("cloud_provider", "unknown")
            system = src.get("metadata", {}).get("instance_type", "unknown")
            benchmark = src.get("test", {}).get("name", "unknown")
            os_version = src.get("system_under_test", {}).get("operating_system", {}).get("version", "unknown")
            cpu = src.get("system_under_test", {}).get("hardware", {}).get("cpu", {})
            cpu_model = cpu.get("model", "unknown")
            cpu_arch = cpu.get("architecture", "unknown")

            key = (platform, system, benchmark)
            grouped[key]["os_builds"].add(os_version)
            grouped[key]["cpu_info"] = cpu_model
            grouped[key]["platform"] = platform
            grouped[key]["architecture"] = cpu_arch
        except (KeyError, TypeError) as e:
            logger.warning(f"Skipping malformed record: {e}")
            continue

    # Convert to structured cells
    cells_by_platform = defaultdict(list)
    for (platform, system, benchmark), data in grouped.items():
        cell = CoverageCell(
            platform=platform,
            system=system,
            benchmark=benchmark,
            os_builds=data["os_builds"],
            cpu_info=data["cpu_info"],
            architecture=data["architecture"]
        )
        cells_by_platform[platform].append(cell)

    return dict(cells_by_platform)

def calculate_summary(cells_by_platform: dict[str, list[CoverageCell]]) -> dict:
    """Generate executive summary from coverage matrix"""

    all_cells = [cell for cells_list in cells_by_platform.values() for cell in cells_list]

    if not all_cells:
        return {
            "coverage_score": 0.0,
            "total_combinations": 0,
            "viable_combinations": 0,
            "critical_gaps": [],
            "recommended_systems": [],
            "generated_at": datetime.now().isoformat()
        }

    viable = [c for c in all_cells if c.viable_for_regression]
    coverage_score = (len(viable) / len(all_cells) * 100) if all_cells else 0

    # Find platforms with zero viable coverage
    gaps = [
        platform for platform, cells_list in cells_by_platform.items()
        if not any(c.viable_for_regression for c in cells_list)
    ]

    # Find best systems (most benchmarks with good coverage >= 3 builds)
    system_scores = defaultdict(int)
    for cell in all_cells:
        if cell.build_count >= 3:
            system_scores[cell.system] += 1

    top_systems = sorted(
        system_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )[:3]

    return {
        "coverage_score": round(coverage_score, 1),
        "total_combinations": len(all_cells),
        "viable_combinations": len(viable),
        "critical_gaps": gaps,
        "recommended_systems": [sys for sys, _ in top_systems],
        "generated_at": datetime.now().isoformat()
    }

# ============ Caching Layer ============
def get_cache_key(days_back: Optional[int] = None) -> str:
    """
    Round current time to 30-second buckets for cache invalidation
    Include days_back in key to cache different time ranges separately
    """
    now = datetime.now()
    bucket = now.replace(second=now.second // 30 * 30, microsecond=0)
    days_str = f"_{days_back}d" if days_back is not None else "_all"
    return f"{bucket.isoformat()}{days_str}"

@lru_cache(maxsize=10)
def get_cached_data(cache_key: str, days_back: Optional[int] = None) -> tuple[dict, dict]:
    """
    Fetch and cache coverage data with 30-second TTL
    Returns: (coverage_matrix, summary)

    Args:
        cache_key: Time-based cache key
        days_back: Optional date filter (None = all historical data)
    """
    logger.info(f"Cache miss - fetching fresh data (key: {cache_key}, days_back: {days_back or 'all'})")
    try:
        client = get_opensearch_client()
        query = CoverageQuery(client)
        results = query.get_all_results(days_back=days_back)
        matrix = build_coverage_matrix(results)
        summary = calculate_summary(matrix)
        return matrix, summary
    except ValueError as e:
        # Configuration errors
        logger.error(f"Configuration error: {e}")
        raise HTTPException(status_code=500, detail=f"Server configuration error: {str(e)}")
    except Exception as e:
        # Any other errors during data fetch
        logger.error(f"Error fetching data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch coverage data: {str(e)}")

# ============ API Endpoints ============
@app.get("/api/coverage")
async def get_coverage(
    platform: Optional[str] = None,
    benchmark: Optional[str] = None,
    architecture: Optional[str] = Query(None, pattern="^(x86_64|aarch64)$"),
    min_builds: int = Query(0, ge=0, le=10),
    days_back: Optional[int] = Query(None, ge=1, le=365, description="Filter to last N days (omit for all data)")
):
    """
    Get coverage matrix with optional filters

    - **platform**: AWS, Azure, GCP, IBM, bare-metal (case-insensitive)
    - **benchmark**: coremark, pyperf, streams, etc. (case-insensitive)
    - **architecture**: x86_64 or aarch64
    - **min_builds**: Hide systems with fewer OS builds (0-10)
    - **days_back**: Only show data from last N days (omit to show all historical data)
    """
    matrix, _ = get_cached_data(get_cache_key(days_back), days_back)

    # Apply filters
    filtered = {}
    for plat, cells in matrix.items():
        # Platform filter (case-insensitive)
        if platform and plat.lower() != platform.lower():
            continue

        filtered_cells = [
            c for c in cells
            if (not benchmark or c.benchmark.lower() == benchmark.lower())
            and (not architecture or c.architecture.lower() == architecture.lower())
            and c.build_count >= min_builds
        ]

        if filtered_cells:
            filtered[plat] = [c.to_dict() for c in filtered_cells]

    return filtered

@app.get("/api/summary")
async def get_summary(
    days_back: Optional[int] = Query(None, ge=1, le=365, description="Filter to last N days (omit for all data)")
):
    """
    Get executive summary with coverage score and recommendations

    Returns:
    - coverage_score: Percentage of viable system×benchmark combinations
    - total_combinations: All system×benchmark pairs found
    - viable_combinations: Pairs with 2+ OS builds (regression-capable)
    - critical_gaps: Platforms with zero viable coverage
    - recommended_systems: Top 3 systems by benchmark diversity

    Query params:
    - **days_back**: Only analyze data from last N days (omit to analyze all historical data)
    """
    _, summary = get_cached_data(get_cache_key(days_back), days_back)
    return summary

@app.post("/api/refresh")
async def force_refresh():
    """
    Force cache refresh (for "just processed batch, show me now" use case)

    Engineers can click this after processing test results to immediately
    see updated coverage without waiting for 30-second cache expiry.
    """
    get_cached_data.cache_clear()
    logger.info("Cache manually cleared via /api/refresh")
    _, summary = get_cached_data(get_cache_key())
    return {
        "status": "refreshed",
        "coverage_score": summary["coverage_score"],
        "timestamp": summary["generated_at"]
    }

@app.get("/api/benchmarks")
async def get_benchmarks(
    days_back: Optional[int] = Query(None, ge=1, le=365, description="Filter to last N days (omit for all data)")
):
    """
    Get list of all available benchmarks for filter dropdown

    Query params:
    - **days_back**: Only show benchmarks from last N days (omit for all historical data)
    """
    matrix, _ = get_cached_data(get_cache_key(days_back), days_back)
    all_cells = [cell for cells in matrix.values() for cell in cells]
    benchmarks = sorted(set(c.benchmark for c in all_cells))
    return {"benchmarks": benchmarks}

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/config-status")
async def config_status():
    """Check configuration status (for debugging)"""
    status = {
        "opensearch_host": "configured" if OPENSEARCH_CONFIG["host"] else "missing",
        "opensearch_port": OPENSEARCH_CONFIG["port"],
        "opensearch_username": "configured" if OPENSEARCH_CONFIG["username"] else "missing",
        "opensearch_password": "configured" if OPENSEARCH_CONFIG["password"] else "missing",
        "opensearch_index": OPENSEARCH_CONFIG["index"],
        "timestamp": datetime.now().isoformat()
    }

    # Try to connect
    try:
        client = get_opensearch_client()
        # Simple ping to verify connection
        info = client.info()
        status["opensearch_connection"] = "success"
        status["opensearch_version"] = info.get("version", {}).get("number", "unknown")
    except ValueError as e:
        status["opensearch_connection"] = f"config_error: {str(e)}"
    except Exception as e:
        status["opensearch_connection"] = f"connection_error: {str(e)}"

    return status

@app.get("/")
async def serve_frontend():
    """Serve the main dashboard HTML"""
    return FileResponse("frontend/index.html")

# Mount static files if frontend directory exists
if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")
