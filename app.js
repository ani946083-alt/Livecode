(() => {
  const params = new URLSearchParams(window.location.search);
  const apiBase = (params.get("api") || "/api").replace(/\/+$/, "");
  let roads = [];
  let summary = null;
  const roadsList = document.querySelector("#roads-list");
  const notice = document.querySelector("#notice");
  const searchInput = document.querySelector("#search-input");
  const statusFilter = document.querySelector("#status-filter");
  const form = document.querySelector("#report-submit-form");
  const submitButton = document.querySelector("#submit-button");
  const formMessage = document.querySelector("#form-message");

  document.querySelector("#today-label").textContent = new Intl.DateTimeFormat("bn-BD", {
    weekday: "short",
    day: "numeric",
    month: "short",
  }).format(new Date());

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[character]);
  }

  function formatTime(value) {
    if (!value) return "সময় উল্লেখ নেই";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "সময় উল্লেখ নেই";
    const minutes = Math.max(0, Math.floor((Date.now() - date.getTime()) / 60000));
    if (minutes < 1) return "এইমাত্র";
    if (minutes < 60) return `${minutes} মিনিট আগে`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} ঘণ্টা আগে`;
    return new Intl.DateTimeFormat("bn-BD", { day: "numeric", month: "short" }).format(date);
  }

  function statusInfo(status) {
    const values = {
      severe: ["অতি উচ্চ ঝুঁকি", "status-blocked"],
      high: ["উচ্চ ঝুঁকি", "status-waterlogged"],
      moderate: ["মাঝারি ঝুঁকি", "status-waterlogged"],
      low: ["কম ঝুঁকি", "status-passable"],
      unknown: ["অবস্থা অজানা", "status-unknown"],
    };
    return values[status] || values.unknown;
  }

  function sortRoads(items) {
    const priority = { severe: 0, high: 1, moderate: 2, low: 3, unknown: 4 };
    return [...items].sort((a, b) => {
      const byStatus = (priority[a.status] ?? 2) - (priority[b.status] ?? 2);
      if (byStatus) return byStatus;
      const byDepth = (Number(b.depth_estimate_cm) || 0) - (Number(a.depth_estimate_cm) || 0);
      if (byDepth) return byDepth;
      return new Date(b.latest_report_at || 0) - new Date(a.latest_report_at || 0);
    });
  }

  function normalizeArea(value) {
    return String(value || "").normalize("NFC").trim().replace(/\s+/g, " ").toLocaleLowerCase();
  }

  function updateStats() {
    const areas = summary && Array.isArray(summary.areas) ? summary.areas : [];
    document.querySelector("#roads-count").textContent = Number(summary?.area_count || 0).toLocaleString("bn-BD");
    document.querySelector("#blocked-count").textContent = areas.filter((area) => area.status === "severe").length.toLocaleString("bn-BD");
    document.querySelector("#water-count").textContent = areas.filter((area) => ["high", "moderate"].includes(area.status)).length.toLocaleString("bn-BD");
    document.querySelector("#reports-count").textContent = Number(summary?.total_reports || 0).toLocaleString("bn-BD");
  }

  function renderRoad(road) {
    const [label, className] = statusInfo(road.status);
    const recent = Array.isArray(road.recent_reports) ? road.recent_reports.slice(0, 2) : [];
    const depth = Number.isFinite(Number(road.depth_estimate_cm)) && road.depth_estimate_cm !== null
      ? `<span class="meta-item"><span class="meta-symbol">≋</span><span class="depth-value">প্রায় ${escapeHtml(road.depth_estimate_cm)} সেমি${road.depth_is_approximate ? "*" : ""}</span></span>`
      : "";
    const flags = [
      road.has_disagreement ? '<span class="disagreement">⚠ রিপোর্টে মতভেদ</span>' : "",
      road.is_stale ? '<span class="stale-label">• পুরোনো রিপোর্ট</span>' : "",
      road.needs_review ? '<span class="review-label">যাচাই প্রয়োজন</span>' : "",
    ].filter(Boolean).join("");
    const notes = recent.map((report) =>
      `<div class="road-note${road.has_disagreement ? " warning" : ""}">“${escapeHtml(report.text)}”</div>`,
    ).join("");

    return `
      <article class="road-row">
        <div class="road-main">
          <div class="road-title-wrap">
            <div class="road-title">${escapeHtml(road.road_name || "নামহীন রাস্তা")}</div>
            <div class="road-area">${escapeHtml(road.area || "এলাকা উল্লেখ নেই")}</div>
          </div>
          <span class="status-pill ${className}">${label}</span>
        </div>
        <div class="road-meta">
          ${depth}
          <span class="meta-item"><span class="meta-symbol">▤</span>${Number(road.report_count) || 0}টি রিপোর্ট</span>
          ${flags}
          <span class="freshness">${formatTime(road.latest_report_at)}</span>
        </div>
        ${notes}
      </article>`;
  }

  function render() {
    updateStats();
    const query = searchInput.value.trim().toLocaleLowerCase();
    const selectedStatus = statusFilter.value;
    const visibleRoads = sortRoads(roads).filter((road) => {
      const matchesQuery = `${road.road_name || ""} ${road.area || ""}`.toLocaleLowerCase().includes(query);
      return matchesQuery && (selectedStatus === "all" || road.status === selectedStatus);
    });

    roadsList.innerHTML = visibleRoads.length
      ? visibleRoads.map(renderRoad).join("")
      : '<div class="empty-state">এই খোঁজে কোনো রাস্তার রিপোর্ট পাওয়া যায়নি।</div>';
  }

  async function loadRoads() {
    roadsList.innerHTML = '<div class="loading-state">রিপোর্ট লোড হচ্ছে...</div>';
    notice.hidden = true;
    try {
      const [summaryResponse, reportsResponse] = await Promise.all([
        fetch(`${apiBase}/summary`, { headers: { Accept: "application/json" } }),
        fetch(`${apiBase}/reports`, { headers: { Accept: "application/json" } }),
      ]);
      if (!summaryResponse.ok) throw new Error(`সারাংশ আনা যায়নি (HTTP ${summaryResponse.status})`);
      if (!reportsResponse.ok) throw new Error(`রিপোর্ট আনা যায়নি (HTTP ${reportsResponse.status})`);
      const summaryPayload = await summaryResponse.json();
      const reportPayload = await reportsResponse.json();
      if (!Array.isArray(summaryPayload.worst_areas) || !Array.isArray(summaryPayload.areas)) {
        throw new Error("Backend-এর /summary response-এর format সঠিক নয়।");
      }
      if (!Array.isArray(reportPayload)) {
        throw new Error("Backend-এর /reports response-এর format সঠিক নয়।");
      }
      summary = summaryPayload;
      document.querySelector("#connection-label").textContent = "লাইভ Backend";
      const freshReportsByArea = new Map();
      reportPayload.filter((report) => !report.is_old).forEach((report) => {
        const key = normalizeArea(report.area);
        if (!freshReportsByArea.has(key)) freshReportsByArea.set(key, []);
        freshReportsByArea.get(key).push(report);
      });
      roads = summary.worst_areas.map((area) => {
        const key = normalizeArea(area.area);
        const areaReports = (freshReportsByArea.get(key) || [])
          .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        return {
          road_name: area.road_name || area.area,
          area: area.area,
          status: area.status || "unknown",
          depth_estimate_cm: area.depth_cm,
          depth_is_approximate: area.needs_review || area.has_conflict || area.confidence < 0.9,
          latest_report_at: area.latest_report_at,
          report_count: area.report_count,
          has_disagreement: area.has_conflict,
          is_stale: false,
          needs_review: area.needs_review,
          recent_reports: areaReports.slice(0, 2).map((report) => ({
            text: report.text,
            reported_at: report.created_at,
          })),
        };
      });
      render();
    } catch (error) {
      roads = [];
      summary = null;
      document.querySelector("#connection-label").textContent = "Backend সংযোগ নেই";
      roadsList.innerHTML = '<div class="empty-state">লাইভ রিপোর্ট লোড করা যায়নি। API ঠিক আছে কি না দেখে আবার চেষ্টা করুন।</div>';
      notice.textContent = `লাইভ API-তে সংযোগ করা যায়নি: ${error.message}`;
      notice.hidden = false;
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    formMessage.hidden = true;
    submitButton.disabled = true;
    submitButton.querySelector("span").textContent = "জমা হচ্ছে...";

    const report = {
      road_name: document.querySelector("#road-name").value.trim(),
      area: document.querySelector("#area-name").value.trim(),
      text: document.querySelector("#report-text").value.trim(),
    };

    try {
      const response = await fetch(`${apiBase}/reports`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(report),
      });
      if (!response.ok) {
        let reason = `রিপোর্ট জমা দেওয়া যায়নি (HTTP ${response.status})`;
        try {
          const body = await response.json();
          if (body.message || body.error) reason = body.message || body.error;
        } catch {
          // Keep the HTTP error when the server does not return JSON.
        }
        throw new Error(reason);
      }
      await response.json();
      await loadRoads();
      if (!notice.hidden) throw new Error("রিপোর্ট জমা হয়েছে, কিন্তু তালিকা রিফ্রেশ করা যায়নি।");
      form.reset();
      formMessage.textContent = "রিপোর্ট Backend-এ সংরক্ষিত হয়েছে। ধন্যবাদ!";
      formMessage.className = "form-message success";
      formMessage.hidden = false;
    } catch (error) {
      formMessage.textContent = error.message || "রিপোর্ট জমা দেওয়া যায়নি। আবার চেষ্টা করুন।";
      formMessage.className = "form-message error";
      formMessage.hidden = false;
    } finally {
      submitButton.disabled = false;
      submitButton.querySelector("span").textContent = "রিপোর্ট জমা দিন";
    }
  });

  searchInput.addEventListener("input", render);
  statusFilter.addEventListener("change", render);
  document.querySelector("#refresh-button").addEventListener("click", loadRoads);

  loadRoads();
  window.setInterval(loadRoads, 60_000);
})();
