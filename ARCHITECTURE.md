# HeatSeek Architecture

## System Components

```
┌─────────────────────────────────────────────────────────────┐
│                         Browser                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              heatseek.html (Static + Dynamic)          │ │
│  │                                                         │ │
│  │  ┌──────────────┐  ┌────────────────────────────────┐ │ │
│  │  │ Static Data  │  │   Live Refresh Components      │ │ │
│  │  │ (Initial)    │  │                                 │ │ │
│  │  │              │  │  - Refresh Button               │ │ │
│  │  │ - Charts     │  │  - Auto-refresh Toggle          │ │ │
│  │  │ - Summary    │  │  - Loading Overlay              │ │ │
│  │  │ - Filters    │  │  - Error Banner                 │ │ │
│  │  │              │  │  - Timestamp Display            │ │ │
│  │  └──────────────┘  │                                 │ │ │
│  │                     │  JavaScript Functions:          │ │ │
│  │                     │  - refreshData()                │ │ │
│  │                     │  - updateVisualization()        │ │ │
│  │                     │  - toggleAutoRefresh()          │ │ │
│  │                     └────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP GET / (initial load)
                              │ HTTP GET /api/coverage (refresh)
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Server (api_server.py)            │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                      Endpoints                          │ │
│  │                                                         │ │
│  │  GET /              → Serve heatseek.html              │ │
│  │  GET /api/health    → Health check                     │ │
│  │  GET /api/coverage  → Fetch fresh coverage data        │ │
│  │  POST /api/regenerate → Rebuild static HTML            │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Query data
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      OpenSearch Cluster                      │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                  zathras-results index                  │ │
│  │                                                         │ │
│  │  - Test results (10,000s of documents)                 │ │
│  │  - System metadata (CPU, OS, platform)                 │ │
│  │  - Benchmark names and results                         │ │
│  │  - Timestamps and versions                             │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

### Initial Page Load (Fast)

```
User → Browser
       ↓
       GET / → FastAPI Server
               ↓
               Read heatseek.html (static file)
               ↓
       ← HTML with embedded data
       ↓
Browser renders page (instant)
```

### Manual Refresh (5-10 seconds)

```
User clicks "Refresh Data"
       ↓
Browser JavaScript: refreshData()
       ↓
       GET /api/coverage → FastAPI Server
                           ↓
                           connect_to_opensearch()
                           ↓
                           fetch_coverage_data() → OpenSearch
                                                   ↓
                                                   Query index
                                                   ↓
                           ← 10,000 documents
                           ↓
                           build_coverage_matrix()
                           ↓
                           calculate_executive_summary()
                           ↓
       ← JSON response
       ↓
updateVisualization(data)
       ↓
Plotly.react() updates charts
       ↓
User sees fresh data
```

### Auto-Refresh (Every 60s)

```
User enables auto-refresh checkbox
       ↓
toggleAutoRefresh()
       ↓
setInterval(refreshData, 60000)
       ↓
       Every 60 seconds:
       ↓
       Same flow as Manual Refresh
       ↓
       (Runs in background)
```

## Component Interactions

### Frontend (HTML/JavaScript)

**Responsibilities**:
- Display visualizations
- Handle user interactions
- Fetch data from API
- Update charts dynamically
- Manage loading/error states
- Preserve filter selections

**Technologies**:
- Plotly.js - Interactive charts
- Bootstrap 5 - UI framework
- Vanilla JavaScript - Data fetching and DOM manipulation
- CSS3 - Styling and animations

### Backend (FastAPI)

**Responsibilities**:
- Serve static HTML file
- Provide REST API for coverage data
- Connect to OpenSearch
- Transform data for frontend
- Handle errors and timeouts

**Technologies**:
- FastAPI - Web framework
- OpenSearch-py - Database client
- Python 3.8+ - Runtime

### Data Store (OpenSearch)

**Responsibilities**:
- Store test results
- Index for fast queries
- Provide search capabilities

**Schema**:
```json
{
  "metadata": {
    "cloud_provider": "aws",
    "instance_type": "m5.24xlarge"
  },
  "system_under_test": {
    "hardware": {
      "cpu": {
        "model": "Intel Xeon Platinum 8259CL",
        "cores": 96,
        "architecture": "x86_64"
      }
    },
    "operating_system": {
      "version": "9.4",
      "kernel_version": "5.14.0-427"
    }
  },
  "test": {
    "name": "specjbb2015"
  }
}
```

## Deployment Architecture

### Development Mode

```
Developer Workstation
  ├── visualize_test_coverage.py (generate HTML once)
  ├── api_server.py (run locally)
  └── .env (OpenSearch credentials)

Browser → http://localhost:8000/
```

### Production Mode

```
Server (Linux VM/Container)
  ├── api_server.py (running via systemd/docker)
  ├── heatseek.html (generated periodically)
  └── .env (production credentials)

Users → http://heatseek.example.com/
```

## Scaling Considerations

### Current Design
- Single FastAPI server
- Synchronous OpenSearch queries
- Full data fetch each time
- No caching

### For Production Scale

**Add Caching**:
```
Browser → FastAPI → Redis Cache → OpenSearch
                         ↓
                    Cache for 60s
```

**Add Load Balancing**:
```
Users → Nginx → FastAPI Server 1
             → FastAPI Server 2
             → FastAPI Server 3
```

**Add Background Processing**:
```
FastAPI → Message Queue → Worker Pool → OpenSearch
                              ↓
                         Pre-compute summaries
```

## Security Considerations

### Current Implementation
- OpenSearch credentials in .env (server-side only)
- CORS enabled for all origins (development mode)
- No authentication on API endpoints
- No rate limiting

### For Production

**Should Add**:
1. API authentication (OAuth2/API keys)
2. CORS restricted to specific domains
3. Rate limiting on /api/coverage endpoint
4. HTTPS/TLS for all connections
5. OpenSearch connection over SSL
6. Input validation and sanitization
7. Security headers (CSP, HSTS, etc.)

## State Management

### Browser State

**Persistent** (survives refresh):
- None (stateless)

**Session** (current page load):
- Filter selections
- Auto-refresh enabled/disabled
- Active platform tab
- Scroll position
- Current data snapshot

**Transient** (during operation):
- Loading state
- Error messages
- Auto-refresh interval handle

### Server State

**Persistent**:
- heatseek.html file (until regenerated)

**Per-Request**:
- OpenSearch connection
- Query results
- Calculated metrics

## Error Handling Flow

```
refreshData()
    ↓
    try {
        fetch('/api/coverage')
            ↓
            [Network OK?] → Yes → [Status 200?] → Yes → updateVisualization()
                ↓                       ↓
                No                      No
                ↓                       ↓
            Network Error          HTTP Error
                ↓                       ↓
                showError("Failed to fetch...")
                ↓
            Previous data remains visible
                ↓
            User can dismiss or retry
    }
```

## Performance Optimization

### Current Optimizations
- Static HTML loads instantly (no API call)
- Plotly.react() for efficient chart updates
- Filter state preserved (no recalculation)
- CSS animations via GPU (transform)

### Bottlenecks
1. OpenSearch query time (5-10s)
2. Network latency (depends on deployment)
3. JSON parsing for large datasets
4. Chart re-rendering

### Future Optimizations
- Server-side caching (Redis)
- Data pagination/chunking
- WebSocket for real-time updates
- Service Worker for offline capability
- Incremental data loading
- Virtual scrolling for large lists

## Testing Strategy

### Unit Tests (Future)
- JavaScript function tests (Jest)
- Python backend tests (pytest)
- Data transformation tests

### Integration Tests (Future)
- API endpoint tests
- End-to-end browser tests (Playwright)
- OpenSearch mock tests

### Manual Tests (Current)
- Functional testing (see TESTING_GUIDE.md)
- Browser compatibility
- Performance benchmarks
- Error scenarios

## Monitoring Points

For production deployment, monitor:

**Frontend**:
- Page load time
- Refresh request frequency
- Error rate
- Browser console errors

**Backend**:
- API response time
- OpenSearch query duration
- Error rate (4xx/5xx)
- Request volume

**Infrastructure**:
- Server CPU/memory
- Network bandwidth
- OpenSearch cluster health
- SSL certificate expiry
