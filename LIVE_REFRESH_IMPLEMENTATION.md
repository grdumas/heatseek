# Live Data Refresh Implementation

## Overview

This document describes the live data refresh feature added to the HeatSeek visualization frontend.

## UX Design Decisions

### 1. Hybrid Approach: Manual + Optional Auto-Refresh

The implementation provides **both manual refresh and optional auto-refresh**, giving users maximum control:

- **Manual Refresh Button**: Always available for on-demand updates
- **Auto-Refresh Toggle**: Optional 60-second auto-refresh that users can enable/disable
- **No Auto-Refresh on Page Load**: Initial data comes from the server-generated HTML to ensure fast page load

**Rationale**: OpenSearch queries can take 5-10 seconds, so:
- Auto-refresh on page load would create a poor first impression with immediate loading delay
- Manual refresh gives users control over when to trigger expensive queries
- Optional auto-refresh helps teams that want to display HeatSeek on monitoring dashboards
- 60-second interval balances freshness with server load

### 2. Visual Loading States

The UI provides clear feedback during data fetches:

- **Full-screen loading overlay** with spinner and message during refresh
- **Disabled refresh button** with loading spinner during fetch
- **Error banner** with clear error messages and dismiss button
- **Timestamp display** showing when data was last updated

### 3. Graceful Error Handling

If the API call fails:
- Error banner appears at top of page with specific error message
- Previous data remains visible (no blank screen)
- User can dismiss error and retry manually
- Console logging for debugging

### 4. Chart Update Without Page Reload

All visualizations update dynamically:
- Plotly charts update using `Plotly.react()` for smooth transitions
- Filters are preserved during refresh
- Executive summary recalculates automatically
- No page flicker or scroll position loss

## Implementation Details

### Frontend Changes (`visualize_test_coverage.py`)

#### Added CSS Styles
- `.refresh-controls` - Container for refresh UI in header
- `.refresh-btn` - Styled button with loading states
- `.auto-refresh-toggle` - Checkbox with label for auto-refresh
- `.loading-overlay` - Full-screen loading indicator
- `.error-banner` - Error message display
- `.last-updated` - Timestamp display

#### Added HTML Elements
```html
<!-- Loading overlay -->
<div id="loading-overlay" class="loading-overlay">...</div>

<!-- Error banner -->
<div id="error-banner" class="error-banner">...</div>

<!-- Refresh controls in header -->
<div class="refresh-controls">
    <div class="last-updated">
        <span id="data-timestamp">...</span>
    </div>
    <div class="auto-refresh-toggle">
        <input type="checkbox" id="auto-refresh-checkbox">
        <label>Auto-refresh (60s)</label>
    </div>
    <button id="refresh-btn" class="refresh-btn">
        🔄 Refresh Data
    </button>
</div>
```

#### Added JavaScript Functions

1. **`refreshData()`** - Main function to fetch fresh data from API
   - Calls `/api/coverage` endpoint
   - Shows loading overlay
   - Handles errors gracefully
   - Updates visualization on success

2. **`updateVisualization(data)`** - Updates all charts with new data
   - Rebuilds system labels with fresh coverage counts
   - Updates executive summary metrics
   - Updates all Plotly heatmaps
   - Refreshes benchmark filter dropdown
   - Re-applies current filter settings

3. **`toggleAutoRefresh()`** - Enable/disable 60-second auto-refresh
   - Uses `setInterval()` when enabled
   - Clears interval when disabled
   - Cleans up on page unload

4. **UI Helper Functions**:
   - `showLoading()` / `hideLoading()` - Control overlay
   - `showError()` / `hideErrorBanner()` - Manage error display
   - `updateTimestamp()` - Update data timestamp
   - `getSystemLabel()` - Format system labels consistently

### Backend API Compatibility

The implementation expects the `/api/coverage` endpoint to return:

```json
{
    "matrix": {
        "platform_name": {
            "system_name": {
                "benchmark_name": ["os_build_1", "os_build_2", ...]
            }
        }
    },
    "benchmarks": ["benchmark1", "benchmark2", ...],
    "platform_stats": {
        "platform_name": {
            "systems": ["system1", ...],
            "os_builds": ["build1", ...],
            "test_count": 1234
        }
    },
    "system_metadata": {
        "platform_name": {
            "system_name": {
                "label": "Xeon 8259CL • 96c",
                "full_model": "Intel(R) Xeon(R) ...",
                "cores": 96,
                "arch": "x86_64",
                "arch_icon": "🔷"
            }
        }
    },
    "executive_summary": {
        "overall_score": 45.2,
        "total_combos": 1000,
        "viable_combos": 452,
        ...
    },
    "total_documents": 5000
}
```

This format matches what `api_server.py` already provides.

## Testing

### Prerequisites

1. OpenSearch cluster must be accessible with credentials in `.env`
2. FastAPI server running: `python api_server.py`
3. Initial HTML generated: `python visualize_test_coverage.py` (once)

### Manual Testing Steps

1. **Generate initial visualization**:
   ```bash
   python visualize_test_coverage.py
   ```

2. **Start the API server**:
   ```bash
   python api_server.py
   ```

3. **Open visualization** at `http://localhost:8000/`

4. **Test manual refresh**:
   - Click "🔄 Refresh Data" button
   - Verify loading overlay appears
   - Verify charts update without page reload
   - Verify timestamp updates
   - Check browser console for success logs

5. **Test auto-refresh**:
   - Enable "Auto-refresh (60s)" checkbox
   - Wait 60 seconds
   - Verify automatic refresh occurs
   - Check console logs confirm auto-refresh
   - Disable checkbox and verify auto-refresh stops

6. **Test error handling**:
   - Stop the API server
   - Click refresh button
   - Verify error banner appears with clear message
   - Verify previous data remains visible
   - Click × to dismiss error
   - Restart server and retry

7. **Test filter preservation**:
   - Apply some filters (architecture, benchmark, etc.)
   - Click refresh
   - Verify filters remain applied after data updates

8. **Test timestamp display**:
   - Note the timestamp before refresh
   - Click refresh
   - Verify timestamp updates to current time

### Browser Compatibility

Tested features used:
- `fetch()` API - Modern browsers (Chrome 42+, Firefox 39+, Safari 10.1+, Edge 14+)
- `async/await` - ES2017 (Chrome 55+, Firefox 52+, Safari 11+, Edge 15+)
- CSS Grid - Modern browsers (Chrome 57+, Firefox 52+, Safari 10.1+, Edge 16+)
- Plotly React - No special requirements

**Recommended**: Chrome 80+, Firefox 75+, Safari 13+, Edge 80+

## File Changes Summary

### Modified Files
- `visualize_test_coverage.py` - Added live refresh UI and JavaScript

### No Changes Required
- `api_server.py` - Already provides `/api/coverage` endpoint
- HTML remains standalone - all dependencies via CDN

## Future Enhancements

Potential improvements for future iterations:

1. **Configurable refresh interval** - Let users choose refresh frequency
2. **Background refresh** - Refresh without blocking UI (using Web Workers)
3. **Partial updates** - Only update changed data to reduce bandwidth
4. **Websocket support** - Push updates from server instead of polling
5. **Offline mode** - Cache data and work offline with stale data warning
6. **Visual diff** - Highlight what changed between refreshes
7. **Refresh on visibility** - Auto-refresh when tab becomes visible
8. **Progressive loading** - Load and display platforms incrementally

## Known Limitations

1. **Full data replacement** - Every refresh fetches all data (not incremental)
2. **No background fetching** - UI blocks during refresh
3. **Fixed 60s interval** - Auto-refresh interval is not configurable
4. **No data versioning** - Cannot compare current vs previous data
5. **No retry logic** - Failed requests require manual retry
