const LeadIntelApi = (() => {
  const storageKey = "leadintel.auth";

  function getAuth() {
    try {
      return JSON.parse(localStorage.getItem(storageKey) || "null");
    } catch {
      return null;
    }
  }

  function setAuth(data) {
    if (!data) localStorage.removeItem(storageKey);
    else localStorage.setItem(storageKey, JSON.stringify(data));
  }

  async function request(path, { method = "GET", body, auth = true } = {}) {
    const headers = { Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const session = getAuth();
    if (auth && session?.access_token) {
      headers.Authorization = `Bearer ${session.access_token}`;
    }
    const res = await fetch(`${window.LEADINTEL_API_BASE}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { raw: text };
    }
    if (!res.ok) {
      const msg =
        data?.error?.message || data?.detail?.message || data?.detail || res.statusText;
      const err = new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
      err.status = res.status;
      err.payload = data;
      throw err;
    }
    return data;
  }

  return {
    getAuth,
    setAuth,
    health: () => request("/healthz", { auth: false }),
    features: () => request("/api/v1/features", { auth: false }),
    login: (payload) => request("/api/v1/auth/login", { method: "POST", body: payload, auth: false }),
    me: () => request("/api/v1/auth/me"),
    summary: () => request("/api/v1/dashboard/summary"),
    leads: (search = "") =>
      request(`/api/v1/leads?limit=100${search ? `&search=${encodeURIComponent(search)}` : ""}`),
    lead: (id) => request(`/api/v1/leads/${id}`),
    odooInstances: () => request("/api/v1/odoo/instances"),
    createOdoo: (payload) =>
      request("/api/v1/odoo/instances", { method: "POST", body: payload }),
  };
})();
