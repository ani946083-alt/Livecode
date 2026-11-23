(() => {
  const params = new URLSearchParams(window.location.search);
  const apiBase = (params.get("api") || "").replace(/\/+$/, "");
  const isDemo = !apiBase;

  const demoRoads = [
    {
      id: "road-1",
      road_name: "স্টেশন রোড",
      area: "নতুন বাজার",
      status: "blocked",
      depth_estimate_cm: 55,
      depth_is_approximate: true,
      latest_report_at: new Date(Date.now() - 12 * 60 * 1000).toISOString(),
      report_count: 4,
      has_disagreement: true,
      is_stale: false,
      recent_reports: [
        { text: "রাস্তা প্রায় বন্ধ, পানি কোমর পর্যন্ত", reported_at: new Date(Date.now() - 12 * 60 * 1000).toISOString() },
        { text: "দোকানের সামনে হাঁটু-সমান পানি", reported_at: new Date(Date.now() - 20 * 60 * 1000).toISOString() },
      ],
    },
    {
      id: "road-2",
      road_name: "কলেজ রোড",
      area: "মধ্যপাড়া",
      status: "waterlogged",
      depth_estimate_cm: 35,
      depth_is_approximate: true,
      latest_report_at: new Date(Date.now() - 34 * 60 * 1000).toISOString(),
      report_count: 6,
      has_disagreement: false,
      is_stale: false,
      recent_reports: [
        { text: "হাঁটু-সমান পানি, রিকশা কোনোমতে যাচ্ছে", reported_at: new Date(Date.now() - 34 * 60 * 1000).toISOString() },
      ],
    },
    {
      id: "road-3",
      road_name: "হাসপাতাল সংযোগ সড়ক",
      area: "দক্ষিণপাড়া",
      status: "waterlogged",
      depth_estimate_cm: 12,
      depth_is_approximate: false,
      latest_report_at: new Date(Date.now() - 78 * 60 * 1000).toISOString(),
      report_count: 3,
      has_disagreement: true,
      is_stale: false,
      recent_reports: [
        { text: "নালা উপচে পানি উঠেছে, প্রায় ১২ সেমি", reported_at: new Date(Date.now() - 78 * 60 * 1000).toISOString() },
        { text: "এখন পানি কম, মোটরসাইকেল যাচ্ছে", reported_at: new Date(Date.now() - 86 * 60 * 1000).toISOString() },
      ],
    },
    {
      id: "road-4",
      road_name: "পুরাতন ব্রিজ",
      area: "পূর্বপাড়া",
      status: "passable",
      depth_estimate_cm: null,
      depth_is_approximate: false,
      latest_report_at: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
      report_count: 2,
      has_disagreement: false,
      is_stale: true,
      recent_reports: [
        { text: "পানি নেমেছে, ছোট গাড়ি চলাচল করছে", reported_at: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString() },
      ],
    },
  ];

  let roads = isDemo ? [...demoRoads] : [];
  const roadsList = document.querySelector("#roads-list");
  const notice = document.querySelector("#notice");
  const searchInput = document.querySelector("#search-input");
  const statusFilter = document.querySelector("#status-filter");
  const form = document.querySelector("#report-submit-form");
  const submitButton = document.querySelector("#submit-button");
  const formMessage = document.querySelector("#form-message");

  document.querySelector("#connection-label").textContent = isDemo ? "ডেমো ডেটা" : "লাইভ API";
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
      blocked: ["চলাচল বন্ধ", "status-blocked"],
      waterlogged: ["পানির প্রভাব", "status-waterlogged"],
      passable: ["চলাচল সম্ভব", "status-passable"],
      unknown: ["অবস্থা অজানা", "status-unknown"],
    };
    return values[status] || values.unknown;
  }

  function sortRoads(items) {
    const priority = { blocked: 0, waterlogged: 1, unknown: 2, passable: 3 };
    return [...items].sort((a, b) => {
      const byStatus = (priority[a.status] ?? 2) - (priority[b.status] ?? 2);
      if (byStatus) return byStatus;
      return new Date(b.latest_report_at || 0) - new Date(a.latest_report_at || 0);
    });
  }

  function updateStats() {
    document.querySelector("#roads-count").textContent = roads.length.toLocaleString("bn-BD");
    document.querySelector("#blocked-count").textContent = roads.filter((road) => road.status === "blocked").length.toLocaleString("bn-BD");
    document.querySelector("#water-count").textContent = roads.filter((road) => road.status === "waterlogged").length.toLocaleString("bn-BD");
    document.querySelector("#reports-count").textContent = roads.reduce((sum, road) => sum + (Number(road.report_count) || 0), 0).toLocaleString("bn-BD");
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
    if (isDemo) {
      render();
      return;
    }

    roadsList.innerHTML = '<div class="loading-state">রিপোর্ট লোড হচ্ছে...</div>';
    notice.hidden = true;
    try {
      const response = await fetch(`${apiBase}/roads`, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`রাস্তার রিপোর্ট আনা যায়নি (HTTP ${response.status})`);
      const payload = await response.json();
      const records = Array.isArray(payload) ? payload : payload.roads;
      if (!Array.isArray(records)) throw new Error("Backend-এর /roads response-এর format সঠিক নয়।");
      roads = records;
      render();
    } catch (error) {
      roadsList.innerHTML = '<div class="empty-state">লাইভ রিপোর্ট লোড করা যায়নি। API ঠিক আছে কি না দেখে আবার চেষ্টা করুন।</div>';
      notice.textContent = `লাইভ API-তে সংযোগ করা যায়নি: ${error.message}`;
      notice.hidden = false;
    }
  }

  function classifyDemoReport(text) {
    const normalized = text.toLocaleLowerCase();
    if (/বন্ধ|যাওয়া যাচ্ছে না|চলাচল অসম্ভব/.test(normalized)) return "blocked";
    if (/পানি|জল|ডুব|জমে/.test(normalized)) return "waterlogged";
    if (/চলাচল|যাচ্ছে|পাস/.test(normalized)) return "passable";
    return "unknown";
  }

  async function submitDemoReport(report) {
    const currentTime = new Date().toISOString();
    const existing = roads.find((road) =>
      road.road_name.toLocaleLowerCase() === report.road_name.toLocaleLowerCase()
      && road.area.toLocaleLowerCase() === report.area.toLocaleLowerCase(),
    );
    if (existing) {
      existing.status = classifyDemoReport(report.text);
      existing.latest_report_at = currentTime;
      existing.report_count = (Number(existing.report_count) || 0) + 1;
      existing.recent_reports = [{ text: report.text, reported_at: currentTime }, ...(existing.recent_reports || [])].slice(0, 2);
      existing.has_disagreement = false;
      existing.is_stale = false;
    } else {
      roads.unshift({
        id: `demo-${Date.now()}`,
        ...report,
        status: classifyDemoReport(report.text),
        depth_estimate_cm: null,
        depth_is_approximate: false,
        latest_report_at: currentTime,
        report_count: 1,
        has_disagreement: false,
        is_stale: false,
        recent_reports: [{ text: report.text, reported_at: currentTime }],
      });
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
      if (isDemo) {
        await submitDemoReport(report);
      } else {
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
        await loadRoads();
        if (!notice.hidden) throw new Error("রিপোর্ট জমা হয়েছে, কিন্তু তালিকা রিফ্রেশ করা যায়নি।");
      }

      form.reset();
      render();
      formMessage.textContent = isDemo
        ? "ডেমোতে রিপোর্ট যোগ হয়েছে। এটি Backend-এ সংরক্ষিত হয়নি।"
        : "রিপোর্ট সফলভাবে জমা হয়েছে। ধন্যবাদ!";
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
})();
