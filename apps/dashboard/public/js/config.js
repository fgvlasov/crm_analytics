/** Override if dashboard is not served from localhost:3000 with API on :8000 */
window.LEADINTEL_API_BASE =
  window.LEADINTEL_API_BASE ||
  (location.port === "3000" ? "http://localhost:8000" : location.origin);
