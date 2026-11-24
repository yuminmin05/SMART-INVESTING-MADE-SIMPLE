/* ส่วนควบคุมหน้าเว็บและเชื่อมต่อ Django API ด้วย Fetch */
(() => {
  const state = {
    stocks: [],
    selected: [],
    returns: {},
    jobId: null,
    results: null,
    monthlyMoney: 0,
    activeYear: 1,
    donutChart: null,
    barChart: null,
    pollTimer: null,
    toastTimer: null,
  };
  const byId = (id) => document.getElementById(id);
  const money = (value) => Number(value).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  const csrfToken = () => {
    const field = document.querySelector("[name=csrfmiddlewaretoken]");
    return field ? field.value : "";
  };

  async function request(url, options = {}) {
    const response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(),
        ...(options.headers || {}),
      },
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "เกิดข้อผิดพลาด กรุณาลองอีกครั้ง");
    return data;
  }

  function showToast(message) {
    const toast = byId("toast");
    toast.textContent = message;
    toast.classList.remove("hidden");
    window.clearTimeout(state.toastTimer);
    state.toastTimer = window.setTimeout(() => toast.classList.add("hidden"), 3500);
  }

  function renderChips() {
    const container = byId("selected-chips");
    container.replaceChildren();
    state.selected.forEach((symbol) => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.append(document.createTextNode(symbol));
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "×";
      remove.setAttribute("aria-label", `นำ ${symbol} ออกจากรายการ`);
      remove.addEventListener("click", () => {
        state.selected = state.selected.filter((item) => item !== symbol);
        renderChips();
        renderStockOptions(byId("stock-search").value);
      });
      chip.append(remove);
      container.append(chip);
    });
    byId("stock-count").textContent = `${state.selected.length} หุ้นที่เลือก`;
  }

  function renderStockOptions(query = "") {
    const options = byId("stock-options");
    const normalized = query.trim().toUpperCase();
    const matches = state.stocks.filter((item) =>
      item.symbol.includes(normalized) && !state.selected.includes(item.symbol)
    );
    options.replaceChildren();
    if (!matches.length) {
      const empty = document.createElement("div");
      empty.className = "stock-option";
      empty.textContent = normalized ? "ไม่พบหุ้นที่ค้นหา" : "เลือกหุ้นครบแล้ว";
      options.append(empty);
    } else {
      matches.slice(0, 20).forEach((item) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "stock-option";
        button.setAttribute("role", "option");
        const symbol = document.createElement("strong");
        symbol.textContent = item.symbol;
        const hint = document.createElement("span");
        hint.textContent = `${Number(item.annual_return).toFixed(2)}% ต่อปี`;
        button.append(symbol, hint);
        button.addEventListener("click", () => {
          state.selected.push(item.symbol);
          renderChips();
          byId("stock-search").value = "";
          renderStockOptions();
          byId("stock-search").focus();
        });
        options.append(button);
      });
    }
  }

  function renderReturns() {
    const body = byId("returns-body");
    body.replaceChildren();
    state.stocks.forEach((stock) => {
      const row = document.createElement("tr");
      const symbol = document.createElement("td");
      symbol.textContent = stock.symbol;
      const yahoo = document.createElement("td");
      yahoo.textContent = `${stock.symbol}.BK`;
      const value = document.createElement("td");
      const input = document.createElement("input");
      input.type = "number";
      input.min = "-100";
      input.max = "1000";
      input.step = "0.01";
      input.value = Number(stock.annual_return).toFixed(2);
      input.dataset.symbol = stock.symbol;
      input.setAttribute("aria-label", `ผลตอบแทนต่อปีของ ${stock.symbol} เป็นเปอร์เซ็นต์`);
      value.append(input);
      row.append(symbol, yahoo, value);
      body.append(row);
    });
  }

  function validateForm() {
    const stockError = byId("stocks-error");
    const moneyError = byId("money-error");
    const monthlyMoney = Number(byId("monthly-money").value.replaceAll(",", ""));
    stockError.textContent = "";
    moneyError.textContent = "";
    byId("form-error").textContent = "";
    if (new Set(state.selected).size !== state.selected.length) {
      stockError.textContent = "พบหุ้นซ้ำ กรุณาตรวจสอบรายการที่เลือก";
      return false;
    }
    if (state.selected.length < 2) {
      stockError.textContent = "กรุณาเลือกหุ้น SET50 อย่างน้อย 2 ตัว";
      return false;
    }
    if (state.selected.some((symbol) => !state.stocks.some((stock) => stock.symbol === symbol))) {
      stockError.textContent = "มีหุ้นที่ไม่อยู่ใน SET50 กรุณาเลือกจากรายการ";
      return false;
    }
    if (!Number.isFinite(monthlyMoney) || monthlyMoney <= 0) {
      moneyError.textContent = "กรุณากรอกเงินลงทุนต่อเดือนให้มากกว่า 0 บาท";
      return false;
    }
    state.monthlyMoney = monthlyMoney;
    return true;
  }

  function setLoading(loading) {
    const button = byId("optimize-button");
    button.disabled = loading;
    button.querySelector(".button-label").classList.toggle("hidden", loading);
    button.querySelector(".button-loading").classList.toggle("hidden", !loading);
  }

  async function startOptimization(event) {
    event.preventDefault();
    if (!validateForm()) return;
    setLoading(true);
    byId("results-panel").classList.add("hidden");
    byId("progress-panel").classList.remove("hidden");
    byId("progress-bar").style.width = "0%";
    try {
      const response = await request("/api/optimize/", {
        method: "POST",
        body: JSON.stringify({
          stocks: state.selected,
          monthly_money: state.monthlyMoney,
          ga_params: {
            population_size: 60,
            generations: 100,
            crossover_prob: 0.9,
            mutation_rate: 0.1,
            mutation_sigma: 0.05,
            eta_c: 20,
            tournament_size: 3,
            elite_size: 2
          }
        }),
      });
      state.jobId = response.job_id;
      await pollJob();
    } catch (error) {
      byId("form-error").textContent = error.message;
      byId("progress-panel").classList.add("hidden");
      setLoading(false);
    }
  }

  async function pollJob() {
    try {
      const job = await request(`/api/optimize/${state.jobId}/`, { headers: {} });
      const completedYears = Number(job.completed_years || 0);
      const yearProgress = job.status === "completed" ? 3 : Math.min(completedYears, 3);
      byId("progress-description").textContent = job.status === "completed"
        ? "คำนวณครบทุกระยะแล้ว"
        : `กำลังคำนวณระยะ ${job.current_year || 1} ปี · เสร็จแล้ว ${completedYears}/3 ระยะ`;
      byId("progress-percent").textContent = `${Math.floor(yearProgress / 3 * 100)}%`;
      byId("progress-bar").style.width = `${yearProgress / 3 * 100}%`;

      if (job.status === "completed") {
        state.results = job.results;
        state.monthlyMoney = job.monthly_money;
        state.activeYear = job.best_years;
        renderResults(job);
        byId("progress-panel").classList.add("hidden");
        byId("results-panel").classList.remove("hidden");
        setLoading(false);
        byId("results-panel").scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }
      if (job.status === "failed") throw new Error(job.error || "คำนวณไม่สำเร็จ");
      state.pollTimer = window.setTimeout(pollJob, 650);
    } catch (error) {
      byId("form-error").textContent = error.message;
      byId("progress-panel").classList.add("hidden");
      setLoading(false);
    }
  }

  function renderResults(job) {
    const years = [1, 5, 10];
    const bestYear = job.best_years;
    const best = job.results[String(bestYear)];
    const bestProfit = best.profit >= 0
      ? `<span class="positive">${money(best.profit)} บาท</span>`
      : `<span class="negative">${money(best.profit)} บาท</span>`;
    byId("best-summary").innerHTML = `
      <article class="summary-card"><span>จำนวนหุ้นที่เลือก</span><strong>${job.stocks.length} ตัว</strong><small>SET50</small></article>
      <article class="summary-card"><span>เงินลงทุนต่อเดือน</span><strong>${money(job.monthly_money)}</strong><small>บาท / เดือน</small></article>
      <article class="summary-card"><span>ช่วงเวลาที่กำไรมากที่สุด</span><strong>${bestYear} ปี</strong><small>เงินลงทุนรวม ${money(best.total_investment)} บาท</small></article>
      <article class="summary-card"><span>มูลค่าอนาคต · กำไรโดยประมาณ</span><strong>${money(best.fv)}</strong><small>${bestProfit}</small></article>
      <article class="summary-card"><span>อัลกอริทึม</span><strong>Genetic Algorithm</strong><small>Fitness: Future Value · ${best.generations} generations</small></article>`;

    const table = byId("comparison-body");
    table.replaceChildren();
    years.forEach((year) => {
      const result = job.results[String(year)];
      const row = document.createElement("tr");
      if (year === bestYear) row.className = "best-row";
      const profitClass = result.profit >= 0 ? "positive" : "negative";
      row.innerHTML = `<td><strong>${year} ปี</strong></td><td>${money(result.total_investment)} บาท</td><td>${money(result.fv)} บาท</td><td class="${profitClass}">${money(result.profit)} บาท</td><td>${year === bestYear ? '<span class="best-pill">กำไรมากที่สุด</span>' : ""}</td>`;
      table.append(row);
    });

    renderCharts(job);
    renderPortfolio(bestYear);
  }

  function renderCharts(job) {
    if (typeof Chart === "undefined") return;
    const palette = ["#16804a", "#49a96d", "#8acb9e", "#c5e8ce", "#317455", "#a9d8b6", "#6db888", "#195f3a"];
    if (state.donutChart) state.donutChart.destroy();
    state.donutChart = new Chart(byId("donut-chart"), {
      type: "doughnut",
      data: {
        labels: state.selected,
        datasets: [{ data: job.results[String(state.activeYear)].weights, backgroundColor: state.selected.map((_, i) => palette[i % palette.length]), borderWidth: 2, borderColor: getComputedStyle(document.body).getPropertyValue("--panel") }],
      },
      options: { responsive: true, maintainAspectRatio: false, cutout: "66%", plugins: { legend: { position: "bottom", labels: { boxWidth: 9, usePointStyle: true, font: { size: 10 } } } } },
    });
    if (state.barChart) state.barChart.destroy();
    state.barChart = new Chart(byId("bar-chart"), {
      type: "bar",
      data: {
        labels: ["1 ปี", "5 ปี", "10 ปี"],
        datasets: [
          { label: "เงินลงทุนรวม", data: [1, 5, 10].map((year) => job.results[String(year)].total_investment), backgroundColor: "#c5e8ce", borderRadius: 5 },
          { label: "มูลค่าในอนาคต", data: [1, 5, 10].map((year) => job.results[String(year)].fv), backgroundColor: "#16804a", borderRadius: 5 },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, ticks: { callback: (value) => `${(Number(value) / 1000000).toFixed(1)}M` } },
        },
        plugins: { legend: { position: "bottom", labels: { boxWidth: 9, usePointStyle: true, font: { size: 10 } } } },
      },
    });
  }

  function renderPortfolio(year) {
    const result = state.results[String(year)];
    const body = byId("portfolio-body");
    body.replaceChildren();
    let totalWeight = 0;
    state.selected.forEach((symbol, index) => {
      const weight = result.weights[index];
      totalWeight += weight;
      const row = document.createElement("tr");
      row.innerHTML = `<td><strong>${symbol}</strong></td><td>${Number(weight).toFixed(2)}%</td><td>${money(state.monthlyMoney * weight / 100)}</td>`;
      body.append(row);
    });
    byId("total-weight").textContent = `${totalWeight.toFixed(2)}%`;
    byId("total-monthly").textContent = `${money(state.monthlyMoney)} บาท`;
    byId("detail-highlight").innerHTML = `
      <span>ช่วงเวลา <strong>${year} ปี</strong></span>
      <span>เงินลงทุนรวม <strong>${money(result.total_investment)} บาท</strong></span>
      <span>มูลค่าอนาคต <strong>${money(result.fv)} บาท</strong></span>
      <span>กำไรโดยประมาณ <strong class="${result.profit >= 0 ? "positive" : "negative"}">${money(result.profit)} บาท</strong></span>`;
    document.querySelectorAll(".result-tabs button").forEach((button) => {
      button.setAttribute("aria-selected", String(Number(button.dataset.year) === year));
    });
    if (state.donutChart) {
      state.donutChart.data.datasets[0].data = result.weights;
      state.donutChart.update();
    }
  }

  function exportCsv() {
    if (!state.results) return;
    const rows = [
      ["ระยะเวลา (ปี)", "หุ้น", "Weight (%)", "เงินลงทุนต่อเดือน (บาท)", "เงินลงทุนรวม (บาท)", "มูลค่าอนาคต (บาท)", "กำไร (บาท)"],
    ];
    [1, 5, 10].forEach((year) => {
      const result = state.results[String(year)];
      state.selected.forEach((symbol, index) => {
        rows.push([
          year, symbol, Number(result.weights[index]).toFixed(6),
          (state.monthlyMoney * result.weights[index] / 100).toFixed(2),
          result.total_investment.toFixed(2), result.fv.toFixed(2), result.profit.toFixed(2),
        ]);
      });
    });
    const csv = "\uFEFF" + rows.map((row) => row.map((cell) =>
      `"${String(cell).replaceAll('"', '""')}"`
    ).join(",")).join("\r\n");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    link.download = "smart-dca-portfolio.csv";
    link.click();
    URL.revokeObjectURL(link.href);
  }

  async function saveReturns() {
    const inputs = [...document.querySelectorAll("#returns-body input")];
    const returns = {};
    for (const input of inputs) {
      const value = Number(input.value);
      if (!Number.isFinite(value) || value < -100 || value > 1000) {
        input.focus();
        byId("returns-message").textContent = "ผลตอบแทนต้องอยู่ระหว่าง -100 ถึง 1,000%";
        return;
      }
      returns[input.dataset.symbol] = value;
    }
    try {
      await request("/api/stocks/", { method: "POST", body: JSON.stringify({ returns }) });
      state.stocks = state.stocks.map((stock) => ({ ...stock, annual_return: returns[stock.symbol] }));
      renderStockOptions(byId("stock-search").value);
      byId("returns-message").textContent = "บันทึกผลตอบแทนลงในฐานข้อมูลแล้ว";
      showToast("บันทึกผลตอบแทนเรียบร้อย");
    } catch (error) {
      byId("returns-message").textContent = error.message;
    }
  }

  async function updateFromYahoo() {
    byId("returns-message").textContent = "กำลังดึงข้อมูลจริงจาก Yahoo Finance...";
    try {
      const response = await request("/api/stocks/yahoo/", {
        method: "POST",
        body: JSON.stringify({ symbols: state.stocks.map((stock) => stock.symbol) }),
      });
      for (const [symbol, value] of Object.entries(response.updated)) {
        const stock = state.stocks.find((item) => item.symbol === symbol);
        if (stock) stock.annual_return = value;
      }
      renderReturns();
      renderStockOptions(byId("stock-search").value);
      byId("returns-message").textContent = response.message;
      showToast(response.failed.length
        ? `อัปเดตสำเร็จ ${Object.keys(response.updated).length} หุ้น`
        : "อัปเดตผลตอบแทนจาก Yahoo Finance เรียบร้อย");
    } catch (error) {
      byId("returns-message").textContent = error.message;
    }
  }

  function bindEvents() {
    const search = byId("stock-search");
    search.addEventListener("focus", () => byId("stock-options").classList.remove("hidden"));
    search.addEventListener("input", () => {
      byId("stock-options").classList.remove("hidden");
      renderStockOptions(search.value);
    });
    search.addEventListener("keydown", (event) => {
      if (event.key === "Escape") byId("stock-options").classList.add("hidden");
      if (event.key === "Enter") {
        const first = byId("stock-options").querySelector("button");
        if (first) { event.preventDefault(); first.click(); }
      }
    });
    document.addEventListener("click", (event) => {
      if (!event.target.closest(".search-wrap")) byId("stock-options").classList.add("hidden");
    });
    byId("monthly-money").addEventListener("input", (event) => {
      const raw = event.target.value.replace(/[^\d.]/g, "");
      const parts = raw.split(".");
      const integerPart = (parts.shift() || "").replace(/^0+(?=\d)/, "");
      const decimalPart = parts.length ? `.${parts.join("").slice(0, 2)}` : "";
      event.target.value = integerPart ? `${Number(integerPart).toLocaleString("en-US")}${decimalPart}` : decimalPart;
    });
    byId("optimizer-form").addEventListener("submit", startOptimization);
    byId("save-returns").addEventListener("click", saveReturns);
    byId("yahoo-button").addEventListener("click", updateFromYahoo);
    byId("recalculate-button").addEventListener("click", () => {
      byId("calculator").scrollIntoView({ behavior: "smooth" });
      byId("results-panel").classList.add("hidden");
    });
    byId("pdf-button").addEventListener("click", () => window.print());
    byId("csv-button").addEventListener("click", exportCsv);
    document.querySelectorAll(".result-tabs button").forEach((button) => {
      button.addEventListener("click", () => {
        state.activeYear = Number(button.dataset.year);
        renderPortfolio(state.activeYear);
      });
    });
    byId("theme-toggle").addEventListener("click", () => {
      document.body.classList.toggle("dark");
      const dark = document.body.classList.contains("dark");
      localStorage.setItem("smart-dca-dark", dark ? "1" : "0");
      byId("theme-toggle").innerHTML = dark ? "☼ <span>โหมดสว่าง</span>" : "◐ <span>โหมดมืด</span>";
    });
    if (localStorage.getItem("smart-dca-dark") === "1") {
      document.body.classList.add("dark");
      byId("theme-toggle").innerHTML = "☼ <span>โหมดสว่าง</span>";
    }
  }

  async function init() {
    bindEvents();
    try {
      const response = await request("/api/stocks/", { headers: {} });
      state.stocks = response.stocks;
      renderChips();
      renderStockOptions();
      renderReturns();
    } catch (error) {
      byId("form-error").textContent = `โหลดรายชื่อหุ้นไม่สำเร็จ: ${error.message}`;
      byId("optimize-button").disabled = true;
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
