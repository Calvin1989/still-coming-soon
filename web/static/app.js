// 会议页的交互：图例按钮控制列表显示哪些类别；搜索；全部展开/收起；点方格跳到对应论文。
// 页面内容本身是静态 HTML，没有这个脚本也能完整阅读（此时显示全部条目，每条都能点开）。
(function () {
  const entries = Array.from(document.querySelectorAll(".entry"));
  const groups = Array.from(document.querySelectorAll(".group"));
  const toggles = Array.from(document.querySelectorAll(".legend button"));
  const search = document.querySelector(".search");
  const count = document.querySelector(".count");
  const nothing = document.querySelector(".nothing");
  const expand = document.querySelector(".expand");
  if (!entries.length || !toggles.length) return;

  function shown() {
    const on = new Set();
    for (const t of toggles) {
      if (t.getAttribute("aria-pressed") === "true") t.dataset.statuses.split(" ").forEach((s) => on.add(s));
    }
    return on;
  }

  function apply() {
    const on = shown();
    const q = search.value.trim().toLowerCase();
    let n = 0;
    for (const e of entries) {
      // data-extra：补充类别（已开源但清单没勾完），按下对应按钮时也显示
      const match = on.has(e.dataset.status) || (e.dataset.extra && on.has(e.dataset.extra));
      const visible = match && (!q || e.dataset.search.includes(q));
      e.hidden = !visible;
      if (visible) n++;
    }
    // 每组的数量跟着筛选变；一篇都不剩的组整个隐藏
    for (const g of groups) {
      const k = g.querySelectorAll(".entry:not([hidden])").length;
      g.hidden = k === 0;
      g.querySelector(".group-head b").textContent = k;
    }
    count.textContent = count.dataset.template.replace("{n}", n);
    nothing.hidden = n !== 0;
    syncExpand();
  }

  // "全部展开 / 全部收起"只作用于当前显示的条目
  function visibleDetails() {
    return entries.filter((e) => !e.hidden).map((e) => e.querySelector("details")).filter(Boolean);
  }
  function syncExpand() {
    if (!expand) return;
    const ds = visibleDetails();
    const allOpen = ds.length > 0 && ds.every((d) => d.open);
    expand.textContent = allOpen ? expand.dataset.collapse : expand.dataset.expand;
    expand.hidden = ds.length === 0;
  }
  if (expand) {
    expand.addEventListener("click", () => {
      const ds = visibleDetails();
      const open = !ds.every((d) => d.open);
      ds.forEach((d) => (d.open = open));
      syncExpand();
    });
    for (const e of entries) e.querySelector("details")?.addEventListener("toggle", syncExpand);
  }

  for (const t of toggles) {
    t.addEventListener("click", () => {
      t.setAttribute("aria-pressed", String(t.getAttribute("aria-pressed") !== "true"));
      apply();
    });
  }
  search.addEventListener("input", apply);

  // 点方格（或打开带 #p-… 的链接）时，确保那篇论文所在的类别是显示状态，展开它，再滚过去
  function reveal() {
    const target = location.hash && document.getElementById(location.hash.slice(1));
    if (!target || !target.classList.contains("entry")) return;
    if (target.hidden) {
      search.value = "";
      for (const t of toggles) {
        if (t.dataset.statuses.split(" ").includes(target.dataset.status)) t.setAttribute("aria-pressed", "true");
      }
      apply();
    }
    const d = target.querySelector("details");
    if (d) d.open = true;
    target.scrollIntoView({ block: "start" });
  }
  window.addEventListener("hashchange", reveal);

  apply();
  reveal();
})();
