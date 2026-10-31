const state = {
  submitting: false,
  documents: [],
  doc: null,
  config: {},
  jobs: [],
  result: null,
  pending: null,
  purpose: "summary",
  length: "standard",
  editing: false,
  draft: "",
  editDocument: false,
  source: null,
  sourceOpen: false,
  highlight: null,
  epoch: 0,
  poll: null,
};
const app = document.getElementById("app");
const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const formatDate = (value) =>
  new Date(value).toLocaleString("zh-CN", { hour12: false });
const nameOf = (p) => (p === "summary" ? "要点总结" : "结构分析");
const busy = () =>
  state.pending && ["queued", "running"].includes(state.pending.status);
const time = (s) =>
  s === null || s === undefined
    ? ""
    : Math.floor(s / 60)
        .toString()
        .padStart(2, "0") +
      ":" +
      Math.floor(s % 60)
        .toString()
        .padStart(2, "0");
function message(text = "") {
  document.getElementById("message").textContent = text;
}
function toast(text) {
  const el = document.getElementById("toast");
  el.textContent = text;
  el.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (el.hidden = true), 3500);
}
async function api(path, method = "GET", body) {
  const response = await fetch("/api/workspace" + path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "输入格式有误，请检查后重试。",
    );
  return data;
}
function metadata() {
  const d = state.doc;
  return `<div class="meta-row"><span class="tag">${d.has_audio ? "录音文稿" : "导入文字"}</span><span>文稿 v${d.version}</span><span>${d.segments.length} 个段落</span><span>${d.segments.reduce((n, s) => n + s.text.length, 0)} 字</span></div>`;
}
function settings() {
  return `<div class="config"><div class="purpose-tabs" role="group" aria-label="生成用途">${["summary", "analysis"].map((p) => `<button data-purpose="${p}" class="${state.purpose === p ? "active" : ""}" aria-pressed="${state.purpose === p}">${nameOf(p)}</button>`).join("")}</div><p class="hint" style="margin-top:12px">${state.purpose === "summary" ? "提炼核心观点，保留重要结论和原文依据。" : "拆解问题、主张、例证与回应，理解表达结构。"}</p><div class="settings-grid"><label class="field">输出篇幅<select id="length" ${busy() ? "disabled" : ""}><option value="standard" ${state.length === "standard" ? "selected" : ""}>标准 · 保留关键说明</option><option value="brief" ${state.length === "brief" ? "selected" : ""}>简短 · 快速浏览</option></select></label><div class="field"><span>输出语言</span><div class="static-field">跟随原文<span>自动</span></div></div></div><div class="connection-inline"><div><strong>${esc(state.config.name || "尚未配置模型")}</strong><small>${esc(state.config.model || "填写服务地址和模型名")}</small></div><button class="small" data-action="connection">配置</button></div><p class="send-note">${state.config.configured ? "生成时文稿将发送至 " + esc(state.config.endpoint) + "。" : "请先配置模型服务。"} 密钥仅本次运行留存。</p><div class="generate-row"><span class="hint">依据当前文稿 v${state.doc.version} · 最多 32,000 字符</span>${busy() ? '<span class="hint">正在生成…</span>' : `<button data-action="generate" class="primary" ${state.editing ? "disabled" : ""}>${state.result ? "重新生成" : "生成" + nameOf(state.purpose)}</button>`}</div></div>`;
}
function sourcePanel() {
  const snapshot = state.source || state.doc;
  return `<details class="reader-source" ${state.sourceOpen ? "open" : ""}><summary>查看原始文稿与引用 · v${snapshot.version}</summary>${state.doc.has_audio ? `<audio id="audio" class="audio-player" controls preload="none" src="/api/workspace/documents/${state.doc.id}/audio"></audio>` : ""}<div class="source-scroll">${snapshot.segments.map((s) => `<article id="source-${esc(s.id)}" class="segment ${state.highlight === s.id ? "highlight" : ""}"><span class="timestamp">${time(s.start) || esc(s.id)}</span><p>${esc(s.text)}</p></article>`).join("")}</div></details>`;
}
function resultText() {
  return state.result?.markdown || "";
}
function editedBody(text, snapshot) {
  const known = new Set(snapshot.segments.map((s) => s.id));
  return text
    .split(/(\bS\d+\b)/g)
    .map((part) =>
      known.has(part)
        ? `<button class="citation" data-cite="${esc(part)}">${esc(part)}</button>`
        : esc(part),
    )
    .join("");
}
function resultPanel() {
  const r = state.result;
  let content = "";
  if (busy())
    content =
      '<div class="processing" role="status"><h3>正在生成' +
      nameOf(state.pending.purpose) +
      '</h3><div class="progress-track"><span></span></div><p>可继续查看原文；取消后上游模型仍可能继续处理或计费。</p><button data-action="cancel" class="small">取消生成</button></div>';
  else if (state.pending?.status === "failed")
    content = `<div class="error-box" role="alert">${esc(state.pending.error)}<p class="hint">调整设置后可重新生成，原文和以前的成果均已保留。</p></div>`;
  else if (state.pending?.status === "cancelled")
    content =
      '<p class="hint">已停止等待，已有成果保留。上游服务可能仍在处理。</p>';
  if (!r)
    return (
      content +
      '<div class="empty"><div class="empty-mark">≡</div><strong>重点从这里开始</strong><p>选择用途和模型，生成后可逐条查看原文依据。</p></div>'
    );
  if (r.version !== state.doc.version)
    content += `<div class="warning">文稿已更新；此结果依据 v${r.version}。引用定位将展示当时的原文。</div>`;
  if (
    r.purpose !== state.purpose ||
    r.length !== state.length ||
    r.model !== state.config.model
  )
    content +=
      '<p class="hint">生成设置已变化，下方保留原有成果；重新生成后更新。</p>';
  content += `<div class="result-heading"><div><span class="eyebrow">生成结果</span><h2>${nameOf(r.purpose)}</h2></div><span class="tag">已保存</span></div><p class="result-meta">文稿 v${r.version} · ${esc(r.model)} · ${r.length === "brief" ? "简短" : "标准"} · ${esc(formatDate(r.created_at))}</p>`;
  if (state.editing)
    return (
      content +
      `<label class="field">编辑结果<textarea id="result-editor" rows="13">${esc(state.draft)}</textarea></label><div class="edit-actions"><button data-action="save-result" class="primary">保存修改</button><button data-action="discard-edit">取消</button></div>`
    );
  if (r.edited_text !== null)
    content += `<div class="result-text">${editedBody(r.edited_text, r.snapshot)}</div><button data-action="result-source" class="small">查看此成果依据的原文</button><p class="hint">这是手动编辑的版本，请重新核对引用。</p>`;
  else
    content += `<p class="lead"><span class="lead-label">核心概述</span>${esc(r.result.lead)}</p>${r.result.sections.map((s) => `<section class="result-block"><h3>${esc(s.title)}</h3><p>${esc(s.body)} ${s.sources.map((id) => `<button class="citation" data-cite="${esc(id)}">原文 ${esc(id)}</button>`).join("")}</p></section>`).join("")}<div class="note">${esc(r.result.note || "引用仅定位原文，内容是否支持结论仍需人工核对。")}</div>`;
  return (
    content +
    `<div class="result-foot"><button data-action="edit-result" ${busy() ? "disabled" : ""}>编辑结果</button><button data-action="copy">复制</button><a class="download" style="margin-left:auto" href="/api/workspace/generations/${r.id}/download">导出 Markdown</a></div>`
  );
}
function render() {
  const oldAudio = document.getElementById("audio");
  const wasPlaying = oldAudio && !oldAudio.paused;
  const previousDocument = app.dataset.documentId;
  const sourceScroll = document.querySelector(".source-scroll")?.scrollTop || 0;
  const d = state.doc;
  app.innerHTML = `<div class="page-title"><div><span class="eyebrow">我的资料 / 文稿工作室</span><h1>${esc(d?.title || "让每一次表达，都有迹可循")}</h1><p>留下核心观点，把录音与文稿变成可使用的资料。</p></div><div class="title-actions"><button data-action="import">导入文字</button></div></div><label class="field library-picker">我的文稿<select id="document-picker" ${state.editing ? "disabled" : ""}><option value="">选择文稿</option>${state.documents.map((x) => `<option value="${x.id}" ${d?.id === x.id ? "selected" : ""}>${esc(x.title)}</option>`).join("")}</select></label>${
    !d
      ? '<section class="panel library-empty"><h2>从一份文稿开始</h2><p class="hint">导入文字，或在录音转写完成后点击“总结／分析”。文稿保存在本机。</p><button data-action="import" class="primary">导入第一份文稿</button></section>'
      : `<div class="reader-layout"><aside class="reader-nav"><div class="reader-nav-intro"><span class="eyebrow">当前资料</span><h3>${esc(d.title)}</h3><span class="hint">文稿 v${d.version} · ${d.segments.length} 个段落</span></div>${["summary", "analysis"].map((p) => `<button class="nav-item ${state.purpose === p ? "active" : ""}" data-purpose="${p}"><span class="nav-glyph" aria-hidden="true">≡</span>${nameOf(p)}</button>`).join("")}</aside><section class="panel reader-page"><div class="reader-toolbar">${metadata()}<button data-action="edit-document" class="small" ${state.editing ? "disabled" : ""}>校对文稿</button></div><details id="reader-settings" ${!state.result || busy() || state.pending?.status === "failed" ? "open" : ""}><summary>生成设置</summary>${settings()}</details>${
          state.jobs.filter((j) => j.status === "completed").length > 1
            ? `<label class="field history">历史成果<select id="history">${state.jobs
                .filter((j) => j.status === "completed")
                .map(
                  (j) =>
                    `<option value="${j.id}" ${j.id === state.result?.id ? "selected" : ""}>${nameOf(j.purpose)} · v${j.version} · ${esc(j.model)} · ${esc(formatDate(j.created_at))}</option>`,
                )
                .join("")}</select></label>`
            : ""
        }${resultPanel()}${sourcePanel()}</section></div>`
  }`;
  app.dataset.documentId = d?.id || "";
  const replacement = document.getElementById("audio");
  if (
    oldAudio &&
    replacement &&
    oldAudio.getAttribute("src") === replacement.getAttribute("src")
  ) {
    replacement.replaceWith(oldAudio);
    if (wasPlaying) oldAudio.play().catch(() => {});
  } else if (oldAudio) oldAudio.pause();
  if (previousDocument === d?.id) {
    const scroll = document.querySelector(".source-scroll");
    if (scroll) scroll.scrollTop = sourceScroll;
  }
}
async function loadDocument(id) {
  clearTimeout(state.poll);
  const epoch = ++state.epoch;
  const [doc, jobs] = await Promise.all([
    api("/documents/" + id),
    api("/generations?document_id=" + encodeURIComponent(id)),
  ]);
  if (epoch !== state.epoch) return;
  Object.assign(state, {
    doc,
    jobs: jobs.items,
    result: jobs.items.find((j) => j.status === "completed") || null,
    pending: jobs.items[0] || null,
    editing: false,
    source: null,
    sourceOpen: false,
    highlight: null,
  });
  render();
  if (busy()) poll(epoch);
}
async function refreshDocuments() {
  state.documents = (await api("/documents")).items;
}
function poll(epoch) {
  state.poll = setTimeout(async () => {
    try {
      const job = await api("/generations/" + state.pending.id);
      if (epoch !== state.epoch) return;
      const previousStatus = state.pending?.status;
      state.pending = job;
      state.jobs = state.jobs.filter((j) => j.id !== job.id);
      state.jobs.unshift(job);
      if (job.status === "completed") state.result = job;
      if (previousStatus !== job.status || job.status === "completed") render();
      if (busy()) poll(epoch);
    } catch (e) {
      if (epoch === state.epoch) {
        message(e.message + "；稍后会重试读取状态。");
        poll(epoch);
      }
    }
  }, 1000);
}
function documentModal(edit) {
  state.editDocument = edit;
  document.getElementById("document-modal-title").textContent = edit
    ? "校对文稿"
    : "导入文字";
  document.getElementById("document-title").value = edit ? state.doc.title : "";
  document.getElementById("document-text").value = edit
    ? state.doc.segments.map((s) => s.text).join("\n\n")
    : "";
  document.querySelector("#document-dialog .form-error").textContent = "";
  document.getElementById("document-dialog").showModal();
}
document.addEventListener("click", async (e) => {
  const b = e.target.closest("button");
  if (!b || b.disabled) return;
  try {
    message();
    if (b.dataset.close) {
      document.getElementById(b.dataset.close).close();
      return;
    }
    if (b.dataset.purpose) {
      if (busy() || state.editing) {
        toast("请先完成当前生成或编辑。");
        return;
      }
      state.purpose = b.dataset.purpose;
      render();
      document.getElementById("reader-settings").open = true;
      return;
    }
    if (b.dataset.cite) {
      state.source = state.result.snapshot;
      state.sourceOpen = true;
      state.highlight = b.dataset.cite;
      render();
      document
        .getElementById("source-" + state.highlight)
        ?.scrollIntoView({ block: "center", behavior: "smooth" });
      const segment = state.source.segments.find(
        (s) => s.id === state.highlight,
      );
      const audio = document.getElementById("audio");
      if (audio && segment?.start !== null && segment?.start !== undefined) {
        audio.currentTime = segment.start;
        audio.play().catch(() => toast("可点击音频播放按钮回听。"));
      }
      return;
    }
    const action = b.dataset.action;
    if (action === "connection") {
      if (busy() || state.editing) {
        toast("请先完成当前操作。");
        return;
      }
      const f = document.getElementById("connection-form");
      for (const k of ["name", "endpoint", "model"])
        f.elements[k].value = state.config[k] || "";
      f.elements.key.value = "";
      document.querySelector("#connection-dialog .form-error").textContent = "";
      document.getElementById("connection-dialog").showModal();
    }
    if (action === "import" || action === "edit-document") {
      if (state.editing || busy()) {
        toast("请先完成或取消当前操作。");
        return;
      }
      documentModal(action === "edit-document");
    }
    if (action === "generate") {
      if (busy() || state.editing || state.submitting) return;
      state.submitting = true;
      b.disabled = true;
      const epoch = state.epoch;
      try {
        const job = await api("/generations", "POST", {
          document_id: state.doc.id,
          version: state.doc.version,
          purpose: state.purpose,
          length: state.length,
        });
        if (epoch !== state.epoch) return;
        state.pending = job;
        render();
        poll(epoch);
      } finally {
        state.submitting = false;
        b.disabled = false;
      }
    }
    if (action === "cancel") {
      const epoch = state.epoch;
      const cancelled = await api(
        "/generations/" + state.pending.id + "/cancel",
        "POST",
      );
      if (epoch !== state.epoch) return;
      state.pending = cancelled;
      render();
    }
    if (action === "result-source") {
      state.source = state.result.snapshot;
      state.sourceOpen = true;
      render();
    }
    if (action === "edit-result") {
      state.draft = resultText();
      state.editing = true;
      render();
      document.getElementById("result-editor").focus();
    }
    if (action === "discard-edit") {
      state.editing = false;
      render();
    }
    if (action === "save-result") {
      if (!state.draft.trim()) {
        toast("结果不能为空。");
        return;
      }
      state.result = await api("/generations/" + state.result.id, "PUT", {
        text: state.draft,
        revision: state.result.edit_revision,
      });
      state.jobs = state.jobs.map((j) =>
        j.id === state.result.id ? state.result : j,
      );
      state.editing = false;
      render();
      toast("修改已保存到本机。");
    }
    if (action === "copy") {
      await navigator.clipboard.writeText(resultText());
      toast("已复制。");
    }
  } catch (error) {
    message(error.message);
  }
});
document.addEventListener("input", (e) => {
  if (e.target.id === "result-editor") state.draft = e.target.value;
});
document.addEventListener("change", async (e) => {
  try {
    if (e.target.id === "document-picker") {
      if (e.target.value) await loadDocument(e.target.value);
    }
    if (e.target.id === "length") state.length = e.target.value;
    if (e.target.id === "history") {
      if (state.editing) {
        e.target.value = state.result.id;
        toast("请先保存或取消修改。");
        return;
      }
      state.result = state.jobs.find((j) => j.id === e.target.value);
      state.source = null;
      state.sourceOpen = false;
      render();
    }
  } catch (error) {
    message(error.message);
  }
});
document
  .getElementById("connection-form")
  .addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target,
      b = f.querySelector('[type="submit"]');
    b.disabled = true;
    try {
      state.config = await api("/connection", "PUT", {
        name: f.elements.name.value,
        endpoint: f.elements.endpoint.value,
        model: f.elements.model.value,
        key: f.elements.key.value || null,
      });
      f.elements.key.value = "";
      document.getElementById("connection-dialog").close();
      render();
      toast("连接设置已保存，生成时调用该服务。");
    } catch (error) {
      document.querySelector("#connection-dialog .form-error").textContent =
        error.message;
    } finally {
      b.disabled = false;
    }
  });
document
  .getElementById("document-form")
  .addEventListener("submit", async (e) => {
    e.preventDefault();
    const b = e.target.querySelector('[type="submit"]');
    b.disabled = true;
    try {
      const input = {
        title: document.getElementById("document-title").value,
        text: document.getElementById("document-text").value,
      };
      const doc = state.editDocument
        ? await api("/documents/" + state.doc.id, "PUT", {
            ...input,
            version: state.doc.version,
          })
        : await api("/documents", "POST", input);
      document.getElementById("document-dialog").close();
      await refreshDocuments();
      await loadDocument(doc.id);
      toast("文稿已保存。");
    } catch (error) {
      document.querySelector("#document-dialog .form-error").textContent =
        error.message;
    } finally {
      b.disabled = false;
    }
  });
async function initialize() {
  try {
    [state.config] = await Promise.all([
      api("/connection"),
      refreshDocuments(),
    ]);
    const task = new URLSearchParams(location.search).get("task");
    if (task) {
      const doc = await api("/from-task/" + encodeURIComponent(task), "POST");
      await refreshDocuments();
      await loadDocument(doc.id);
    } else if (state.documents.length)
      await loadDocument(state.documents[0].id);
    else render();
  } catch (error) {
    render();
    message(error.message);
  }
}
document.addEventListener(
  "toggle",
  (event) => {
    if (event.target.isConnected && event.target.matches?.(".reader-source"))
      state.sourceOpen = event.target.open;
  },
  true,
);
initialize();
