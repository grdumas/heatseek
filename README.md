# HeatSeek

Interactive visualization tool for analyzing RHEL performance test coverage across platforms, systems, and benchmarks.

## Purpose

This tool helps test infrastructure teams and QA leads answer:
- **Where can we detect performance regressions?** (which system×benchmark combinations have multi-release data)
- **What are the coverage gaps?** (missing OS versions, platforms, or benchmarks)
- **Which systems should we standardize on?** (actionable recommendations)

## Features

### 📊 Interactive Coverage Heatmaps
- **Platform-organized**: Separate tabs for AWS, Azure, GCP, IBM Cloud, Bare Metal
- **Color-coded**: Green = good coverage (3+ OS builds), Yellow = insufficient (1 build), Gray = no data
- **Hover tooltips**: See exact RHEL versions and kernel info tested on each system×benchmark

### 🎯 Executive Summary
- **Coverage score**: % of system×benchmark combinations viable for regression detection
- **Critical gaps**: Platforms/systems lacking multi-release data
- **Strong coverage highlights**: Best-tested combinations
- **Recommendations**: Which 2-3 systems to standardize testing on

### 🔍 Interactive Filters
- **Benchmark filter**: Show specific benchmarks (coremark, pyperf, streams, etc.)
- **Architecture filter**: x86_64 vs aarch64
- **Coverage threshold**: Hide systems below minimum OS build count
- **System search**: Find specific CPU models (e.g., "Xeon", "EPYC", "96c")

## Quick Start

### 1. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install python-dotenv opensearch-py
```

### 2. Configure OpenSearch Connection

Copy `.env.example` to `.env` and fill in your OpenSearch credentials:

```bash
cp .env.example .env
nano .env  # Edit with your credentials
```

Required settings:
```bash
OPENSEARCH_HOST=your-opensearch-host.com
OPENSEARCH_PORT=443
OPENSEARCH_USERNAME=your-username
OPENSEARCH_PASSWORD=your-password
OPENSEARCH_INDEX=zathras-results
```

### 3. Generate Visualization

```bash
source venv/bin/activate
python3 visualize_test_coverage.py
```

This creates `heatseek.html` - a standalone HTML file you can:
- Open directly in a browser
- Host on a web server
- Share via email/Confluence

### 4. View Results

```bash
firefox heatseek.html
# or
google-chrome heatseek.html
```

## Deployment Options

### Option 1: Simple Static Hosting (Recommended)

Host the generated HTML on any web server:

```bash
# Apache
cp heatseek.html /var/www/html/coverage.html

# Nginx
cp heatseek.html /usr/share/nginx/html/coverage.html

# Python HTTP server (testing)
python3 -m http.server 8080
# Visit: http://localhost:8080/heatseek.html
```

### Option 2: Auto-Regenerate with Cron

Set up weekly regeneration:

```bash
# Add to crontab (regenerate every Sunday at 2 AM)
0 2 * * 0 cd /home/user/repos/heatseek && source venv/bin/activate && python3 visualize_test_coverage.py && cp heatseek.html /var/www/html/coverage.html
```

### Option 3: Simple Express Server (with API)

```bash
npm init -y
npm install express

# Create server.js:
cat > server.js << 'EOF'
const express = require('express');
const { execSync } = require('child_process');
const path = require('path');
const app = express();

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'heatseek.html'));
});

app.post('/api/regenerate', (req, res) => {
  try {
    execSync('source venv/bin/activate && python3 visualize_test_coverage.py', {
      cwd: __dirname,
      shell: '/bin/bash'
    });
    res.json({ status: 'success', message: 'Coverage regenerated' });
  } catch (error) {
    res.status(500).json({ status: 'error', message: error.message });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Coverage matrix server running on http://localhost:${PORT}`);
});
EOF

# Run server
node server.js
```

## Use Cases

### For Test Infrastructure Teams
**"Which systems should we standardize on?"**
- Check Executive Summary → Recommendations section
- Look for systems with highest viable coverage % and benchmark diversity

**"Where are our biggest coverage gaps?"**
- Use filters: Min Coverage = 0, then scan for gray cells
- Critical gaps section shows platforms with 0% multi-release coverage

### For QA Leads
**"Can we detect regressions for coremark on x86_64?"**
- Filter: Benchmark = coremark, Architecture = x86_64
- Look for green cells (3+ OS builds)

**"Which RHEL versions are tested on our primary platform?"**
- Navigate to platform tab (e.g., AWS)
- Hover over cells to see exact RHEL + kernel versions

### For Engineering Managers
**"What's our overall test coverage health?"**
- Check coverage score in Executive Summary
- Track improvement over time (regenerate monthly)

## Output

The generated HTML file (`heatseek.html`) is:
- **Standalone**: No external dependencies, works offline
- **Interactive**: Plotly.js embedded for zoom, pan, export
- **Responsive**: Works on desktop, tablet, mobile
- **Shareable**: Safe to email (no credentials embedded)

Typical file size: 200-400 KB depending on data volume.

## Data Source

Pulls data from OpenSearch index configured in `.env`:
- **Index**: `zathras-results` (RHEL performance test results)
- **Fields used**:
  - `metadata.cloud_provider`: AWS, Azure, GCP, IBM, bare metal
  - `metadata.instance_type`: m5.24xlarge, Standard_D4s_v5, etc.
  - `system_under_test.hardware.cpu`: Model, cores, architecture
  - `system_under_test.operating_system`: RHEL version, kernel
  - `test.name`: Benchmark name (coremark, pyperf, streams, etc.)

## Understanding the Colors

| Color | Meaning | OS Builds | Regression Detection |
|-------|---------|-----------|---------------------|
| **Gray** | No coverage | 0 | ❌ Impossible |
| **Yellow** | Insufficient | 1 | ❌ Nothing to compare to |
| **Light Green** | Minimal viable | 2 | ✅ Can compare 2 releases |
| **Green** | Good | 3-4 | ✅ Multiple comparisons |
| **Dark Green** | Excellent | 5+ | ✅ Strong trend analysis |

**Goal**: Maximize dark green cells by testing the same system×benchmark combination across consecutive RHEL releases.

## Coverage Score Interpretation

- **< 20%**: Fragmented infrastructure, limited regression detection capability
- **20-40%**: Partial coverage, some valid comparisons possible
- **40-60%**: Good coverage, regression detection viable for major benchmarks
- **60-80%**: Strong coverage, comprehensive regression monitoring possible
- **> 80%**: Excellent coverage, full regression detection across portfolio

## Troubleshooting

### "No module named 'opensearchpy'"
```bash
source venv/bin/activate
pip install opensearch-py
```

### "Connection refused" or "Authentication failed"
Check `.env` file:
- Verify `OPENSEARCH_HOST` is correct (no http:// prefix)
- Confirm `OPENSEARCH_PORT` (often 443 for HTTPS, not 9200)
- Test credentials manually with curl

### "Empty visualization" or "No data"
Check OpenSearch index:
- Verify index name in `.env` matches actual index
- Confirm data exists: `curl -u username:password https://host:443/index/_count`
- Check date range - data might be outside expected timeframe

### Output file is too large (> 1 MB)
- Large datasets generate big HTML files
- Consider filtering data by date range in the script
- Host on web server instead of emailing

## Customization

### Change Time Range

Edit `visualize_test_coverage.py`, modify the query:

```python
query = {
    "size": 10000,
    "query": {
        "range": {
            "metadata.test_timestamp": {
                "gte": "2026-01-01",  # Start date
                "lte": "2026-06-30"   # End date
            }
        }
    },
    "_source": [...]
}
```

### Add Custom Categories

Edit benchmark grouping logic if you want to group by category instead of individual benchmarks.

### Change Color Thresholds

Modify the `colorscale` in `generate_html_visualization()` to adjust when colors change.

## Security Notes

⚠️ **Never commit `.env` file to git!** It contains credentials.

The generated HTML file:
- ✅ Safe to share - no credentials embedded
- ✅ Works offline - all JavaScript/CSS inline or CDN
- ❌ Contains test metadata - don't share outside organization if data is confidential

## License

Internal Red Hat tool. Not for external distribution.

## Support

For questions or issues:
1. Check this README
2. Review the visualization's built-in legend
3. Contact the Performance QA team

---

**Last Updated**: 2026-06-02
**Version**: 1.0
