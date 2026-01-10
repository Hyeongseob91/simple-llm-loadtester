# Phase 3 Testing Guide

## Quick Start

```bash
cd /mnt/data1/work/wigtn/projects/llm-loadtest/web
npm install
npm run dev
```

Open browser: http://localhost:5050

## Testing Checklist

### ✅ 1. Dark Mode Toggle

#### Test Steps:
1. Navigate to any page
2. Look at the sidebar footer
3. Click the "Dark Mode" button (moon icon)
4. Verify the page switches to dark theme
5. Click "Light Mode" button (sun icon)
6. Verify the page switches back to light theme

#### Expected Results:
- [ ] Button icon changes: Moon → Sun
- [ ] Background changes: Light gray → Dark gray
- [ ] All text remains readable
- [ ] Charts update with dark-compatible colors
- [ ] No flash/flicker during transition
- [ ] Theme persists on page reload
- [ ] System preference is respected on first visit

#### Edge Cases:
- [ ] Works with browser back/forward
- [ ] Works across different pages
- [ ] No hydration errors in console

---

### ✅ 2. Chart Improvements (Benchmark Detail Page)

#### Test Steps:
1. Run a benchmark or open existing result
2. Navigate to `/benchmark/[id]`
3. Scroll to "Throughput & Latency by Concurrency" chart
4. Look for the brush component at bottom
5. Drag the brush handles to zoom
6. Verify multi-axis labels (left and right)

#### Expected Results:

**Multi Y-Axis:**
- [ ] Left Y-axis shows "Throughput (tok/s)"
- [ ] Right Y-axis shows "Latency (ms)"
- [ ] Blue line (throughput) scales with left axis
- [ ] Green/Orange lines (TTFT) scale with right axis
- [ ] Both axes have appropriate ranges

**Zoom/Pan:**
- [ ] Brush component visible at chart bottom
- [ ] Can drag brush handles to select range
- [ ] Chart zooms to selected concurrency range
- [ ] Can drag entire brush to pan
- [ ] Can reset by expanding brush to full width

**Visual Quality:**
- [ ] Dots are visible on lines (r: 4)
- [ ] Dots grow on hover (r: 6)
- [ ] Axis labels are readable
- [ ] Grid lines are subtle
- [ ] Dark mode: gray grid, white text
- [ ] Light mode: light grid, dark text

**Error Rate & Goodput Chart:**
- [ ] Only appears if goodput data exists
- [ ] Shows error rate in red
- [ ] Shows goodput in green
- [ ] Has brush for zooming
- [ ] Percentages displayed correctly

#### Edge Cases:
- [ ] Works with single concurrency level
- [ ] Handles missing data points
- [ ] Tooltips show correct values
- [ ] No console errors

---

### ✅ 3. Test Presets (New Benchmark Page)

#### Test Steps:
1. Navigate to `/benchmark/new`
2. Scroll to "Quick Presets" section
3. Click "Quick" preset
4. Verify form fields auto-fill
5. Click "Standard" preset
6. Verify form fields update
7. Click "Stress" preset
8. Verify form fields update

#### Expected Results:

**Quick Preset:**
- [ ] Concurrency: 1,5,10
- [ ] Prompts: 50
- [ ] Input Length: 128
- [ ] Output Length: 64
- [ ] Preset button highlighted with blue border
- [ ] Preset button has blue background

**Standard Preset:**
- [ ] Concurrency: 1,10,50,100
- [ ] Prompts: 200
- [ ] Input Length: 256
- [ ] Output Length: 128
- [ ] Previous preset unhighlighted
- [ ] Standard preset highlighted

**Stress Preset:**
- [ ] Concurrency: 10,50,100,200,500
- [ ] Prompts: 500
- [ ] Input Length: 512
- [ ] Output Length: 256
- [ ] Stress preset highlighted

**UI Behavior:**
- [ ] Only one preset selected at a time
- [ ] Hover effect on unselected presets
- [ ] Preset descriptions visible
- [ ] Preset details (concurrency, prompts, tokens) shown
- [ ] Can manually edit after applying preset
- [ ] Manual edits don't break preset selection

#### Edge Cases:
- [ ] Can still submit with custom values
- [ ] Server settings not affected by presets
- [ ] Goodput settings independent of presets
- [ ] Form validation still works

---

### ✅ 4. Comparison Enhancements

#### Test Steps:
1. Run at least 2 benchmarks with different models
2. Navigate to `/compare`
3. Select 2 runs from the list
4. Wait for comparison to load
5. Check all comparison sections

#### Expected Results:

**Run Selection:**
- [ ] List shows all completed runs
- [ ] Checkboxes work correctly
- [ ] Can select 2-5 runs
- [ ] Cannot select more than 5
- [ ] Selected runs highlighted in blue
- [ ] Counter shows "X/5"

**Best Results Cards:**
- [ ] Shows best throughput value
- [ ] Shows which run achieved it
- [ ] Shows best TTFT value
- [ ] Shows which run achieved it
- [ ] Cards have green/blue backgrounds
- [ ] Values formatted correctly (1 decimal)

**Model Comparison Table:**
- [ ] Table appears when 2+ runs selected
- [ ] All columns visible:
  - Run ID (8 chars)
  - Model name
  - Best throughput
  - Best TTFT
  - Best concurrency
  - Error rate
  - Goodput (if available)
- [ ] Values formatted correctly
- [ ] Rows align properly
- [ ] Table scrolls horizontally on small screens
- [ ] Dark mode: proper text colors

**Concurrency Comparison Chart:**
- [ ] Chart appears when 2+ runs selected
- [ ] Multiple lines shown (one per model)
- [ ] Each line has different color
- [ ] Legend shows model names + run IDs
- [ ] X-axis: Concurrency levels
- [ ] Y-axis: Throughput (tok/s)
- [ ] Tooltip shows values on hover
- [ ] Lines connect properly
- [ ] Handles different concurrency ranges

**Data Accuracy:**
- [ ] Table values match individual results
- [ ] Chart values match table
- [ ] Best values correctly identified
- [ ] No data inconsistencies

#### Edge Cases:
- [ ] Works with 2 runs (minimum)
- [ ] Works with 5 runs (maximum)
- [ ] Handles runs with different concurrency levels
- [ ] Handles missing goodput data
- [ ] Shows loading state while fetching
- [ ] Handles API errors gracefully

---

### ✅ 5. Cross-Feature Integration

#### Test Scenarios:

**Dark Mode + Charts:**
- [ ] Chart tooltips use dark theme
- [ ] Grid lines visible but subtle
- [ ] Line colors maintain contrast
- [ ] Axis labels readable
- [ ] Brush component styled correctly

**Dark Mode + Comparison:**
- [ ] Table headers readable
- [ ] Table rows have subtle borders
- [ ] Cards have proper backgrounds
- [ ] Chart integrates with dark theme

**Dark Mode + Presets:**
- [ ] Preset buttons have proper contrast
- [ ] Selected preset clearly visible
- [ ] Hover states work correctly
- [ ] Form inputs readable

**Presets + Benchmark Workflow:**
1. [ ] Select preset
2. [ ] Fill server details
3. [ ] Start benchmark
4. [ ] Result page shows correct config
5. [ ] Can compare preset-based runs

---

### ✅ 6. Performance Testing

#### Metrics to Check:

**Page Load:**
- [ ] Initial load < 2s
- [ ] No layout shift (CLS < 0.1)
- [ ] Charts render smoothly
- [ ] No console errors

**Interactions:**
- [ ] Dark mode toggle instant (<100ms)
- [ ] Preset selection instant
- [ ] Chart zoom/pan smooth (60fps)
- [ ] Comparison loads in <1s for 5 runs

**Memory:**
- [ ] No memory leaks on theme toggle
- [ ] No memory leaks on chart interactions
- [ ] useMemo prevents unnecessary re-renders

#### Testing Tools:
```bash
# Check bundle size
npm run build

# Check lighthouse score
# Use Chrome DevTools > Lighthouse
# Target: Performance > 90, Accessibility > 95
```

---

### ✅ 7. Accessibility Testing

#### Keyboard Navigation:
- [ ] Can tab through preset buttons
- [ ] Can tab through comparison checkboxes
- [ ] Can activate dark mode with Enter/Space
- [ ] Focus indicators visible
- [ ] No keyboard traps

#### Screen Reader:
- [ ] Preset buttons have descriptive labels
- [ ] Chart axes have labels
- [ ] Table headers properly marked
- [ ] Button states announced
- [ ] Theme change announced

#### Color Contrast:
- [ ] Text readable in light mode (WCAG AA)
- [ ] Text readable in dark mode (WCAG AA)
- [ ] Interactive elements have sufficient contrast
- [ ] Chart lines distinguishable

---

### ✅ 8. Browser Compatibility

Test in these browsers:

**Desktop:**
- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Edge (latest)

**Mobile:**
- [ ] Chrome Mobile
- [ ] Safari iOS
- [ ] Samsung Internet

**Features to verify:**
- [ ] Charts render correctly
- [ ] Dark mode works
- [ ] Responsive layout
- [ ] Touch interactions work

---

### ✅ 9. Error Handling

#### Test Error Cases:

**API Errors:**
1. Stop backend server
2. Try to load comparison
   - [ ] Shows error message
   - [ ] No console errors
   - [ ] Can retry

**Missing Data:**
1. Load result without goodput
   - [ ] Goodput chart hidden
   - [ ] Table shows "N/A" for goodput
   - [ ] No breaking errors

**Invalid Input:**
1. Manually edit preset values to invalid
   - [ ] Form validation triggers
   - [ ] Cannot submit invalid data
   - [ ] Error messages clear

---

### ✅ 10. Regression Testing

Verify existing features still work:

**Dashboard:**
- [ ] Recent runs list displays
- [ ] Status badges correct
- [ ] Navigation works

**History:**
- [ ] All runs listed
- [ ] Pagination works
- [ ] Delete functionality works

**Benchmark Creation:**
- [ ] Can create without presets
- [ ] All settings work
- [ ] Goodput thresholds work
- [ ] API key field works

**Benchmark Results:**
- [ ] Summary cards display
- [ ] Detailed table shows
- [ ] All metrics correct
- [ ] Status updates work

---

## Automated Testing

### Run TypeScript Check:
```bash
npx tsc --noEmit
```
Expected: No errors

### Run Linter:
```bash
npm run lint
```
Expected: No errors or warnings

### Build Test:
```bash
npm run build
```
Expected: Successful build, no errors

---

## Visual Regression Testing

### Screenshot Locations:
1. Dashboard (light/dark)
2. New Benchmark with presets (light/dark)
3. Benchmark result with charts (light/dark)
4. Compare page with 2 models (light/dark)

### Manual Review:
- [ ] Spacing consistent
- [ ] Alignment correct
- [ ] Colors match design
- [ ] Typography hierarchy clear
- [ ] No visual glitches

---

## Production Readiness Checklist

### Code Quality:
- [x] TypeScript strict mode
- [x] No console.logs
- [x] No TODO comments
- [x] No unused imports
- [x] Proper error handling

### Documentation:
- [x] Implementation guide created
- [x] Visual guide created
- [x] Testing guide created
- [x] Code comments where needed

### Performance:
- [x] useMemo for expensive ops
- [x] Proper React Query usage
- [x] No unnecessary re-renders
- [x] Optimized bundle size

### Accessibility:
- [x] Semantic HTML
- [x] ARIA labels where needed
- [x] Keyboard navigation
- [x] Color contrast

### Browser Support:
- [x] Modern browsers supported
- [x] Graceful degradation
- [x] No breaking errors

---

## Known Limitations

1. **Chart Zoom**: Works best with 3+ data points
2. **Comparison**: Maximum 5 runs at once
3. **Presets**: Fixed values (not customizable via UI)
4. **Dark Mode**: Requires JavaScript enabled

---

## Bug Report Template

If you find issues, please report with:

```markdown
**Feature**: [e.g., Dark Mode Toggle]
**Browser**: [e.g., Chrome 120]
**OS**: [e.g., Ubuntu 22.04]

**Steps to Reproduce**:
1. ...
2. ...
3. ...

**Expected**: ...
**Actual**: ...

**Screenshots**: [if applicable]
**Console Errors**: [if any]
```

---

## Success Criteria

All tests passing means Phase 3 is ready for production:

- ✅ All functionality tests passed
- ✅ No TypeScript errors
- ✅ No console errors
- ✅ Performance metrics met
- ✅ Accessibility standards met
- ✅ Works across browsers
- ✅ No regressions in existing features

---

## Next Steps After Testing

1. **Approval**: Get stakeholder review
2. **Deployment**: Deploy to staging
3. **User Testing**: Get real user feedback
4. **Monitoring**: Set up error tracking
5. **Iteration**: Address feedback in Phase 4
