// 会议页的交互：图例按钮控制列表显示哪些类别；搜索；点方格跳到对应论文。
// 页面内容本身是静态 HTML，没有这个脚本也能完整阅读（此时显示全部条目）。
(function () {
  const entries = Array.from(document.querySelectorAll(".entry"));
  const toggles = Array.from(document.querySelectorAll(".legend button"));
  const search = document.querySelector(".search");
  const count = document.querySelector(".count");
  const nothing = document.querySelector(".nothing");
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
      const visible = on.has(e.dataset.status) && (!q || e.dataset.search.includes(q));
      e.hidden = !visible;
      if (visible) n++;
    }
    count.textContent = count.dataset.template.replace("{n}", n);
    nothing.hidden = n !== 0;
  }

  for (const t of toggles) {
    t.addEventListener("click", () => {
      t.setAttribute("aria-pressed", String(t.getAttribute("aria-pressed") !== "true"));
      apply();
    });
  }
  search.addEventListener("input", apply);

  // 点方格（或打开带 #p-… 的链接）时，确保那篇论文所在的类别是显示状态，再滚过去
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
    target.scrollIntoView({ block: "start" });
  }
  window.addEventListener("hashchange", reveal);

  apply();
  reveal();
})();
