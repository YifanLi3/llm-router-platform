# Phase 3

**Starting in this phase, development formally moves into integrating “observable backend APIs + frontend dashboard pages.”**

- First, complete the backend APIs required by the dashboard.
- Then connect the Streamlit pages to these real APIs.

---

## 1. Phase Goals

After completing Phase 3, the expected outcome is:

- Build the page UI with Streamlit.
- After repeatedly calling `POST /route` at `http://localhost:8080/docs`:
  - Metrics from `GET /quality/dashboard` change (request count, success rate, etc.).
  - The same changes are visible after refreshing Streamlit's Overview / Models / Performance pages.
- When the backend is unavailable, Streamlit must clearly indicate that “data is unavailable/backend is unreachable”; it must not continue displaying random values as though everything is normal.

---

## 2. Core Content

### A. Backend API Layer
The backend APIs added or completed in Phase 3 are:

- `GET /status`
  - Returns a system-status snapshot.
  - Used by the frontend to display service runtime status, router_mode, and quality/adapters/optimization information.
- `GET /analytics`
  - Returns dashboard overview data.
  - Provides aggregated data for the Overview / Models / Users / Costs pages.
- `GET /quality/dashboard`
  - Returns quality-monitoring data.
  - Provides success rate, error rate, P95, hotspots, SLOs, and more for the Performance / Alerts pages.
- `POST /feedback`
  - Submits user feedback.
  - Serves as an entry point for the subsequent quality feedback loop.

Notes:
- `/health` and `/route` are not newly created in Phase 3, but they remain in use.
- The backend focus of Phase 3 is “providing real data for the dashboard.”

### B. Frontend Page Layer
- `Overview`
- `Models`
- `Performance`

- `Users`
- `Costs`
- `Alerts`
- Logs`

---

## 3. Page-to-Backend API Mapping

### `Overview`
Page purpose:
- Displays a system overview.
- Displays core metrics including total request volume, average latency, success rate, cost, and cache hit rate.

Required backend APIs:
- `GET /analytics`
- `GET /health`

Implementation requirements:
- The 5 metric cards at the top must display real values.
- After refreshing the page, the metrics must change as `/route` is called.

### `Models`
Page purpose:
- Displays each model's request volume, success rate, latency, cost, and efficiency.

Required backend APIs:
- `GET /analytics`

Implementation requirements:
- Display at least one set of real, model-aggregated data in a table.

### `Performance`
Page purpose:
- Displays performance metrics such as request volume, response time, P95, and error rate.

Required backend APIs:
- `GET /quality/dashboard`
- `GET /analytics`

Implementation requirements:
- Display real avg / p95 / error_rate values.

### `Users`
Page purpose:
- Displays request distribution and usage across user tiers.

Required backend APIs:
- `GET /analytics`

Implementation requirements:
- Display the request percentage or request count for free / premium / enterprise users.

### `Costs`
Page purpose:
- Displays cost distribution and primary cost sources.

Required backend APIs:
- `GET /analytics`

Implementation requirements:
- Display total cost and cost distribution by model.

### `Alerts`
Page purpose:
- Displays system alerts, hotspot models, and SLO status.

Required backend APIs:
- `GET /quality/dashboard`
- `GET /health`

Implementation requirements:
- Display hotspot models, SLO compliance status, or error-rate anomaly notifications.

### `Logs`
Page purpose:
- Displays system logs and troubleshooting information.

---

## 4. Suggested Implementation Order

### Step 1: Complete the Backend APIs
First, prepare these APIs and confirm that their response structures are stable:
- `GET /status`
- `GET /analytics`
- `GET /quality/dashboard`
- `POST /feedback`

### Step 2: Build the 3 Core Pages First
First complete:
- `Overview`
- `Models`
- `Performance`

Reasons:
- These 3 pages best demonstrate “real-data integration.”
- Once they are complete, Phase 3 already has a minimum deliverable.

### Step 3: Complete the Business Analysis Pages
Then complete:
- `Users`
- `Costs`
- `Alerts`

### Step 4: Build the Logs Page Last
Finally, complete:
- `Logs`
- Feedback form
- Real sidebar status
- Actual trend lines
