const form = document.getElementById("uploadForm");
const fileInput = document.getElementById("audioFile");
const fileLabel = document.getElementById("fileLabel");
const modelInput = document.getElementById("model");
const languageInput = document.getElementById("language");
const startButton = document.getElementById("startButton");
const message = document.getElementById("message");
const currentTaskEl = document.getElementById("currentTask");
const tasksEl = document.getElementById("tasks");
const refreshButton = document.getElementById("refreshButton");

let polling = null;

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  fileLabel.textContent = file ? `${file.name} (${formatSize(file.size)})` : "选择录音文件";
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideMessage();
  const file = fileInput.files[0];
  if (!file) {
    showMessage("请先选择 mp3、wav 或 m4a 文件。");
    return;
  }

  const data = new FormData();
  data.append("file", file);
  data.append("model", modelInput.value);
  data.append("language", languageInput.value);

  startButton.disabled = true;
  startButton.textContent = "提交中";
  try {
    const response = await fetch("/api/transcribe", { method: "POST", body: data });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "提交失败");
    }
    fileInput.value = "";
    fileLabel.textContent = "选择录音文件";
    await loadTasks();
    startPolling();
  } catch (error) {
    showMessage(error.message);
  } finally {
    startButton.disabled = false;
    startButton.textContent = "开始转写";
  }
});

refreshButton.addEventListener("click", loadTasks);

async function loadTasks() {
  const response = await fetch("/api/tasks");
  const payload = await response.json();
  renderTasks(payload.items || []);
  const hasRunning = (payload.items || []).some((task) => task.status === "queued" || task.status === "running");
  if (hasRunning) {
    startPolling();
  } else {
    stopPolling();
  }
}

function renderTasks(tasks) {
  const current = tasks.find((task) => task.status === "queued" || task.status === "running");
  renderCurrentTask(current);

  const history = tasks.filter((task) => task.id !== (current && current.id));
  renderHistory(history);
}

function renderCurrentTask(task) {
  if (!task) {
    currentTaskEl.innerHTML = "<p class='meta'>当前没有正在运行的任务。</p>";
    return;
  }
  currentTaskEl.innerHTML = renderTaskCard(task, { showPreview: true });
}

function renderHistory(tasks) {
  if (!tasks.length) {
    tasksEl.innerHTML = "<p class='meta'>还没有最近结果。</p>";
    return;
  }

  tasksEl.innerHTML = tasks.map((task) => renderTaskCard(task, { showPreview: false })).join("");
}

function renderTaskCard(task, options) {
  const progress = Number(task.progress || 0);
  const statusText = task.status === "completed" ? "完成" : task.status === "failed" ? "失败" : task.status === "running" ? "处理中" : "等待中";
  const download = task.status === "completed" ? `<a class="download" href="/api/tasks/${task.id}/download">下载 TXT</a> <a class="download" href="/workspace?task=${task.id}">总结／分析</a>` : "";
  const retry = task.status === "failed" ? `<button class="retry" type="button" data-retry="${task.id}">重新转写</button>` : "";
  const error = task.error ? `<div class="error">${escapeHtml(task.error)}</div>` : "";
  const segment = task.total_segments ? `第 ${task.current_segment || 0} / ${task.total_segments} 段` : "";
  const preview = options.showPreview && task.preview_text ? `<div class="preview">${escapeHtml(task.preview_text)}</div>` : "";
  return `
    <article class="task">
      <div class="taskHeader">
        <div class="filename">${escapeHtml(task.filename)}</div>
        <div class="status">${statusText}</div>
      </div>
      <div class="bar"><span style="width:${Math.max(0, Math.min(100, progress))}%"></span></div>
      <div class="meta">
        <span>${escapeHtml(task.stage || "")} ${segment}</span>
        <span>${progress}%</span>
      </div>
      ${preview}
      ${error}
      <div class="actions">${download}${retry}</div>
    </article>
  `;
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-retry]");
  if (!button) return;
  hideMessage();
  button.disabled = true;
  try {
    const response = await fetch(`/api/tasks/${button.dataset.retry}/retry`, { method: "POST" });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "重新转写失败");
    }
    await loadTasks();
    startPolling();
  } catch (error) {
    showMessage(error.message);
  } finally {
    button.disabled = false;
  }
});

function startPolling() {
  if (polling) return;
  polling = window.setInterval(loadTasks, 2000);
}

function stopPolling() {
  if (!polling) return;
  window.clearInterval(polling);
  polling = null;
}

function showMessage(text) {
  message.hidden = false;
  message.textContent = text;
}

function hideMessage() {
  message.hidden = true;
  message.textContent = "";
}

function formatSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

loadTasks();
