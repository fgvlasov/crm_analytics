(() => {
  const $ = (sel) => document.querySelector(sel);
  const titles = {
    overview: ["Overview", "Workspace health and sync status"],
    leads: ["Leads", "Scores, temperature, and Fast AI queue actions"],
    providers: ["AI Providers", "BYOK connections for Fast Assessment"],
    odoo: ["Odoo integrations", "Connect CRM instances and manage tokens"],
    features: ["Features", "Phases enabled on this SaaS deployment"],
  };

  let selectedLeadId = null;
  let lastJobId = null;

  function show(el, on) {
    el.classList.toggle("hidden", !on);
  }

  function setRoute(route) {
    document.querySelectorAll(".nav-item").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.route === route);
    });
    document.querySelectorAll(".page").forEach((page) => {
      show(page, page.id === `page-${route}`);
    });
    const [title, sub] = titles[route] || ["LeadIntel", ""];
    $("#page-title").textContent = title;
    $("#page-subtitle").textContent = sub;
    if (route === "overview") loadOverview();
    if (route === "leads") loadLeads();
    if (route === "providers") loadProviders();
    if (route === "odoo") loadOdoo();
    if (route === "features") loadFeatures();
  }

  async function enterApp() {
    show($("#view-login"), false);
    show($("#view-app"), true);
    try {
      const me = await LeadIntelApi.me();
      $("#user-chip").innerHTML = `<strong>${me.user.name}</strong><br>${me.user.email}<br>${me.tenant.name}`;
    } catch {
      LeadIntelApi.setAuth(null);
      showLogin();
      return;
    }
    try {
      await LeadIntelApi.health();
      $("#api-status").textContent = "API OK";
      $("#api-status").className = "pill ok";
    } catch {
      $("#api-status").textContent = "API down";
      $("#api-status").className = "pill bad";
    }
    setRoute("overview");
  }

  function showLogin() {
    show($("#view-app"), false);
    show($("#view-login"), true);
  }

  async function loadOverview() {
    try {
      const s = await LeadIntelApi.summary();
      $("#stat-leads").textContent = s.leads_total;
      $("#stat-odoo-leads").textContent = s.leads_from_odoo;
      $("#stat-instances").textContent = s.odoo_instances;
      $("#stat-connected").textContent = s.odoo_connected;
      const hints = $("#feature-hints");
      hints.innerHTML = "";
      Object.entries(s.features || {}).forEach(([k, v]) => {
        const li = document.createElement("li");
        li.textContent = `${k}: ${v ? "enabled" : "off"}`;
        hints.appendChild(li);
      });
    } catch (err) {
      $("#stat-leads").textContent = "—";
      if (err.status === 403) {
        $("#feature-hints").innerHTML =
          "<li>Odoo connector feature may be disabled — check FEATURE_ODOO_CONNECTOR</li>";
      }
    }
  }

  async function loadLeads(search = "") {
    const body = $("#leads-body");
    body.innerHTML = `<tr><td colspan="7" class="muted">Loading…</td></tr>`;
    try {
      const data = await LeadIntelApi.leads(search);
      if (!data.items?.length) {
        body.innerHTML = `<tr><td colspan="7" class="muted">No leads yet — sync from Odoo</td></tr>`;
        return;
      }
      body.innerHTML = "";
      data.items.forEach((lead) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${esc(lead.latest_score_total ?? "—")}</td>
          <td>${esc(lead.latest_temperature || "—")}</td>
          <td>${esc(lead.name)}</td>
          <td>${esc(lead.company_name || "—")}</td>
          <td>${esc(lead.stage_name || "—")}</td>
          <td>${esc(lead.latest_assessment_status || "—")}</td>
          <td><button type="button" class="btn" data-queue="${esc(lead.id)}">Fast AI</button></td>`;
        tr.querySelector("[data-queue]").addEventListener("click", async (ev) => {
          ev.stopPropagation();
          try {
            const job = await LeadIntelApi.queueFast(lead.id, true);
            lastJobId = job.id;
            alert(`Queued job ${job.id} (${job.status})`);
            await loadLeads(search);
          } catch (err) {
            alert(err.message);
          }
        });
        tr.addEventListener("click", () => showLeadDetail(lead));
        body.appendChild(tr);
      });
    } catch (err) {
      body.innerHTML = `<tr><td colspan="7" class="error">${esc(err.message)}</td></tr>`;
    }
  }

  async function showLeadDetail(lead) {
    selectedLeadId = lead.id;
    const box = $("#lead-detail");
    show(box, true);
    $("#lead-detail-title").textContent = lead.name;
    $("#lead-detail-body").textContent = JSON.stringify(lead, null, 2);
    const assessEl = $("#lead-assessment-body");
    try {
      const a = await LeadIntelApi.latestAssessment(lead.id);
      assessEl.textContent = JSON.stringify(a, null, 2);
    } catch {
      assessEl.textContent = "No assessment yet.";
    }
  }

  async function loadProviders() {
    const list = $("#providers-list");
    list.innerHTML = "";
    try {
      const items = await LeadIntelApi.providers();
      if (!items.length) {
        list.innerHTML = `<p class="muted">No providers yet — add a mock provider to start.</p>`;
        return;
      }
      items.forEach((p) => {
        const card = document.createElement("article");
        card.className = "feature-card" + (p.is_default ? " on" : "");
        card.innerHTML = `
          <div class="flag">${esc(p.provider_type)} · ${esc(p.status)}</div>
          <strong>${esc(p.name)}</strong>
          <div class="muted">${esc(p.default_model)}</div>
          <button type="button" class="btn" data-test="${esc(p.id)}">Test</button>`;
        card.querySelector("[data-test]").addEventListener("click", async () => {
          try {
            const res = await LeadIntelApi.testProvider(p.id);
            alert(JSON.stringify(res));
          } catch (err) {
            alert(err.message);
          }
        });
        list.appendChild(card);
      });
    } catch (err) {
      list.innerHTML = `<p class="error">${esc(err.message)}</p>`;
    }
  }

  async function loadOdoo() {
    const list = $("#odoo-list");
    const empty = $("#odoo-empty");
    list.innerHTML = "";
    try {
      const items = await LeadIntelApi.odooInstances();
      show(empty, !items.length);
      items.forEach((inst) => {
        const card = document.createElement("article");
        card.className = "feature-card" + (inst.status === "connected" ? " on" : "");
        card.innerHTML = `
          <div class="flag">${esc(inst.status)}</div>
          <strong>${esc(inst.name)}</strong>
          <div class="muted">${esc(inst.base_url)}</div>
          <div class="muted">${esc(inst.company_name || "")}</div>
          <div class="muted">Last sync: ${esc(inst.last_sync_at || "never")}</div>`;
        list.appendChild(card);
      });
    } catch (err) {
      show(empty, true);
      empty.textContent = err.message;
      empty.classList.add("error");
    }
  }

  async function loadFeatures() {
    const grid = $("#features-grid");
    grid.innerHTML = "";
    try {
      const data = await LeadIntelApi.features();
      Object.entries(data.features || {}).forEach(([key, on]) => {
        const card = document.createElement("div");
        card.className = "feature-card" + (on ? " on" : "");
        card.innerHTML = `<div class="flag">${on ? "ON" : "OFF"}</div><strong>${esc(key)}</strong>`;
        grid.appendChild(card);
      });
    } catch (err) {
      grid.textContent = err.message;
    }
  }

  function esc(s) {
    return String(s ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  $("#login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = $("#login-error");
    show(err, false);
    const fd = new FormData(e.target);
    try {
      const tokens = await LeadIntelApi.login({
        email: fd.get("email"),
        password: fd.get("password"),
        tenant_slug: fd.get("tenant_slug"),
      });
      LeadIntelApi.setAuth(tokens);
      await enterApp();
    } catch (ex) {
      err.textContent = ex.message || "Login failed";
      show(err, true);
    }
  });

  $("#btn-logout").addEventListener("click", () => {
    LeadIntelApi.setAuth(null);
    showLogin();
  });

  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => setRoute(btn.dataset.route));
  });

  $("#btn-refresh-leads").addEventListener("click", () =>
    loadLeads($("#lead-search").value.trim())
  );
  $("#lead-search").addEventListener("keydown", (e) => {
    if (e.key === "Enter") loadLeads(e.target.value.trim());
  });

  $("#odoo-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = $("#odoo-error");
    const once = $("#odoo-once");
    show(err, false);
    show(once, false);
    const fd = new FormData(e.target);
    try {
      const res = await LeadIntelApi.createOdoo({
        name: fd.get("name"),
        base_url: fd.get("base_url"),
        company_name: fd.get("company_name") || null,
        database_name: fd.get("database_name") || null,
        odoo_version: fd.get("odoo_version") || null,
      });
      $("#once-id").textContent = res.instance.id;
      $("#once-token").textContent = res.integration_token;
      $("#once-secret").textContent = res.webhook_secret;
      show(once, true);
      e.target.reset();
      await loadOdoo();
    } catch (ex) {
      err.textContent = ex.message;
      show(err, true);
    }
  });

  $("#btn-queue-fast")?.addEventListener("click", async () => {
    if (!selectedLeadId) return;
    try {
      const job = await LeadIntelApi.queueFast(selectedLeadId, true);
      lastJobId = job.id;
      alert(`Queued ${job.id}`);
      const lead = await LeadIntelApi.lead(selectedLeadId);
      await showLeadDetail(lead);
    } catch (err) {
      alert(err.message);
    }
  });

  $("#btn-run-latest-job")?.addEventListener("click", async () => {
    if (!lastJobId) {
      alert("Queue a job first");
      return;
    }
    try {
      const a = await LeadIntelApi.runJob(lastJobId);
      $("#lead-assessment-body").textContent = JSON.stringify(a, null, 2);
      await loadLeads();
    } catch (err) {
      alert(err.message);
    }
  });

  $("#provider-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = $("#provider-error");
    show(err, false);
    const fd = new FormData(e.target);
    try {
      await LeadIntelApi.createProvider({
        name: fd.get("name"),
        provider_type: fd.get("provider_type"),
        api_key: fd.get("api_key") || null,
        base_url: fd.get("base_url") || null,
        default_model: fd.get("default_model") || "gpt-4o-mini",
        is_default: fd.get("is_default") === "on",
      });
      e.target.reset();
      await loadProviders();
    } catch (ex) {
      err.textContent = ex.message;
      show(err, true);
    }
  });

  if (LeadIntelApi.getAuth()?.access_token) enterApp();
  else showLogin();
})();
