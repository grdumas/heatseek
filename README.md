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
- **Rich tooltips**: See exact RHEL versions, kernel info, and CPU details for each system×benchmark

### 🎯 Executive Summary
- **Coverage score**: Percentage of system×benchmark combinations viable for regression detection
- **Viable combinations**: Count of pairs with 2+ OS builds
- **Critical gaps**: Platforms/systems lacking multi-release data
- **Recommendations**: Which systems to standardize testing on

### 🔍 Interactive Filters
- **Benchmark filter**: Show specific benchmarks (coremark, pyperf, streams, etc.)
- **Architecture filter**: x86_64 vs aarch64
- **Coverage threshold**: Hide systems below minimum OS build count
- **System search**: Find specific CPU models (e.g., "Xeon", "EPYC", "96c")

## Quick Start

Choose your deployment mode:

### Option 1: Real-time Dashboard (Recommended)

Best for teams that need live updates after processing test results.

**Features:**
- Real-time data refresh (click "Refresh Data" to see latest results)
- Server-side filtering for fast queries
- REST API for automation
- 30-second intelligent caching

**Setup:**

```bash
# 1. Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure OpenSearch
cp .env.example .env
nano .env  # Add your credentials

# 3. Start server
uvicorn server:app --host 0.0.0.0 --port 8080

# 4. Open browser
# Visit: http://localhost:8080
```

See [Real-time Dashboard](#real-time-dashboard-details) section for full details.

### Option 2: Static HTML Generation

Best for periodic reporting or sharing coverage snapshots via email/Confluence.

**Features:**
- Standalone HTML file (no server needed)
- Works offline
- Easy to email or host on static web server

**Setup:**

```bash
# 1. Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install python-dotenv opensearch-py

# 2. Configure OpenSearch
cp .env.example .env
nano .env  # Add your credentials

# 3. Generate visualization
python3 visualize_test_coverage.py

# 4. Open result
firefox heatseek.html
```

See [Static HTML Generation](#static-html-generation-details) section for full details.

## Configuration

Both modes use the same `.env` configuration:

```bash
OPENSEARCH_HOST=your-opensearch-host.com
OPENSEARCH_PORT=443
OPENSEARCH_USERNAME=your-username
OPENSEARCH_PASSWORD=your-password
OPENSEARCH_INDEX=zathras-results
```

⚠️ **Never commit `.env` file to git!** It contains credentials.

## Real-time Dashboard Details

### API Endpoints

#### GET /api/coverage
Get coverage matrix with optional filters.

Query Parameters:
- `platform` - Filter by platform (AWS, Azure, GCP, etc.)
- `benchmark` - Filter by benchmark name
- `architecture` - Filter by CPU architecture (x86_64, aarch64)
- `min_builds` - Minimum number of OS builds (0-10)

Example:
```bash
curl "http://localhost:8080/api/coverage?platform=AWS&min_builds=2"
```

#### GET /api/summary
Get executive summary with coverage metrics.

Example:
```bash
curl http://localhost:8080/api/summary | jq
```

Response:
```json
{
  "coverage_score": 45.2,
  "total_combinations": 248,
  "viable_combinations": 112,
  "critical_gaps": ["IBM", "bare-metal"],
  "recommended_systems": ["m5.24xlarge", "Standard_D4s_v5", "n2-standard-32"],
  "generated_at": "2026-06-03T10:30:00.123456"
}
```

#### POST /api/refresh
Force cache refresh for immediate data updates.

```bash
curl -X POST http://localhost:8080/api/refresh
```

#### GET /api/benchmarks
Get list of all available benchmarks.

```bash
curl http://localhost:8080/api/benchmarks
```

#### GET /api/platform-summary
Get architectural breakdown for a specific platform.

```bash
curl "http://localhost:8080/api/platform-summary?platform=AWS"
```

#### GET /health
Health check endpoint for monitoring.

```bash
curl http://localhost:8080/health
```

### API Documentation

FastAPI provides automatic interactive documentation:
- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

### Architecture

```
┌─────────────┐
│   Browser   │ (Single-page HTML + vanilla JS)
└──────┬──────┘
       │ HTTP/JSON
       ↓
┌─────────────┐
│  FastAPI    │ (Python backend with 30s cache)
│   Server    │
└──────┬──────┘
       │
       ↓
┌─────────────┐
│ OpenSearch  │ (Existing zathras-results index)
└─────────────┘
```

### Performance

Tested on RHEL 9.3, 4 CPU cores, 8GB RAM:

| Metric | Value |
|--------|-------|
| Concurrent users | 12 |
| Requests/second | ~50 |
| Avg response time (cached) | 80ms |
| Avg response time (cache miss) | 1.8s |
| Memory usage | ~150MB |
| CPU usage (idle) | <5% |
| CPU usage (under load) | ~30% |

### Production Deployment

#### Quick Setup
```bash
# Install as systemd service
sudo cp heatseek.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable heatseek
sudo systemctl start heatseek

# Check status
sudo systemctl status heatseek
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete production deployment guide including:
- Systemd service configuration
- Nginx/Apache reverse proxy setup
- SSL/TLS configuration
- Monitoring and logging
- Performance tuning

### Development Mode
```bash
uvicorn server:app --reload --host 0.0.0.0 --port 8080
```

### Modifying Cache TTL

Edit `server.py`:

```python
def get_cache_key() -> str:
    """Change 30 to desired seconds"""
    now = datetime.now()
    bucket = now.replace(second=now.second // 30 * 30, microsecond=0)
    return bucket.isoformat()
```

## Static HTML Generation Details

### Deployment Options

#### Simple Static Hosting

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

#### Auto-Regenerate with Cron

Set up weekly regeneration:

```bash
# Add to crontab (regenerate every Sunday at 2 AM)
0 2 * * 0 cd /home/user/repos/heatseek && source venv/bin/activate && python3 visualize_test_coverage.py && cp heatseek.html /var/www/html/coverage.html
```

#### Simple Express Server (with API)

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

### Output Details

The generated HTML file (`heatseek.html`) is:
- **Standalone**: No external dependencies, works offline
- **Interactive**: Plotly.js embedded for zoom, pan, export
- **Responsive**: Works on desktop, tablet, mobile
- **Shareable**: Safe to email (no credentials embedded)

Typical file size: 200-400 KB depending on data volume.

### Customization

#### Change Time Range

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

#### Change Color Thresholds

Modify the `colorscale` in `generate_html_visualization()` to adjust when colors change.

## Use Cases

### For Test Engineers
**"I just processed 50 new test results - did this improve coverage?"**
- Use real-time dashboard
- Click "Refresh Data" button
- See updated coverage score in ~2 seconds

### For Test Infrastructure Teams
**"Which systems should we standardize on?"**
- Check Executive Summary → Recommendations section
- Look for systems with highest viable coverage % and benchmark diversity
- Use filters to compare x86_64 vs aarch64 options

**"Where are our biggest coverage gaps?"**
- Use filters: Min Coverage = 0, then scan for gray cells
- Critical gaps section shows platforms with 0% multi-release coverage

### For QA Leads
**"Can we detect regressions for coremark on x86_64?"**
- Filter: Benchmark = coremark, Architecture = x86_64
- Look for green cells (3+ OS builds)
- Hover over cells to see exact RHEL + kernel versions

**"Which RHEL versions are tested on our primary platform?"**
- Navigate to platform tab (e.g., AWS)
- Hover over cells for detailed version information

### For Engineering Managers
**"What's our overall test coverage health?"**
- Check coverage score in dashboard/summary
- Track improvement over time (refresh weekly or monthly)
- Share static HTML reports in status meetings

## Understanding the Visualizations

### Color Coding Legend

| Color | Meaning | OS Builds | Regression Detection |
|-------|---------|-----------|---------------------|
| **Gray** | No coverage | 0 | ❌ Impossible |
| **Yellow** | Insufficient | 1 | ❌ Nothing to compare to |
| **Light Green** | Minimal viable | 2 | ✅ Can compare 2 releases |
| **Green** | Good | 3-4 | ✅ Multiple comparisons |
| **Dark Green** | Excellent | 5+ | ✅ Strong trend analysis |

**Goal**: Maximize green cells by testing the same system×benchmark combination across consecutive RHEL releases.

### Coverage Score Interpretation

- **< 20%**: Fragmented infrastructure, limited regression detection capability
- **20-40%**: Partial coverage, some valid comparisons possible
- **40-60%**: Good coverage, regression detection viable for major benchmarks
- **60-80%**: Strong coverage, comprehensive regression monitoring possible
- **> 80%**: Excellent coverage, full regression detection across portfolio

## Data Source

Both modes pull data from the OpenSearch index configured in `.env`:

- **Index**: `zathras-results` (RHEL performance test results)
- **Fields used**:
  - `metadata.cloud_provider`: AWS, Azure, GCP, IBM, bare metal
  - `metadata.instance_type`: m5.24xlarge, Standard_D4s_v5, etc.
  - `system_under_test.hardware.cpu`: Model, cores, architecture
  - `system_under_test.operating_system`: RHEL version, kernel
  - `test.name`: Benchmark name (coremark, pyperf, streams, etc.)

## Troubleshooting

### Real-time Dashboard Issues

#### "Failed to load coverage data: JSON.parse" Error

This error occurs when the dashboard receives a non-JSON response from the API server.

Quick Diagnostics:
```bash
# 1. Check server configuration status
curl http://localhost:8080/api/config-status

# Expected response:
# {
#   "opensearch_host": "configured",
#   "opensearch_username": "configured",
#   "opensearch_password": "configured",
#   "opensearch_connection": "success"
# }

# 2. Test API endpoints directly (should return JSON, not HTML)
curl http://localhost:8080/api/summary
curl http://localhost:8080/api/coverage
```

Common Causes:

1. **Missing Environment Variables**
   ```bash
   # Ensure all required variables are set:
   export OPENSEARCH_HOST="your-opensearch-host.com"
   export OPENSEARCH_USERNAME="your-username"
   export OPENSEARCH_PASSWORD="your-password"
   export OPENSEARCH_INDEX="zathras-results"  # optional, defaults to zathras-results
   ```

2. **OpenSearch Connection Failure**
   - Check if host is reachable: `curl -k https://$OPENSEARCH_HOST:443`
   - Test authentication: `curl -k -u "$OPENSEARCH_USERNAME:$OPENSEARCH_PASSWORD" https://$OPENSEARCH_HOST:443`
   - Check server logs for connection errors

3. **Server Not Listening on All Interfaces (Remote Access)**
   ```bash
   # Use --host 0.0.0.0, not 127.0.0.1
   uvicorn server:app --host 0.0.0.0 --port 8080
   
   # Check firewall rules
   sudo firewall-cmd --add-port=8080/tcp --permanent
   sudo firewall-cmd --reload
   ```

4. **Browser Console Errors**
   - Open DevTools (F12) → Console tab for detailed error messages
   - Check Network tab to see actual API response content

#### Dashboard shows "No data"
```bash
# Check OpenSearch connectivity
curl -u user:pass https://opensearch-host:443/zathras-results/_count

# Verify environment variables
cat .env

# Check server logs
tail -f logs/heatseek.log
```

#### "Connection refused" errors
```bash
# Check server is running
curl http://localhost:8080/health

# Verify port
sudo lsof -i :8080

# Check firewall
sudo firewall-cmd --list-all
```

#### Stale data showing
```bash
# Force cache refresh
curl -X POST http://localhost:8080/api/refresh

# Or click "Refresh Data" button in UI
```

### Common Issues (Both Modes)

#### "No module named 'opensearchpy'"
```bash
source venv/bin/activate
pip install opensearch-py
# Or for real-time dashboard:
pip install -r requirements.txt
```

#### "Connection refused" or "Authentication failed"
Check `.env` file:
- Verify `OPENSEARCH_HOST` is correct (no http:// prefix)
- Confirm `OPENSEARCH_PORT` (often 443 for HTTPS, not 9200)
- Test credentials manually with curl

#### "Empty visualization" or "No data"
Check OpenSearch index:
- Verify index name in `.env` matches actual index
- Confirm data exists: `curl -u username:password https://host:443/index/_count`
- Check date range - data might be outside expected timeframe

#### Port Already in Use
```bash
# Find what's using the port
lsof -i :8080

# Use a different port
uvicorn server:app --host 0.0.0.0 --port 8001
```

#### Output file is too large (> 1 MB)
For static HTML generation:
- Large datasets generate big HTML files
- Consider filtering data by date range in the script
- Host on web server instead of emailing

## Project Structure

```
heatseek/
├── server.py                  # FastAPI backend for real-time dashboard
├── visualize_test_coverage.py # Static HTML generator
├── frontend/
│   └── index.html            # Single-page app for real-time dashboard
├── requirements.txt          # Python dependencies
├── .env                      # Configuration (not in git)
├── .env.example             # Configuration template
├── heatseek.service         # Systemd service file
├── DEPLOYMENT.md            # Production deployment guide
└── README.md                # This file
```

## Security Notes

⚠️ **Never commit `.env` file to git!** It contains credentials.

Both visualization modes:
- ✅ Use read-only OpenSearch credentials
- ✅ Safe to share generated output (no credentials embedded)
- ✅ No sensitive data storage
- ⚠️ Contain test metadata - keep behind company firewall

Real-time dashboard:
- ✅ No user authentication (relies on VPN/network security)
- ✅ Stateless architecture

## Development

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/
```

### Adding New API Endpoints

Edit `server.py`:

```python
@app.get("/api/your-endpoint")
async def your_endpoint():
    """Your endpoint description"""
    matrix, summary = get_cached_data(get_cache_key())
    # Your logic here
    return {"result": "data"}
```

## Migration Notes

### From v1.0 Static HTML to v2.0 Real-time Dashboard

v1.0 used static HTML generation. v2.0 offers both static generation and live API-backed dashboard.

**To migrate**:
1. Keep v1.0's `visualize_test_coverage.py` for backward compatibility
2. Deploy v2.0 real-time dashboard at new URL (e.g., `/coverage/live`)
3. Monitor usage for 2 weeks
4. Deprecate static-only workflow once users migrate

**Data compatibility**: Both modes read from the same OpenSearch index - no data migration needed.

## License

Internal Red Hat tool. Not for external distribution.

## Support

For questions or issues:
1. Check this README
2. Review [DEPLOYMENT.md](DEPLOYMENT.md) for production setup
3. Check API docs at http://localhost:8080/docs (real-time mode)
4. Review server logs: `sudo journalctl -u heatseek -f` (real-time mode)
5. Contact the Performance QA team

---

**Version**: 2.0.0  
**Last Updated**: 2026-06-03  
**Maintained by**: Performance QA Team
