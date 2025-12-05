const dataRoot = "./data";
const summaryCandidates = ["summary.md", "financial_summary.md"];
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
  monthList: document.getElementById("monthList"),
  summaryContent: document.getElementById("summaryContent"),
  infoBar: document.getElementById("infoBar"),
  selectedLabel: document.getElementById("selectedLabel"),
  statementLinks: document.getElementById("statementLinks"),
  monthItemTemplate: document.getElementById("monthItemTemplate"),
  reloadButton: document.getElementById("reloadButton"),
  statusDot: document.getElementById("statusDot"),
};

let months = [];
let activeKey = null;

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
