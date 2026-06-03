# HeatSeek v2.0 - Real-time Coverage Dashboard

Interactive, real-time visualization tool for analyzing RHEL performance test coverage across platforms, systems, and benchmarks.

## What's New in v2.0

### Real-time Updates
- **Live data refresh** - Engineers can click "Refresh Data" after processing test results to immediately see updated coverage
- **30-second intelligent caching** - Fresh enough for "just processed" workflow, light enough on OpenSearch
- **Server-side filtering** - Fast, responsive filtering without reloading all data

### Improved Architecture
- **FastAPI backend** - Clean REST API with automatic documentation
- **Single-page application** - Smooth, modern user experience with no page reloads
- **Efficient querying** - Only fetch data matching active filters

### Better User Experience
- **Platform tabs** - Quick switching between AWS, Azure, GCP, IBM Cloud, Bare Metal
- **Interactive heatmaps** - Hover for detailed OS version and CPU info
- **Real-time metrics** - Coverage score, viable combinations, and critical gaps update instantly
- **Responsive design** - Works on desktop, tablet, and mobile

## Quick Start

### 1. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure OpenSearch Connection

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
nano .env
```

Required settings:
```bash
OPENSEARCH_HOST=your-opensearch-host.com
OPENSEARCH_PORT=443
OPENSEARCH_USERNAME=your-username
OPENSEARCH_PASSWORD=your-password
OPENSEARCH_INDEX=zathras-results
```

### 3. Start the Server

```bash
source venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 8080
```

### 4. Open Dashboard

Visit: http://localhost:8080

## Features

### 📊 Interactive Coverage Heatmaps
- **Platform-organized**: Separate tabs for AWS, Azure, GCP, IBM Cloud, Bare Metal
- **Color-coded**: 
  - Gray = no data
  - Yellow = insufficient (1 build)
  - Light green = minimal viable (2 builds)
  - Green = good (3-4 builds)
  - Dark green = excellent (5+ builds)
- **Rich tooltips**: Hover to see exact RHEL versions, kernel info, CPU details

### 🎯 Real-time Executive Summary
- **Coverage score**: Percentage of system×benchmark combinations viable for regression detection
- **Viable combinations**: Count of pairs with 2+ OS builds
- **Total combinations**: All system×benchmark pairs discovered
- **Critical gaps**: Number of platforms lacking multi-release data

### 🔍 Interactive Filters
- **Benchmark filter**: Show specific benchmarks (coremark, pyperf, streams, etc.)
- **Architecture filter**: x86_64 vs aarch64
- **Coverage threshold**: Hide systems below minimum OS build count
- **Real-time application**: Filters update instantly without page reload

### 🔄 Manual Refresh
Engineers can click "Refresh Data" button after processing test batches to immediately see updated coverage scores without waiting for cache expiry.

## API Endpoints

### GET /api/coverage
Get coverage matrix with optional filters.

**Query Parameters**:
- `platform` - Filter by platform (AWS, Azure, GCP, etc.)
- `benchmark` - Filter by benchmark name
- `architecture` - Filter by CPU architecture (x86_64, aarch64)
- `min_builds` - Minimum number of OS builds (0-10)

**Example**:
```bash
curl "http://localhost:8080/api/coverage?platform=AWS&min_builds=2"
```

### GET /api/summary
Get executive summary with coverage metrics.

**Example**:
```bash
curl http://localhost:8080/api/summary | jq
```

**Response**:
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

### POST /api/refresh
Force cache refresh for immediate data updates.

**Example**:
```bash
curl -X POST http://localhost:8080/api/refresh
```

### GET /api/benchmarks
Get list of all available benchmarks.

**Example**:
```bash
curl http://localhost:8080/api/benchmarks
```

### GET /health
Health check endpoint for monitoring.

**Example**:
```bash
curl http://localhost:8080/health
```

## Use Cases

### For Test Engineers
**"I just processed 50 new test results - did this improve coverage?"**
1. Process your test batch
2. Open dashboard
3. Click "Refresh Data" button
4. See updated coverage score and heatmaps in ~2 seconds

### For Test Infrastructure Teams
**"Which systems should we standardize on?"**
1. Check Executive Summary metrics
2. Look for systems with highest coverage score
3. Use filters to compare x86_64 vs aarch64 options
4. Review recommended systems based on benchmark diversity

### For QA Leads
**"Can we detect regressions for coremark on AWS x86_64?"**
1. Select "AWS" platform tab
2. Filter: Benchmark = coremark, Architecture = x86_64
3. Look for green cells (3+ OS builds)
4. Hover to see specific RHEL versions tested

### For Engineering Managers
**"What's our overall test coverage health?"**
- Check coverage score in dashboard header
- Monitor viable combinations count
- Track improvement over time (refresh weekly)

## Architecture

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

### Why This Design?

1. **Real-time data** - Engineers see latest results without waiting for cron
2. **Server-side filtering** - Fast queries, don't send 10k records for 50 results
3. **Intelligent caching** - 30-second TTL balances freshness with OpenSearch load
4. **Stateless** - No database, all data from OpenSearch
5. **Simple deployment** - One systemd service, works for ~12 concurrent users

## Performance

- **Cache TTL**: 30 seconds (configurable)
- **Query size**: 10,000 records (last 90 days)
- **Concurrent users**: Tested up to 12 users
- **Worker processes**: 2 (configurable)
- **Response time**: 
  - Cached: <100ms
  - Cache miss: ~2s (OpenSearch query time)

## Color Coding Legend

| Color | Meaning | OS Builds | Regression Detection |
|-------|---------|-----------|---------------------|
| **Gray** | No coverage | 0 | ❌ Impossible |
| **Yellow** | Insufficient | 1 | ❌ Nothing to compare to |
| **Light Green** | Minimal viable | 2 | ✅ Can compare 2 releases |
| **Green** | Good | 3-4 | ✅ Multiple comparisons |
| **Dark Green** | Excellent | 5+ | ✅ Strong trend analysis |

**Goal**: Maximize green cells by testing the same system×benchmark combination across consecutive RHEL releases.

## Deployment

### Development
```bash
uvicorn server:app --reload --host 0.0.0.0 --port 8080
```

### Production
See [DEPLOYMENT.md](DEPLOYMENT.md) for complete deployment guide including:
- Systemd service setup
- Nginx/Apache reverse proxy configuration
- SSL/TLS setup
- Monitoring and logging
- Performance tuning

### Quick Production Start
```bash
# Install as systemd service
sudo cp heatseek.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable heatseek
sudo systemctl start heatseek

# Check status
sudo systemctl status heatseek
```

## Troubleshooting

### Dashboard shows "No data"
```bash
# Check OpenSearch connectivity
curl -u user:pass https://opensearch-host:443/zathras-results/_count

# Verify environment variables
cat .env

# Check server logs
tail -f logs/heatseek.log
```

### "Connection refused" errors
```bash
# Check server is running
curl http://localhost:8080/health

# Verify port
sudo lsof -i :8080

# Check firewall
sudo firewall-cmd --list-all
```

### Stale data showing
```bash
# Force cache refresh
curl -X POST http://localhost:8080/api/refresh

# Or click "Refresh Data" button in UI
```

## Development

### Project Structure
```
heatseek/
├── server.py              # FastAPI backend (~300 lines)
├── frontend/
│   └── index.html         # Single-page app (~400 lines)
├── requirements.txt       # Python dependencies
├── .env                   # Configuration (not in git)
├── heatseek.service      # Systemd service file
├── DEPLOYMENT.md         # Deployment guide
└── README_V2.md          # This file
```

### Adding New Endpoints

Edit `server.py`:

```python
@app.get("/api/your-endpoint")
async def your_endpoint():
    """Your endpoint description"""
    matrix, summary = get_cached_data(get_cache_key())
    # Your logic here
    return {"result": "data"}
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

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/
```

## Migration from v1.0

v1.0 used static HTML generation. v2.0 is a live API-backed dashboard.

**To migrate**:
1. Keep v1.0's `visualize_test_coverage.py` for backward compatibility
2. Deploy v2.0 alongside at new URL (e.g., `/coverage/live`)
3. Monitor usage for 2 weeks
4. Deprecate v1.0 once users migrate

**Data compatibility**: Both versions read from the same OpenSearch index - no data migration needed.

## API Documentation

FastAPI provides automatic interactive documentation:
- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

## Security Notes

⚠️ **Never commit `.env` file to git!** It contains credentials.

The dashboard:
- ✅ Uses read-only OpenSearch credentials
- ✅ No user authentication (relies on VPN/network security)
- ✅ No sensitive data storage (stateless)
- ⚠️ Contains test metadata - keep behind company firewall

## Performance Benchmarks

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

## Support

For questions or issues:
1. Check [DEPLOYMENT.md](DEPLOYMENT.md)
2. Review API docs: http://localhost:8080/docs
3. Check server logs: `sudo journalctl -u heatseek -f`
4. Contact the Performance QA team

## License

Internal Red Hat tool. Not for external distribution.

---

**Version**: 2.0.0  
**Last Updated**: 2026-06-03  
**Maintained by**: Performance QA Team
