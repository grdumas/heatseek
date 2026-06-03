# Testing Guide for Live Refresh Feature

This guide walks through testing the live data refresh functionality added to HeatSeek.

## Prerequisites

Before testing, ensure you have:

1. **OpenSearch cluster accessible** with valid credentials
2. **Environment configured** in `.env` file
3. **Python dependencies installed**: `pip install -r requirements.txt`

## Test Scenario 1: Basic Manual Refresh

### Setup
```bash
# Generate initial HTML visualization
python visualize_test_coverage.py

# Start the API server
python api_server.py
```

### Test Steps
1. Open `http://localhost:8000/` in your browser
2. **Verify initial page load**:
   - Page loads quickly without delay
   - Refresh button visible in top-right corner
   - Timestamp shows current date/time
   - Auto-refresh checkbox is unchecked

3. **Click the Refresh Data button**:
   - Loading overlay appears with spinner
   - Message says "Fetching fresh data from OpenSearch..."
   - Button becomes disabled and shows loading spinner
   - After 5-10 seconds, overlay disappears
   - Charts update (may not look different if data hasn't changed)
   - Timestamp updates to new refresh time

4. **Check browser console**:
   ```
   HeatSeek initialized with live data refresh capability
   API endpoint: http://localhost:8000/api/coverage
   Data refreshed successfully
   ```

### Expected Results
- Page loads quickly with static data  
- Loading overlay appears during fetch  
- Charts update without page reload  
- Timestamp updates  
- No console errors  

---

## Test Scenario 2: Auto-Refresh

### Test Steps
1. Open `http://localhost:8000/`
2. **Enable auto-refresh**:
   - Check the "Auto-refresh (60s)" checkbox
   - Console logs: "Auto-refresh enabled (60s interval)"

3. **Wait 60 seconds**:
   - Console logs: "Auto-refreshing data..."
   - Loading overlay appears automatically
   - Charts update
   - Timestamp updates

4. **Disable auto-refresh**:
   - Uncheck the checkbox
   - Console logs: "Auto-refresh disabled"
   - Wait 60 seconds to confirm no refresh occurs

### Expected Results
- Auto-refresh triggers every 60 seconds when enabled  
- Auto-refresh stops when disabled  
- Console logs confirm start/stop  
- Refresh happens in background without user interaction  

---

## Test Scenario 3: Error Handling

### Test Steps
1. Open `http://localhost:8000/`
2. **Stop the API server** (Ctrl+C in the terminal)
3. **Click Refresh Data**:
   - Loading overlay appears
   - After timeout/failure, loading overlay disappears
   - Red error banner appears at top of page
   - Error message shows: "Failed to fetch fresh data: ..."
   - Previous data still visible

4. **Dismiss error**:
   - Click X button on error banner
   - Banner disappears

5. **Restart server and retry**:
   ```bash
   python api_server.py
   ```
   - Click refresh button again
   - Should succeed this time

### Expected Results
- Error banner appears on failure  
- Specific error message shown  
- Previous data remains visible  
- Error dismissible  
- Recovery works after fixing issue  

---

## Test Scenario 4: Filter Preservation

### Test Steps
1. Open `http://localhost:8000/`
2. **Apply filters**:
   - Select specific benchmarks from dropdown
   - Choose "x86_64" architecture filter
   - Set minimum coverage to "2+ OS builds"
   - Type "Xeon" in system search

3. **Verify filters applied**:
   - Charts update to show filtered data
   - Filter status shows: "Showing: X systems (Y hidden by filters)"

4. **Click Refresh Data**:
   - Data refreshes
   - Charts update

5. **Verify filters still applied**:
   - Same benchmarks still selected
   - Same architecture filter active
   - Same coverage threshold
   - Same search term present
   - Filter status unchanged

### Expected Results
- Filters remain active after refresh  
- Filtered view preserved  
- No need to reapply filters  

---

## Test Scenario 5: Multi-Tab Behavior

### Test Steps
1. Open `http://localhost:8000/` in two browser tabs
2. **In Tab 1**:
   - Enable auto-refresh
   - Console logs confirm auto-refresh started

3. **In Tab 2**:
   - Auto-refresh is OFF (checkbox unchecked)
   - Each tab maintains independent state

4. **Click manual refresh in Tab 2**:
   - Only Tab 2 refreshes
   - Tab 1 unaffected

5. **Close Tab 1**:
   - Auto-refresh interval should clean up
   - No memory leaks

### Expected Results
- Each tab maintains independent auto-refresh state  
- Manual refresh only affects current tab  
- No cross-tab interference  
- Cleanup happens on tab close  

---

## Test Scenario 6: Network Throttling

This tests the UX with slow network conditions.

### Test Steps
1. **Open Chrome DevTools** (F12)
2. **Go to Network tab**
3. **Enable throttling**: Select "Slow 3G" from dropdown
4. **Click Refresh Data**:
   - Loading overlay appears
   - "This may take 5-10 seconds" message shown
   - Progress visible through overlay
   - Charts update when complete

### Expected Results
- Loading state clearly visible during slow fetch  
- User understands something is happening  
- No timeout errors (request completes)  
- Graceful handling of slow networks  

---

## Test Scenario 7: Data Changes

This verifies that new data actually appears in the charts.

### Test Steps

**Option A: Simulated Changes**
1. Make note of current executive summary score (e.g., "45.2%")
2. Click refresh
3. If OpenSearch data changed, score updates
4. Verify timestamp updated even if score unchanged

**Option B: Forced Changes** (requires database access)
1. Add new test results to OpenSearch
2. Click refresh
3. Verify new data appears in charts
4. Check executive summary recalculates

### Expected Results
- New data appears after refresh  
- Executive summary recalculates  
- Charts update with new values  
- Timestamp always updates  

---

## Automated Checks

You can also verify the implementation with these quick checks:

### Check 1: API Response Format
```bash
curl http://localhost:8000/api/coverage | jq '.matrix | keys'
# Should return array of platform names
```

### Check 2: HTML Contains Refresh Controls
```bash
grep -q "refresh-btn" heatseek.html && echo "PASS: Refresh button present" || echo "FAIL: Missing"
grep -q "auto-refresh-checkbox" heatseek.html && echo "PASS: Auto-refresh checkbox present" || echo "FAIL: Missing"
grep -q "loading-overlay" heatseek.html && echo "PASS: Loading overlay present" || echo "FAIL: Missing"
```

### Check 3: JavaScript Functions Exist
```bash
grep -q "function refreshData()" heatseek.html && echo "PASS: refreshData() defined" || echo "FAIL: Missing"
grep -q "function updateVisualization()" heatseek.html && echo "PASS: updateVisualization() defined" || echo "FAIL: Missing"
grep -q "function toggleAutoRefresh()" heatseek.html && echo "PASS: toggleAutoRefresh() defined" || echo "FAIL: Missing"
```

---

## Troubleshooting

### Issue: "Failed to fetch data"
**Solutions**:
- Verify API server is running: `curl http://localhost:8000/api/health`
- Check browser console for CORS errors
- Verify .env file has correct OpenSearch credentials
- Check OpenSearch is accessible: `curl -u user:pass https://opensearch-host:9200`

### Issue: Loading overlay never disappears
**Solutions**:
- Check browser console for JavaScript errors
- Verify API endpoint returns valid JSON
- Test API directly: `curl http://localhost:8000/api/coverage`
- Check network tab in DevTools for failed requests

### Issue: Auto-refresh not triggering
**Solutions**:
- Verify checkbox is checked
- Check console logs for "Auto-refresh enabled"
- Make sure browser tab is not throttled (Chrome throttles background tabs)
- Try in a different browser

### Issue: Charts don't update after refresh
**Solutions**:
- Check console for errors in `updateVisualization()`
- Verify API response contains all required fields
- Check Plotly is loaded: `typeof Plotly` should return "object"
- Clear browser cache and reload

---

## Browser Compatibility Testing

Test in multiple browsers to ensure cross-compatibility:

| Browser | Version | Status |
|---------|---------|--------|
| Chrome | 80+ | Primary target |
| Firefox | 75+ | Should work |
| Safari | 13+ | Should work |
| Edge | 80+ | Should work |
| Mobile Safari | iOS 13+ | Test touch interactions |
| Mobile Chrome | Android 9+ | Test on smaller screens |

---

## Performance Testing

Monitor performance during refresh:

1. **Open DevTools Performance tab**
2. **Start recording**
3. **Click refresh**
4. **Stop recording when complete**
5. **Analyze**:
   - Network request time (should be less than 15s)
   - JavaScript execution time (should be less than 1s)
   - Render time (should be less than 500ms)
   - Total time (should be less than 20s)

---

## Acceptance Criteria

The implementation is successful if:

- Manual refresh fetches fresh data from API
- Auto-refresh works when enabled
- Loading states provide clear feedback
- Errors are handled gracefully
- Filters persist across refreshes
- Charts update without page reload
- Timestamps update correctly
- No console errors in normal operation
- Works in Chrome, Firefox, Safari, Edge
- Response time acceptable for 5-10 second queries
