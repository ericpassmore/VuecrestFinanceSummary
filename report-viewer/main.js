const dataRoot = "./data";
const summaryCandidates = ["financial_summary.md"];
const monthNames = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

const dom = {
  navButtons: document.querySelectorAll("[data-view]"),
  monthList: document.getElementById("monthList"),
  summaryContent: document.getElementById("summaryContent"),
  infoBar: document.getElementById("infoBar"),
  selectedLabel: document.getElementById("selectedLabel"),
  statementLinks: document.getElementById("statementLinks"),
  monthItemTemplate: document.getElementById("monthItemTemplate"),
  reloadButton: document.getElementById("reloadButton"),
  statusDot: document.getElementById("statusDot"),
  reportView: document.getElementById("reportView"),
  legalView: document.getElementById("legalView"),
  legalForm: document.getElementById("legalForm"),
  legalYear: document.getElementById("legalYear"),
  legalMonth: document.getElementById("legalMonth"),
  legalActive: document.getElementById("legalActive"),
  closedLitigations: document.getElementById("closedLitigations"),
  legalStatus: document.getElementById("legalStatus"),
};

let months = [];
let activeKey = null;
let activeView = "reports";

function setStatus(state) {
  dom.statusDot.classList.remove("idle", "busy", "ready");
  dom.statusDot.classList.add(state);
  dom.statusDot.title =
    state === "busy"
      ? "Loading data..."
      : state === "ready"
      ? "Up to date"
      : "Idle";
}

function keyFor(item) {
  return `${item.year}-${item.month}`;
}

async function fetchDirectoryNumbers(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Unable to read ${url} (${response.status})`);
  }
  const html = await response.text();
  const doc = new DOMParser().parseFromString(html, "text/html");
  const hrefs = Array.from(doc.querySelectorAll("a")).map(
    (a) => a.getAttribute("href") || ""
  );
  return hrefs
    .map((href) => href.replace(/\/$/, ""))
    .filter((name) => name && name !== "..")
    .map((name) => Number(name))
    .filter((num) => Number.isFinite(num));
}

async function fetchIfExists(url) {
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) return null;
    return await response.text();
  } catch (err) {
    console.warn(`Failed to fetch ${url}:`, err);
    return null;
  }
}

async function fetchJsonIfExists(url) {
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) return null;
    return await response.json();
  } catch (err) {
    console.warn(`Failed to read JSON from ${url}:`, err);
    return null;
  }
}

async function resolveSummaryPath(year, month) {
  for (const candidate of summaryCandidates) {
    const url = `${dataRoot}/summaries/${year}/${month}/${candidate}`;
    const content = await fetchIfExists(url);
    if (content !== null) {
      return { url, content };
    }
  }
  return { url: null, content: null };
}

async function resolveFinancial(type, year, month) {
  const base = `${dataRoot}/html/${type}/${year}/${month}`;
  const meta = await fetchJsonIfExists(`${base}/meta.json`);
  if (!meta) return null;
  return {
    type,
    label: meta.label || `${type.replace("_", " ")} ${month}/${year}`,
    pageUrl: `${base}/page.html`,
    tableUrl: `${base}/table.html`,
  };
}

async function loadMonths() {
  const years = await fetchDirectoryNumbers(`${dataRoot}/summaries/`);
  const discovered = [];

  for (const year of years.sort((a, b) => b - a)) {
    const monthsInYear = await fetchDirectoryNumbers(
      `${dataRoot}/summaries/${year}/`
    );
    for (const month of monthsInYear.sort((a, b) => b - a)) {
      const summary = await resolveSummaryPath(year, month);
      const income = await resolveFinancial("income_statement", year, month);
      const balance = await resolveFinancial("balance_sheet", year, month);

      if (summary.url || income || balance) {
        discovered.push({
          year,
          month,
          label: `${monthNames[month - 1] || month} ${year}`,
          summaryUrl: summary.url,
          summaryContent: summary.content,
          income,
          balance,
        });
      }
    }
  }

  return discovered.sort((a, b) => b.year - a.year || b.month - a.month);
}

function renderMonthList() {
  dom.monthList.innerHTML = "";

  if (!months.length) {
    dom.monthList.innerHTML = `<div class="placeholder">No reports found in data/summaries</div>`;
    dom.selectedLabel.textContent = "No report selected";
    dom.summaryContent.innerHTML = `<div class="placeholder">Add a summary markdown file under data/summaries/&lt;year&gt;/&lt;month&gt;/</div>`;
    dom.statementLinks.innerHTML = "";
    return;
  }

  for (const item of months) {
    const clone =
      dom.monthItemTemplate.content.firstElementChild.cloneNode(true);
    clone.dataset.key = keyFor(item);
    clone.querySelector(".month-title").textContent = item.label;

    const incomeChip = clone.querySelector(".income-chip");
    const balanceChip = clone.querySelector(".balance-chip");
    const summaryChip = clone.querySelector(".summary-chip");

    incomeChip.style.opacity = item.income ? "1" : "0.35";
    balanceChip.style.opacity = item.balance ? "1" : "0.35";
    summaryChip.style.opacity = item.summaryUrl ? "1" : "0.35";

    clone.addEventListener("click", () => selectMonth(item));

    if (item.summaryUrl && !activeKey) {
      activeKey = keyFor(item);
      clone.classList.add("active");
    }

    dom.monthList.appendChild(clone);
  }
}

function updateActiveCard(key) {
  dom.monthList.querySelectorAll(".month-card").forEach((card) => {
    card.classList.toggle("active", card.dataset.key === key);
  });
}

function renderStatementLinks(item) {
  dom.statementLinks.innerHTML = "";
  const links = [];
  if (item.income) {
    links.push({
      label: "Income Statement (table)",
      url: item.income.tableUrl,
    });
  }
  if (item.balance) {
    links.push({ label: "Balance Sheet (table)", url: item.balance.tableUrl });
  }

  if (!links.length) {
    dom.statementLinks.innerHTML = `<span class="pill">No financial HTML snapshots for this month</span>`;
    return;
  }

  for (const link of links) {
    const anchor = document.createElement("a");
    anchor.href = link.url;
    anchor.textContent = link.label;
    anchor.target = "_blank";
    anchor.rel = "noreferrer";
    anchor.className = "link";
    dom.statementLinks.appendChild(anchor);
  }
}

function escapeHtml(value) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function formatInline(text) {
  return escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`(.+?)`/g, "<code>$1</code>");
}

function markdownToHtml(md) {
  const lines = md.split(/\r?\n/);
  let html = "";
  let inList = false;

  const closeList = () => {
    if (inList) {
      html += "</ul>";
      inList = false;
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    if (!line.trim()) {
      closeList();
      continue;
    }

    if (/^#{1,6}\s/.test(line)) {
      closeList();
      const level = line.match(/^#+/)[0].length;
      const content = formatInline(line.replace(/^#{1,6}\s/, ""));
      html += `<h${level}>${content}</h${level}>`;
      continue;
    }

    if (line.startsWith("- ")) {
      if (!inList) {
        html += "<ul>";
        inList = true;
      }
      html += `<li>${formatInline(line.replace(/^- /, ""))}</li>`;
      continue;
    }

    if (/^---+$/.test(line)) {
      closeList();
      html += "<hr />";
      continue;
    }

    closeList();
    html += `<p>${formatInline(line)}</p>`;
  }

  closeList();
  return html || '<div class="placeholder">Summary is empty.</div>';
}

function showView(targetView) {
  activeView = targetView;
  const views = {
    reports: dom.reportView,
    legal: dom.legalView,
  };

  Object.entries(views).forEach(([key, el]) => {
    if (!el) return;
    el.classList.toggle("hidden", key !== targetView);
  });

  dom.navButtons.forEach((btn) => {
    const isActive = btn.dataset.view === targetView;
    btn.classList.toggle("active", isActive);
    btn.setAttribute("aria-pressed", String(isActive));
  });
}

function initNavigation() {
  dom.navButtons.forEach((btn) =>
    btn.addEventListener("click", () => showView(btn.dataset.view))
  );
}

function populateSelect(select, values) {
  if (!select) return;
  select.innerHTML = "";
  values.forEach(({ value, label }) => {
    const opt = document.createElement("option");
    opt.value = String(value);
    opt.textContent = label;
    select.appendChild(opt);
  });
}

function seedLegalForm() {
  if (!dom.legalForm) return;
  const now = new Date();
  const currentYear = now.getFullYear();

  populateSelect(dom.legalYear, [
    { value: currentYear, label: String(currentYear) },
    { value: currentYear + 1, label: String(currentYear + 1) },
  ]);

  populateSelect(
    dom.legalMonth,
    Array.from({ length: 12 }, (_, i) => {
      const month = i + 1;
      return { value: month, label: month.toString().padStart(2, "0") };
    })
  );
  dom.legalMonth.value = String(now.getMonth() + 1);

  populateSelect(
    dom.legalActive,
    Array.from({ length: 11 }, (_, i) => ({ value: i, label: String(i) }))
  );
}

function setLegalStatus(message, kind = "muted") {
  if (!dom.legalStatus) return;
  dom.legalStatus.textContent = message;
  dom.legalStatus.className = `callout ${kind}`;
}

async function submitLegalDetails(event) {
  event.preventDefault();
  if (
    !dom.legalYear ||
    !dom.legalMonth ||
    !dom.legalActive ||
    !dom.closedLitigations
  ) {
    return;
  }

  const payload = {
    year: Number(dom.legalYear.value),
    month: Number(dom.legalMonth.value),
    active_litigation: Number(dom.legalActive.value),
    closed_litigations: dom.closedLitigations.value.trim(),
  };

  setLegalStatus("Saving legal details...", "muted");
  try {
    const response = await fetch("api/legal-details", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const info = await response.json().catch(() => ({}));
      const message = info.error || `Save failed (${response.status})`;
      throw new Error(message);
    }

    const info = await response.json();
    const savedPath = info.path || "server";
    setLegalStatus(`Saved legal details to ${savedPath}.`, "success");
  } catch (err) {
    setLegalStatus(
      `Error saving legal details: ${err.message || err}`,
      "error"
    );
  }
}

async function selectMonth(item) {
  activeKey = keyFor(item);
  updateActiveCard(activeKey);
  dom.selectedLabel.textContent = item.label;
  renderStatementLinks(item);

  if (!item.summaryUrl) {
    dom.summaryContent.innerHTML = `<div class="placeholder">No summary markdown found for ${item.label}.</div>`;
    return;
  }

  if (!item.summaryContent) {
    dom.summaryContent.innerHTML = `<div class="placeholder">Loading summary...</div>`;
    item.summaryContent = await fetchIfExists(item.summaryUrl);
  }

  if (!item.summaryContent) {
    dom.summaryContent.innerHTML = `<div class="placeholder">Could not load ${item.summaryUrl}.</div>`;
    return;
  }

  dom.summaryContent.innerHTML = markdownToHtml(item.summaryContent);
}

async function bootstrap() {
  setStatus("busy");
  dom.summaryContent.innerHTML = `<div class="placeholder">Looking for reports in ${dataRoot}...</div>`;
  try {
    initNavigation();
    seedLegalForm();
    dom.legalForm?.addEventListener("submit", submitLegalDetails);
    showView(activeView);
    months = await loadMonths();
    renderMonthList();
    if (months.length) {
      selectMonth(months[0]);
    }
    setStatus("ready");
  } catch (err) {
    console.error(err);
    setStatus("idle");
    dom.summaryContent.innerHTML = `<div class="placeholder">Error: ${escapeHtml(
      err.message || String(err)
    )}</div>`;
  }
}

dom.reloadButton?.addEventListener("click", bootstrap);

bootstrap();
