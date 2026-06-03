#!/usr/bin/env python3
"""
FastAPI backend server for HeatSeek.

Provides REST API endpoints to fetch fresh coverage data from OpenSearch
and serve the static HTML visualization.
"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from visualize_test_coverage import (
    connect_to_opensearch,
    fetch_coverage_data,
    build_coverage_matrix,
    calculate_executive_summary
)

load_dotenv()

app = FastAPI(
    title="HeatSeek API",
    description="Performance test coverage analysis API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def serve_visualization():
    """Serve the main HTML visualization."""
    html_file = "heatseek.html"
    if not os.path.exists(html_file):
        raise HTTPException(status_code=404, detail=f"{html_file} not found. Run visualize_test_coverage.py first.")
    return FileResponse(html_file)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "heatseek-api"}


@app.get("/api/coverage")
async def get_coverage_data():
    """
    Fetch fresh coverage data from OpenSearch.

    Returns:
        JSON with coverage matrix, benchmarks, platform stats, and executive summary
    """
    try:
        index = os.getenv('OPENSEARCH_INDEX', 'zathras-results')

        client = connect_to_opensearch()
        docs = fetch_coverage_data(client, index)

        matrix, benchmarks, platform_stats, system_metadata = build_coverage_matrix(docs)

        executive_summary = calculate_executive_summary(matrix, benchmarks)

        def serialize_summary(summary):
            """Convert sets in executive summary to lists for JSON serialization."""
            serialized = summary.copy()
            if 'recommended_systems' in serialized:
                serialized['recommended_systems'] = [
                    (system, {
                        'total': stats['total'],
                        'viable': stats['viable'],
                        'benchmarks': list(stats['benchmarks'])
                    })
                    for system, stats in serialized['recommended_systems']
                ]
            return serialized

        serialized_summary = serialize_summary(executive_summary)
        serialized_matrix = {}
        for platform, systems in matrix.items():
            serialized_matrix[platform] = {}
            for system, benchmark_dict in systems.items():
                serialized_matrix[platform][system] = {}
                for benchmark, os_builds in benchmark_dict.items():
                    serialized_matrix[platform][system][benchmark] = list(os_builds)

        serialized_platform_stats = {}
        for platform, stats in platform_stats.items():
            serialized_platform_stats[platform] = {
                'systems': list(stats['systems']),
                'os_builds': list(stats['os_builds']),
                'test_count': stats['test_count']
            }

        return JSONResponse({
            "matrix": serialized_matrix,
            "benchmarks": benchmarks,
            "platform_stats": serialized_platform_stats,
            "system_metadata": system_metadata,
            "executive_summary": serialized_summary,
            "total_documents": len(docs)
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch coverage data: {str(e)}")


@app.post("/api/regenerate")
async def regenerate_visualization():
    """
    Regenerate the static HTML visualization file.

    Fetches fresh data from OpenSearch and writes new heatseek.html file.
    """
    try:
        import subprocess
        result = subprocess.run(
            ['python3', 'visualize_test_coverage.py'],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Regeneration failed: {result.stderr}"
            )

        return {
            "status": "success",
            "message": "Visualization regenerated successfully",
            "output": result.stdout
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Regeneration timed out after 120 seconds")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Regeneration error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
