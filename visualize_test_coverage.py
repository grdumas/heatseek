#!/usr/bin/env python3
"""
Generate an interactive test coverage matrix visualization.

Shows coverage across:
- Platform (AWS, Azure, GCP, IBM, bare metal)
- System (CPU model + core count)
- OS Build (RHEL version + kernel)
- Benchmarks

Output: Standalone HTML file with interactive Plotly visualizations
"""

import os
import json
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv
from opensearchpy import OpenSearch

# Load environment variables
load_dotenv()

def connect_to_opensearch():
    """Establish connection to OpenSearch cluster."""
    client = OpenSearch(
        hosts=[{
            'host': os.getenv('OPENSEARCH_HOST'),
            'port': int(os.getenv('OPENSEARCH_PORT', 9200))
        }],
        http_auth=(os.getenv('OPENSEARCH_USERNAME'), os.getenv('OPENSEARCH_PASSWORD')),
        use_ssl=os.getenv('OPENSEARCH_USE_SSL', 'true').lower() == 'true',
        verify_certs=os.getenv('OPENSEARCH_VERIFY_CERTS', 'true').lower() == 'true',
        ssl_show_warn=False
    )
    return client

def get_system_label(doc, short=False):
    """
    Create human-readable system label: CPU model + core count.

    Args:
        doc: Document from OpenSearch
        short: If True, return abbreviated label for display

    Returns:
        If short=True: "Xeon 8259CL • 96c"
        If short=False: Full details dict with label and metadata
    """
    try:
        cpu = doc.get('system_under_test', {}).get('hardware', {}).get('cpu', {})
        model = cpu.get('model', 'Unknown CPU')
        cores = cpu.get('cores', 0)
        arch = cpu.get('architecture', 'unknown')

        # Simplify CPU model names
        if 'INTEL' in model.upper() and 'XEON' in model.upper():
            # Extract Xeon model number
            # Handle formats like: "Intel(R) Xeon(R) Platinum 8573C" or "Intel Xeon 8259CL"
            # Remove (R) markers first
            clean_model = model.replace('(R)', '').replace('(r)', '').replace('(TM)', '').replace('(tm)', '')
            parts = clean_model.split()

            model_short = "Xeon"  # Default
            for i, part in enumerate(parts):
                if 'XEON' in part.upper() and i+1 < len(parts):
                    # Get model number (e.g., "8259CL" or "Platinum 8573C")
                    next_part = parts[i+1]
                    if i+2 < len(parts) and next_part.upper() in ['PLATINUM', 'GOLD', 'SILVER', 'BRONZE']:
                        # Include tier and model number (e.g., "Platinum 8573C")
                        model_short = f"Xeon {next_part} {parts[i+2]}"
                    elif next_part.upper() not in ['PROCESSOR', 'CPU']:
                        # Just model number (e.g., "8259CL")
                        model_short = f"Xeon {next_part}"
                    break
        elif 'AMD' in model and 'EPYC' in model:
            # Try to extract model number
            parts = model.split()
            for i, part in enumerate(parts):
                if 'EPYC' in part and i+1 < len(parts):
                    model_short = f"EPYC {parts[i+1]}"
                    break
            else:
                model_short = "AMD EPYC"
        elif 'Neoverse' in model:
            model_short = model.split()[0]  # Just "Neoverse-N1"
        else:
            # Take first 20 chars
            model_short = model[:20]

        if short:
            return f"{model_short} • {cores}c"
        else:
            return {
                'label': f"{model_short} • {cores}c",
                'full_model': model,
                'cores': cores,
                'arch': arch,
                'arch_icon': '🔷' if arch == 'x86_64' else '🔶' if arch == 'aarch64' else '❓'
            }
    except:
        if short:
            return "Unknown System"
        else:
            return {
                'label': "Unknown System",
                'full_model': 'Unknown',
                'cores': 0,
                'arch': 'unknown',
                'arch_icon': '❓'
            }

def get_os_label(doc):
    """Create OS label: RHEL version + kernel."""
    try:
        os_info = doc.get('system_under_test', {}).get('operating_system', {})
        version = os_info.get('version', 'unknown')
        kernel = os_info.get('kernel_version', 'unknown')

        # Simplify kernel version (just major.minor)
        if kernel and kernel != 'unknown':
            kernel_parts = kernel.split('.')
            if len(kernel_parts) >= 2:
                kernel_short = f"{kernel_parts[0]}.{kernel_parts[1]}"
            else:
                kernel_short = kernel[:10]
        else:
            kernel_short = 'unknown'

        return f"RHEL {version} (k{kernel_short})"
    except:
        return "Unknown OS"

def fetch_coverage_data(client, index):
    """Fetch all relevant data for coverage analysis."""

    print("🔍 Fetching coverage data from OpenSearch...")

    query = {
        "size": 10000,
        "_source": [
            "metadata.cloud_provider",
            "metadata.instance_type",
            "system_under_test.hardware.cpu",
            "system_under_test.operating_system",
            "test.name"
        ]
    }

    result = client.search(index=index, body=query)
    docs = result['hits']['hits']

    print(f"✅ Retrieved {len(docs):,} documents")

    return docs

def build_coverage_matrix(docs):
    """
    Build coverage data structure.

    Returns:
    - matrix: dict[platform][system_info][benchmark] = set of OS builds
    - benchmarks: set of all benchmark names
    - platforms: dict of platform -> system count
    - system_metadata: dict[platform][system_label] = full system info
    """

    matrix = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    benchmarks = set()
    platform_stats = defaultdict(lambda: {'systems': set(), 'os_builds': set(), 'test_count': 0})
    system_metadata = defaultdict(dict)

    for hit in docs:
        doc = hit['_source']

        # Extract dimensions
        platform = doc.get('metadata', {}).get('cloud_provider', 'unknown')
        system_info = get_system_label(doc, short=False)
        system_label = system_info['label']
        os_build = get_os_label(doc)
        benchmark = doc.get('test', {}).get('name', 'unknown')

        # Update matrix (use label as key)
        matrix[platform][system_label][benchmark].add(os_build)

        # Store full system metadata
        if system_label not in system_metadata[platform]:
            system_metadata[platform][system_label] = system_info

        # Track benchmarks
        benchmarks.add(benchmark)

        # Track platform stats
        platform_stats[platform]['systems'].add(system_label)
        platform_stats[platform]['os_builds'].add(os_build)
        platform_stats[platform]['test_count'] += 1

    return matrix, sorted(benchmarks), platform_stats, system_metadata

def calculate_executive_summary(matrix, benchmarks):
    """
    Calculate executive summary metrics for the dashboard.

    Returns:
    - coverage_score: % of system×benchmark combos with 2+ OS builds
    - critical_gaps: Top 3 platforms/systems with no multi-release coverage
    - strong_coverage: Top 3 system×benchmark combos with best coverage
    - recommendation: Which systems to standardize on
    """

    # Calculate overall coverage score
    total_combos = 0
    viable_combos = 0  # 2+ OS builds

    platform_coverage = {}
    system_benchmark_coverage = []

    for platform, systems in matrix.items():
        platform_viable = 0
        platform_total = 0

        for system, benchmark_dict in systems.items():
            for benchmark, os_builds in benchmark_dict.items():
                total_combos += 1
                platform_total += 1

                os_count = len(os_builds)

                if os_count >= 2:
                    viable_combos += 1
                    platform_viable += 1

                # Track for best coverage
                system_benchmark_coverage.append({
                    'platform': platform,
                    'system': system,
                    'benchmark': benchmark,
                    'os_count': os_count
                })

        platform_coverage[platform] = {
            'viable': platform_viable,
            'total': platform_total,
            'score': (platform_viable / platform_total * 100) if platform_total > 0 else 0
        }

    overall_score = (viable_combos / total_combos * 100) if total_combos > 0 else 0

    # Find critical gaps (lowest coverage platforms)
    gaps = sorted(platform_coverage.items(), key=lambda x: x[1]['score'])[:3]

    # Find strong coverage (highest OS build counts)
    strong = sorted(system_benchmark_coverage, key=lambda x: x['os_count'], reverse=True)[:3]

    # Generate recommendation based on systems with best coverage
    system_scores = defaultdict(lambda: {'total': 0, 'viable': 0, 'benchmarks': set()})

    for platform, systems in matrix.items():
        for system, benchmark_dict in systems.items():
            for benchmark, os_builds in benchmark_dict.items():
                system_scores[system]['total'] += 1
                system_scores[system]['benchmarks'].add(benchmark)
                if len(os_builds) >= 2:
                    system_scores[system]['viable'] += 1

    # Rank by both viable coverage and benchmark diversity
    ranked_systems = sorted(
        system_scores.items(),
        key=lambda x: (x[1]['viable'], len(x[1]['benchmarks'])),
        reverse=True
    )[:3]

    return {
        'overall_score': overall_score,
        'total_combos': total_combos,
        'viable_combos': viable_combos,
        'critical_gaps': gaps,
        'strong_coverage': strong,
        'recommended_systems': ranked_systems
    }

def generate_html_visualization(matrix, benchmarks, platform_stats, system_metadata, output_file):
    """Generate interactive HTML visualization using Plotly with Bootstrap tabs."""

    print("\n📊 Generating HTML visualization...")

    # Calculate executive summary
    print("📈 Calculating executive summary...")
    summary = calculate_executive_summary(matrix, benchmarks)

    # Build HTML with embedded Plotly
    html_parts = []

    # HTML header with Bootstrap
    html_parts.append("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>HeatSeek - Performance Test Coverage</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }
        .header {
            background: white;
            padding: 30px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        h1 {
            margin: 0 0 10px 0;
            color: #cc0000;
            font-size: 32px;
        }
        .subtitle {
            color: #666;
            font-size: 14px;
        }
        .executive-summary {
            background: white;
            padding: 25px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .summary-title {
            font-size: 20px;
            font-weight: bold;
            color: #333;
            margin-bottom: 20px;
            border-bottom: 2px solid #cc0000;
            padding-bottom: 10px;
        }
        .score-display {
            text-align: center;
            padding: 20px;
            background: linear-gradient(135deg, #cc0000 0%, #a00000 100%);
            color: white;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .score-number {
            font-size: 48px;
            font-weight: bold;
            margin-bottom: 5px;
        }
        .score-label {
            font-size: 14px;
            opacity: 0.9;
        }
        .summary-section {
            margin-bottom: 20px;
        }
        .summary-section h3 {
            font-size: 16px;
            font-weight: bold;
            color: #cc0000;
            margin-bottom: 10px;
        }
        .gap-item, .strong-item, .rec-item {
            padding: 10px;
            background: #f9f9f9;
            border-left: 4px solid #cc0000;
            margin-bottom: 10px;
            border-radius: 4px;
        }
        .gap-item { border-left-color: #dc3545; }
        .strong-item { border-left-color: #38761d; }
        .rec-item { border-left-color: #0066cc; }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .stat-label {
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
            margin-bottom: 5px;
            font-weight: 600;
        }
        .stat-value {
            font-size: 28px;
            font-weight: bold;
            color: #333;
        }
        .platform-tabs {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .nav-tabs {
            border-bottom: 2px solid #dee2e6;
            margin-bottom: 20px;
        }
        .nav-tabs .nav-link {
            color: #666;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 14px;
            padding: 12px 20px;
            border: none;
            border-bottom: 3px solid transparent;
        }
        .nav-tabs .nav-link:hover {
            color: #cc0000;
            border-color: transparent;
            background: transparent;
        }
        .nav-tabs .nav-link.active {
            color: #cc0000;
            background: transparent;
            border-color: transparent transparent #cc0000 transparent;
            font-weight: bold;
        }
        .tab-pane {
            min-height: 400px;
        }
        .platform-info {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-around;
            flex-wrap: wrap;
            gap: 15px;
        }
        .platform-info-item {
            text-align: center;
        }
        .platform-info-label {
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
            font-weight: 600;
        }
        .platform-info-value {
            font-size: 20px;
            font-weight: bold;
            color: #333;
        }
        .legend {
            background: white;
            padding: 25px;
            margin-top: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .legend-title {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 15px;
            color: #333;
        }
        .color-legend {
            display: flex;
            gap: 15px;
            margin: 15px 0;
            flex-wrap: wrap;
        }
        .color-item {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .color-box {
            width: 40px;
            height: 25px;
            border-radius: 4px;
            border: 1px solid #ddd;
        }
        .filter-panel {
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .filter-panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #cc0000;
        }
        .filter-panel-title {
            font-size: 18px;
            font-weight: bold;
            color: #333;
        }
        .filter-controls {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
        }
        .filter-row {
            display: flex;
            gap: 20px;
            margin-bottom: 15px;
            flex-wrap: wrap;
            align-items: center;
        }
        .filter-group {
            flex: 1;
            min-width: 200px;
        }
        .filter-label {
            font-size: 13px;
            font-weight: 600;
            color: #333;
            margin-bottom: 5px;
            display: block;
        }
        .filter-status {
            font-size: 13px;
            color: #666;
            font-style: italic;
            margin-top: 10px;
        }
        .arch-radio-group {
            display: flex;
            gap: 15px;
        }
        .arch-radio-group label {
            display: flex;
            align-items: center;
            gap: 5px;
            cursor: pointer;
            font-weight: normal;
        }
        .arch-radio-group input[type="radio"] {
            cursor: pointer;
        }
        .slider-container {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .slider-value {
            font-weight: bold;
            color: #cc0000;
            min-width: 60px;
        }
        @media (max-width: 768px) {
            .stats {
                grid-template-columns: 1fr;
            }
            .filter-row {
                flex-direction: column;
                gap: 15px;
            }
            .filter-group {
                width: 100%;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>HeatSeek - Performance Test Coverage</h1>
        <div class="subtitle">
            Red Hat Enterprise Linux Performance Testing Coverage Analysis<br>
            Generated: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """
        </div>
    </div>
""")

    # Executive Summary Section (Priority 2)
    html_parts.append(f"""
    <div class="executive-summary">
        <div class="summary-title">Executive Summary <span id="filter-indicator" style="font-size: 14px; color: #666; font-weight: normal;"></span></div>

        <div class="row">
            <div class="col-md-4">
                <div class="score-display">
                    <div class="score-number" id="overall-score">{summary['overall_score']:.1f}%</div>
                    <div class="score-label">Overall Coverage Score</div>
                    <div style="font-size: 12px; margin-top: 10px;" id="coverage-details">
                        {summary['viable_combos']:,} of {summary['total_combos']:,} combinations<br>
                        have multi-release coverage (2+ OS builds)
                    </div>
                </div>
            </div>

            <div class="col-md-8">
                <div class="summary-section">
                    <h3>Critical Gaps (Lowest Coverage Platforms)</h3>
""")

    for platform, stats in summary['critical_gaps']:
        html_parts.append(f"""
                    <div class="gap-item">
                        <strong>{platform.upper()}</strong>: {stats['score']:.1f}% coverage
                        ({stats['viable']} of {stats['total']} combinations viable)
                    </div>
""")

    html_parts.append("""
                </div>

                <div class="summary-section">
                    <h3>Strong Coverage (Best System×Benchmark Combinations)</h3>
""")

    for item in summary['strong_coverage']:
        html_parts.append(f"""
                    <div class="strong-item">
                        <strong>{item['system']}</strong> on {item['platform']} running <strong>{item['benchmark']}</strong>
                        <br><span style="color: #38761d; font-weight: bold;">{item['os_count']} OS builds tested</span>
                    </div>
""")

    html_parts.append("""
                </div>

                <div class="summary-section">
                    <h3>Actionable Recommendations</h3>
""")

    html_parts.append("""
                    <div class="rec-item">
                        <strong>Standardize testing on these systems for best regression detection:</strong>
                        <ul style="margin: 10px 0 0 0; padding-left: 20px;">
""")

    for system, scores in summary['recommended_systems']:
        html_parts.append(f"""
                            <li><strong>{system}</strong>
                            ({scores['viable']} viable combinations across {len(scores['benchmarks'])} benchmarks)</li>
""")

    html_parts.append("""
                        </ul>
                        <div style="margin-top: 10px; font-size: 13px; color: #666;">
                            Focus: Increase OS build diversity on these proven systems to maximize regression detection capability.
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
""")

    # Overall statistics
    total_platforms = len(matrix)
    total_systems = sum(len(systems) for systems in matrix.values())
    total_benchmarks = len(benchmarks)
    total_combinations = sum(
        sum(len(benchmarks_dict) for benchmarks_dict in systems.values())
        for systems in matrix.values()
    )

    html_parts.append(f"""
    <div class="stats">
        <div class="stat-card">
            <div class="stat-label">Platforms</div>
            <div class="stat-value">{total_platforms}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Unique Systems</div>
            <div class="stat-value">{total_systems}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Benchmarks</div>
            <div class="stat-value">{total_benchmarks}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">System×Benchmark Combinations</div>
            <div class="stat-value">{total_combinations}</div>
        </div>
    </div>
""")

    # Filter Panel (Priority 4)
    benchmarks_json = json.dumps(benchmarks)
    html_parts.append(f"""
    <div class="filter-panel">
        <div class="filter-panel-header">
            <div class="filter-panel-title">🔍 Filters</div>
            <button class="btn btn-sm btn-outline-secondary" onclick="resetFilters()">Reset</button>
        </div>
        <div class="filter-controls">
            <div class="filter-row">
                <div class="filter-group">
                    <label class="filter-label" for="benchmark-filter">Benchmark</label>
                    <select id="benchmark-filter" class="form-select" multiple size="5" onchange="applyFilters()">
                        <option value="all" selected>All Benchmarks</option>
""")

    for benchmark in benchmarks:
        html_parts.append(f"""                        <option value="{benchmark}">{benchmark}</option>
""")

    html_parts.append("""
                    </select>
                    <small class="text-muted">Hold Ctrl/Cmd to select multiple</small>
                </div>

                <div class="filter-group">
                    <label class="filter-label">Architecture</label>
                    <div class="arch-radio-group">
                        <label>
                            <input type="radio" name="arch-filter" value="all" checked onchange="applyFilters()">
                            All
                        </label>
                        <label>
                            <input type="radio" name="arch-filter" value="x86_64" onchange="applyFilters()">
                            x86_64 🔷
                        </label>
                        <label>
                            <input type="radio" name="arch-filter" value="aarch64" onchange="applyFilters()">
                            aarch64 🔶
                        </label>
                    </div>
                </div>
            </div>

            <div class="filter-row">
                <div class="filter-group">
                    <label class="filter-label" for="coverage-slider">
                        Minimum Coverage <span class="slider-value" id="min-coverage-value">0+ OS builds</span>
                    </label>
                    <div class="slider-container">
                        <input type="range" class="form-range" id="coverage-slider" min="0" max="5" value="0"
                               oninput="updateCoverageLabel(); applyFilters()">
                    </div>
                </div>

                <div class="filter-group">
                    <label class="filter-label" for="system-search">Search Systems</label>
                    <input type="text" id="system-search" class="form-control"
                           placeholder="e.g., 'Xeon', 'EPYC', '96c'" oninput="debouncedFilter()">
                </div>
            </div>

            <div class="filter-status" id="filter-status">
                Showing all systems
            </div>
        </div>
    </div>

    <script>
        // Debounce search input
        let searchTimeout;
        function debouncedFilter() {{
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(applyFilters, 300);
        }}

        function updateCoverageLabel() {{
            const value = document.getElementById('coverage-slider').value;
            document.getElementById('min-coverage-value').textContent = value + '+ OS builds';
        }}
    </script>
""")

    # Bootstrap tabs for platforms (Priority 1)
    html_parts.append("""
    <div class="platform-tabs">
        <ul class="nav nav-tabs" id="platformTabs" role="tablist">
""")

    # Generate tab headers
    platforms = sorted(matrix.keys())
    for i, platform in enumerate(platforms):
        active = "active" if i == 0 else ""
        platform_id = platform.replace(' ', '_').lower()
        html_parts.append(f"""
            <li class="nav-item" role="presentation">
                <button class="nav-link {active}" id="{platform_id}-tab" data-bs-toggle="tab"
                        data-bs-target="#{platform_id}" type="button" role="tab"
                        aria-controls="{platform_id}" aria-selected="{"true" if i == 0 else "false"}">
                    {platform.upper()}
                </button>
            </li>
""")

    html_parts.append("""
        </ul>

        <div class="tab-content" id="platformTabContent">
""")

    # Generate tab content for each platform
    plot_id = 0

    for i, platform in enumerate(platforms):
        active = "show active" if i == 0 else ""
        platform_id = platform.replace(' ', '_').lower()
        systems = matrix[platform]
        stats = platform_stats[platform]

        html_parts.append(f"""
            <div class="tab-pane fade {active}" id="{platform_id}" role="tabpanel" aria-labelledby="{platform_id}-tab">
                <div class="platform-info">
                    <div class="platform-info-item">
                        <div class="platform-info-label">Systems</div>
                        <div class="platform-info-value">{len(stats['systems'])}</div>
                    </div>
                    <div class="platform-info-item">
                        <div class="platform-info-label">OS Builds</div>
                        <div class="platform-info-value">{len(stats['os_builds'])}</div>
                    </div>
                    <div class="platform-info-item">
                        <div class="platform-info-label">Total Tests</div>
                        <div class="platform-info-value">{stats['test_count']:,}</div>
                    </div>
                </div>
                <div id="plot_{plot_id}"></div>
            </div>
""")

        # Build matrix data for this platform (Priority 3: Better labels + coverage metrics)
        system_list = sorted(systems.keys())
        system_meta = system_metadata[platform]

        # Matrix: rows = systems, cols = benchmarks
        z_data = []  # Number of OS builds tested
        hover_data = []  # Detailed hover text
        y_labels = []  # System labels with architecture icons and coverage

        for system in system_list:
            row_z = []
            row_hover = []

            # Get system metadata
            meta = system_meta.get(system, {
                'arch_icon': '❓',
                'full_model': 'Unknown',
                'cores': 0,
                'arch': 'unknown'
            })

            # Calculate coverage for this system (how many benchmarks covered)
            benchmarks_covered = sum(1 for b in benchmarks if len(systems[system].get(b, set())) > 0)
            coverage_text = f"{benchmarks_covered}/{len(benchmarks)}"

            # Build row label with icon and coverage
            y_label = f"{meta['arch_icon']} {system} [{coverage_text}]"
            y_labels.append(y_label)

            for benchmark in benchmarks:
                os_builds = systems[system].get(benchmark, set())
                count = len(os_builds)
                row_z.append(count)

                if count > 0:
                    os_list = '<br>'.join(sorted(os_builds))
                    hover_text = (
                        f"<b>System:</b> {meta['full_model']}<br>"
                        f"<b>Cores:</b> {meta['cores']}<br>"
                        f"<b>Architecture:</b> {meta['arch']}<br>"
                        f"<b>Benchmark:</b> {benchmark}<br>"
                        f"<br><b>{count} OS build(s):</b><br>{os_list}"
                    )
                else:
                    hover_text = (
                        f"<b>System:</b> {meta['full_model']}<br>"
                        f"<b>Cores:</b> {meta['cores']}<br>"
                        f"<b>Architecture:</b> {meta['arch']}<br>"
                        f"<b>Benchmark:</b> {benchmark}<br>"
                        f"<br>❌ No coverage"
                    )

                row_hover.append(hover_text)

            z_data.append(row_z)
            hover_data.append(row_hover)

        # Store system architectures for filtering
        system_archs = [system_meta.get(s, {}).get('arch', 'unknown') for s in system_list]

        # Create Plotly heatmap with improved color scale (Priority 1)
        html_parts.append(f"""
    <script>
        // Store original unfiltered data for plot {plot_id}
        var originalData_{plot_id} = {{
            z: {json.dumps(z_data)},
            x: {json.dumps(benchmarks)},
            y: {json.dumps(y_labels)},
            text: {json.dumps(hover_data)},
            archs: {json.dumps(system_archs)},
            systemLabels: {json.dumps(system_list)}
        }};

        var data_{plot_id} = [{{
            type: 'heatmap',
            z: {json.dumps(z_data)},
            x: {json.dumps(benchmarks)},
            y: {json.dumps(y_labels)},
            text: {json.dumps(hover_data)},
            hovertemplate: '%{{text}}<extra></extra>',
            colorscale: [
                [0,    '#e0e0e0'],   /* Gray: No coverage (0 OS builds) */
                [0.15, '#ffd966'],   /* Yellow: Insufficient (1 OS build - can't compare) */
                [0.3,  '#93c47d'],   /* Light green: Minimal viable (2 OS builds) */
                [0.5,  '#6aa84f'],   /* Green: Good (3-4 OS builds) */
                [1,    '#38761d']    /* Dark green: Excellent (5+ OS builds) */
            ],
            colorbar: {{
                title: 'Coverage<br>Quality',
                tickmode: 'array',
                tickvals: [0, 1, 2, 3, 5],
                ticktext: [
                    'None',
                    'Insufficient',
                    'Minimal',
                    'Good',
                    'Excellent'
                ],
                len: 0.8
            }},
            zmin: 0,
            zmax: 6
        }}];

        var layout_{plot_id} = {{
            xaxis: {{
                title: 'Benchmark',
                tickangle: -45,
                side: 'bottom',
                automargin: true
            }},
            yaxis: {{
                title: 'System Configuration [Benchmarks Covered]',
                automargin: true,
                tickfont: {{
                    size: 11
                }}
            }},
            margin: {{
                l: 300,
                r: 120,
                t: 30,
                b: 150
            }},
            height: {max(500, len(system_list) * 35)},
            paper_bgcolor: 'white',
            plot_bgcolor: 'white'
        }};

        var config_{plot_id} = {{
            responsive: true,
            displayModeBar: true,
            displaylogo: false,
            modeBarButtonsToRemove: ['lasso2d', 'select2d']
        }};

        Plotly.newPlot('plot_{plot_id}', data_{plot_id}, layout_{plot_id}, config_{plot_id});
    </script>
""")

        plot_id += 1

    # Close tabs structure
    html_parts.append("""
        </div>
    </div>
""")

    # Enhanced legend with color guide (Priority 1)
    html_parts.append("""
    <div class="legend">
        <div class="legend-title">How to Read This Matrix</div>

        <div class="row">
            <div class="col-md-6">
                <h4 style="font-size: 14px; font-weight: bold; margin-bottom: 10px;">Color Scale</h4>
                <div class="color-legend">
                    <div class="color-item">
                        <div class="color-box" style="background: #e0e0e0;"></div>
                        <div><strong>Gray</strong>: No coverage (0 OS builds)</div>
                    </div>
                    <div class="color-item">
                        <div class="color-box" style="background: #ffd966;"></div>
                        <div><strong>Yellow</strong>: Insufficient (1 OS build - can't compare)</div>
                    </div>
                    <div class="color-item">
                        <div class="color-box" style="background: #93c47d;"></div>
                        <div><strong>Light Green</strong>: Minimal viable (2 OS builds)</div>
                    </div>
                    <div class="color-item">
                        <div class="color-box" style="background: #6aa84f;"></div>
                        <div><strong>Green</strong>: Good (3-4 OS builds)</div>
                    </div>
                    <div class="color-item">
                        <div class="color-box" style="background: #38761d;"></div>
                        <div><strong>Dark Green</strong>: Excellent (5+ OS builds)</div>
                    </div>
                </div>
            </div>

            <div class="col-md-6">
                <h4 style="font-size: 14px; font-weight: bold; margin-bottom: 10px;">Legend Symbols</h4>
                <ul style="margin: 0; padding-left: 20px; line-height: 1.8;">
                    <li><strong>🔷</strong> x86_64 architecture</li>
                    <li><strong>🔶</strong> aarch64 architecture</li>
                    <li><strong>[X/Y]</strong> Benchmarks covered (X of Y total)</li>
                </ul>
            </div>
        </div>

        <div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid #ddd;">
            <h4 style="font-size: 14px; font-weight: bold; margin-bottom: 10px;">Understanding the Data</h4>
            <ul style="margin: 5px 0; padding-left: 20px; line-height: 1.8;">
                <li><strong>Rows</strong>: System configurations (architecture icon + CPU model + core count + coverage)</li>
                <li><strong>Columns</strong>: Performance benchmarks</li>
                <li><strong>Cell Color</strong>: Coverage quality based on number of different OS builds tested</li>
                <li><strong>Hover</strong>: Mouse over cells to see full system details and which RHEL versions were tested</li>
            </ul>
        </div>

        <div style="margin-top: 15px; padding: 15px; background: #f0f8ff; border-left: 4px solid #0066cc; border-radius: 4px;">
            <strong>Coverage Goal:</strong> For valid regression detection, we need the <strong>same system×benchmark</strong>
            tested across <strong>multiple consecutive RHEL releases</strong>. Aim for green cells (3+ OS builds) to establish
            reliable performance baselines and detect regressions accurately.
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>

    <script>
        // Global filter state
        const allBenchmarks = {json.dumps(benchmarks)};
        const totalPlots = {plot_id};

        function getFilteredData(plotId, benchmarkIndices, rowIndices) {{
            const orig = window['originalData_' + plotId];

            // Filter columns (benchmarks)
            const filteredX = benchmarkIndices.map(i => orig.x[i]);

            // Filter rows (systems) and their corresponding z data
            const filteredY = rowIndices.map(i => orig.y[i]);
            const filteredZ = rowIndices.map(rowIdx =>
                benchmarkIndices.map(colIdx => orig.z[rowIdx][colIdx])
            );
            const filteredText = rowIndices.map(rowIdx =>
                benchmarkIndices.map(colIdx => orig.text[rowIdx][colIdx])
            );

            return {{
                x: filteredX,
                y: filteredY,
                z: filteredZ,
                text: filteredText
            }};
        }}

        function applyFilters() {{
            // Get filter values
            const benchmarkSelect = document.getElementById('benchmark-filter');
            const selectedBenchmarks = Array.from(benchmarkSelect.selectedOptions)
                .map(opt => opt.value)
                .filter(v => v !== 'all');

            const archFilter = document.querySelector('input[name="arch-filter"]:checked').value;
            const minCoverage = parseInt(document.getElementById('coverage-slider').value);
            const searchQuery = document.getElementById('system-search').value.toLowerCase().trim();

            // Determine which benchmark columns to show
            let benchmarkIndices;
            if (selectedBenchmarks.length === 0 || benchmarkSelect.selectedOptions[0]?.value === 'all') {{
                benchmarkIndices = allBenchmarks.map((_, i) => i);
            }} else {{
                benchmarkIndices = selectedBenchmarks.map(b => allBenchmarks.indexOf(b)).filter(i => i >= 0);
            }}

            // Track total and hidden system counts across all platforms
            let totalSystemsAll = 0;
            let visibleSystemsAll = 0;
            let totalCombos = 0;
            let viableCombos = 0;

            // Filter each plot
            for (let plotId = 0; plotId < totalPlots; plotId++) {{
                const orig = window['originalData_' + plotId];
                if (!orig) continue;

                // Determine which rows (systems) to show
                const rowIndices = [];
                for (let i = 0; i < orig.y.length; i++) {{
                    totalSystemsAll++;

                    // Architecture filter
                    if (archFilter !== 'all' && orig.archs[i] !== archFilter) {{
                        continue;
                    }}

                    // Search filter (search in both display label and original system label)
                    if (searchQuery && !orig.y[i].toLowerCase().includes(searchQuery) &&
                        !orig.systemLabels[i].toLowerCase().includes(searchQuery)) {{
                        continue;
                    }}

                    // Coverage filter (check if ALL benchmarks have fewer than threshold)
                    if (minCoverage > 0) {{
                        const rowData = orig.z[i];
                        const maxCoverageInRow = Math.max(...rowData);
                        if (maxCoverageInRow < minCoverage) {{
                            continue;
                        }}
                    }}

                    rowIndices.push(i);
                    visibleSystemsAll++;
                }}

                // Get filtered data
                const filtered = getFilteredData(plotId, benchmarkIndices, rowIndices);

                // Calculate coverage stats for this filtered data
                for (let row of filtered.z) {{
                    for (let cell of row) {{
                        totalCombos++;
                        if (cell >= 2) {{
                            viableCombos++;
                        }}
                    }}
                }}

                // Update plot
                const plotDiv = 'plot_' + plotId;
                const update = {{
                    z: [filtered.z],
                    x: [filtered.x],
                    y: [filtered.y],
                    text: [filtered.text]
                }};

                const layoutUpdate = {{
                    height: Math.max(500, filtered.y.length * 35)
                }};

                Plotly.react(plotDiv, [{{
                    type: 'heatmap',
                    z: filtered.z,
                    x: filtered.x,
                    y: filtered.y,
                    text: filtered.text,
                    hovertemplate: '%{{text}}<extra></extra>',
                    colorscale: [
                        [0,    '#e0e0e0'],
                        [0.15, '#ffd966'],
                        [0.3,  '#93c47d'],
                        [0.5,  '#6aa84f'],
                        [1,    '#38761d']
                    ],
                    colorbar: {{
                        title: 'Coverage<br>Quality',
                        tickmode: 'array',
                        tickvals: [0, 1, 2, 3, 5],
                        ticktext: ['None', 'Insufficient', 'Minimal', 'Good', 'Excellent'],
                        len: 0.8
                    }},
                    zmin: 0,
                    zmax: 6
                }}], layoutUpdate);
            }}

            // Update filter status
            const hiddenSystems = totalSystemsAll - visibleSystemsAll;
            let statusText = '';
            if (hiddenSystems === 0) {{
                statusText = 'Showing all systems';
            }} else {{
                statusText = `Showing: ${{visibleSystemsAll}} systems (${{hiddenSystems}} hidden by filters)`;
            }}

            // Update benchmark count
            const showingBenchmarks = benchmarkIndices.length;
            if (showingBenchmarks < allBenchmarks.length) {{
                statusText += ` • ${{showingBenchmarks}} of ${{allBenchmarks.length}} benchmarks`;
            }}

            document.getElementById('filter-status').textContent = statusText;

            // Update executive summary if filters are active
            const filtersActive = hiddenSystems > 0 || showingBenchmarks < allBenchmarks.length;
            const coverageScore = totalCombos > 0 ? (viableCombos / totalCombos * 100).toFixed(1) : 0;

            if (filtersActive) {{
                document.getElementById('filter-indicator').textContent = '(Filtered View)';
                document.getElementById('overall-score').textContent = coverageScore + '%';
                document.getElementById('coverage-details').innerHTML =
                    `${{viableCombos.toLocaleString()}} of ${{totalCombos.toLocaleString()}} combinations<br>` +
                    `have multi-release coverage (2+ OS builds)`;
            }} else {{
                document.getElementById('filter-indicator').textContent = '';
                // Reset to original values
                document.getElementById('overall-score').textContent = '{summary["overall_score"]:.1f}%';
                document.getElementById('coverage-details').innerHTML =
                    '{summary["viable_combos"]:,} of {summary["total_combos"]:,} combinations<br>' +
                    'have multi-release coverage (2+ OS builds)';
            }}
        }}

        function resetFilters() {{
            // Reset all controls
            document.getElementById('benchmark-filter').selectedIndex = 0;
            document.querySelector('input[name="arch-filter"][value="all"]').checked = true;
            document.getElementById('coverage-slider').value = 0;
            document.getElementById('system-search').value = '';
            updateCoverageLabel();
            applyFilters();
        }}
    </script>
</body>
</html>
""")

    # Write to file
    html_content = '\n'.join(html_parts)

    with open(output_file, 'w') as f:
        f.write(html_content)

    print(f"✅ Visualization saved to: {output_file}")
    print(f"\n📂 Open in browser: file://{os.path.abspath(output_file)}")

def main():
    """Main execution."""
    index = os.getenv('OPENSEARCH_INDEX', 'zathras-results')
    output_file = 'heatseek.html'

    try:
        print("="*80)
        print("TEST COVERAGE MATRIX VISUALIZATION")
        print("="*80 + "\n")

        # Connect to OpenSearch
        print("🔌 Connecting to OpenSearch...")
        client = connect_to_opensearch()

        info = client.info()
        print(f"✅ Connected to OpenSearch {info['version']['number']}")
        print(f"📊 Index: {index}\n")

        # Fetch data
        docs = fetch_coverage_data(client, index)

        # Build coverage matrix
        print("\n📋 Building coverage matrix...")
        matrix, benchmarks, platform_stats, system_metadata = build_coverage_matrix(docs)
        print(f"✅ Matrix built: {len(matrix)} platforms, {len(benchmarks)} benchmarks")

        # Generate visualization
        generate_html_visualization(matrix, benchmarks, platform_stats, system_metadata, output_file)

        print("\n" + "="*80)
        print("✅ Done! Open the HTML file in your browser to explore coverage.")
        print("="*80 + "\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
