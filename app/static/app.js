const form = document.querySelector("#job-form");
const submitButton = document.querySelector("#submit-button");
const statusTitle = document.querySelector("#status-title");
const statusMessage = document.querySelector("#status-message");
const statusPill = document.querySelector("#status-pill");
const jobIdText = document.querySelector("#job-id");
const progressFill = document.querySelector("#progress-fill");
const progressPercent = document.querySelector("#progress-percent");
const timeEstimate = document.querySelector("#time-estimate");
const imageGrid = document.querySelector("#image-grid");
const imageCount = document.querySelector("#image-count");
const subtitleList = document.querySelector("#subtitle-list");
const subtitleCount = document.querySelector("#subtitle-count");
const sceneViewer = document.querySelector("#scene-viewer");
const viewerCounter = document.querySelector("#viewer-counter");
const viewerTitle = document.querySelector("#viewer-title");
const viewerImage = document.querySelector("#viewer-image");
const viewerCaption = document.querySelector("#viewer-caption");
const viewerPrev = document.querySelector("#viewer-prev");
const viewerNext = document.querySelector("#viewer-next");
const viewerClose = document.querySelector("#viewer-close");

let pollTimer = null;
let currentScenes = [];
let activeSceneIndex = 0;
const subtitlePreviewCache = new Map();

viewerClose.addEventListener("click", closeSceneViewer);
viewerPrev.addEventListener("click", () => showScene(activeSceneIndex - 1));
viewerNext.addEventListener("click", () => showScene(activeSceneIndex + 1));
sceneViewer.addEventListener("click", (event) => {
  if (event.target === sceneViewer) {
    closeSceneViewer();
  }
});

document.addEventListener("keydown", (event) => {
  if (!sceneViewer.classList.contains("is-open")) {
    return;
  }

  if (event.key === "Escape") {
    closeSceneViewer();
  }
  if (event.key === "ArrowLeft") {
    showScene(activeSceneIndex - 1);
  }
  if (event.key === "ArrowRight") {
    showScene(activeSceneIndex + 1);
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearPoll();

  const data = new FormData(form);
  const languages = data.getAll("subtitle_languages");
  const payload = {
    url: data.get("url"),
    subtitle_languages: languages.length ? languages : ["ko"],
  };

  setWorking(true);
  setStatus("queued", "작업을 등록하는 중입니다.", "");
  clearResults();

  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    const job = await response.json();
    jobIdText.textContent = `Job ID: ${job.job_id}`;
    pollJob(job.job_id);
  } catch (error) {
    setWorking(false);
    setStatus("failed", "작업 등록에 실패했습니다.", String(error));
  }
});

async function pollJob(jobId) {
  try {
    const response = await fetch(`/api/jobs/${jobId}`);
    if (!response.ok) {
      throw new Error(await response.text());
    }
    const job = await response.json();
    renderJob(job);

    if (job.status === "completed" || job.status === "failed") {
      setWorking(false);
      clearPoll();
      return;
    }
    pollTimer = window.setTimeout(() => pollJob(jobId), 1600);
  } catch (error) {
    setWorking(false);
    setStatus("failed", "상태 확인에 실패했습니다.", String(error));
    clearPoll();
  }
}

function renderJob(job) {
  setStatus(job.status, job.message, job.error || "");
  setProgress(job.progress_percent || 0, job.elapsed_seconds || 0, job.eta_seconds);
  renderScenes(job.scenes || [], job.image_urls || []);
  renderSubtitles(job.subtitles || []);
}

function setStatus(status, message, detail) {
  statusTitle.textContent = statusLabel(status);
  statusMessage.textContent = detail ? `${message} ${detail}` : message;
  statusPill.textContent = status;
  statusPill.className = `status-pill ${status}`;
}

function setProgress(percent, elapsedSeconds, etaSeconds) {
  const clampedPercent = Math.min(Math.max(Number(percent) || 0, 0), 100);
  progressFill.style.width = `${clampedPercent}%`;
  progressPercent.textContent = `${clampedPercent}%`;

  const elapsedText = `경과 ${formatDuration(elapsedSeconds)}`;
  const etaText = etaSeconds === null || etaSeconds === undefined
    ? "예상 시간 계산 전"
    : `예상 남은 시간 ${formatDuration(etaSeconds)}`;
  timeEstimate.textContent = `${elapsedText} · ${etaText}`;
}

function formatDuration(totalSeconds) {
  const seconds = Math.max(0, Math.floor(Number(totalSeconds) || 0));
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes <= 0) {
    return `${remainingSeconds}초`;
  }
  return `${minutes}분 ${remainingSeconds}초`;
}

function statusLabel(status) {
  const labels = {
    queued: "대기 중",
    running: "분석 중",
    completed: "완료",
    failed: "실패",
  };
  return labels[status] || status;
}

function renderScenes(scenes, fallbackUrls) {
  const normalizedScenes = scenes.length
    ? scenes
    : fallbackUrls.map((url) => ({
        image_url: url,
        timestamp_seconds: null,
        captions_by_language: {},
      }));

  currentScenes = normalizedScenes;
  if (sceneViewer.classList.contains("is-open")) {
    activeSceneIndex = Math.min(activeSceneIndex, Math.max(currentScenes.length - 1, 0));
    updateSceneViewer();
  }

  imageCount.textContent = String(normalizedScenes.length);
  imageGrid.innerHTML = "";
  if (!normalizedScenes.length) {
    imageGrid.innerHTML = `<p class="empty-state">아직 저장된 이미지가 없습니다.</p>`;
    return;
  }

  for (const scene of normalizedScenes) {
    const card = document.createElement("article");
    card.className = "image-card";

    const link = document.createElement("a");
    link.href = scene.image_url;
    link.setAttribute("aria-label", "큰 화면으로 캡처 이미지 보기");
    link.addEventListener("click", (event) => {
      event.preventDefault();
      openSceneViewer(currentScenes.indexOf(scene));
    });
    const image = document.createElement("img");
    image.src = scene.image_url;
    image.alt = "Captured scene";
    link.append(image);

    const label = document.createElement("span");
    const fileName = scene.image_url.split("/").pop();
    const timeLabel = scene.timestamp_seconds === null || scene.timestamp_seconds === undefined
      ? ""
      : `${formatDuration(scene.timestamp_seconds)} · `;
    label.textContent = `${timeLabel}${fileName}`;

    card.append(link, label, renderSceneCaptions(scene.captions_by_language || {}));
    imageGrid.append(card);
  }
}

function openSceneViewer(index) {
  if (!currentScenes.length) {
    return;
  }
  activeSceneIndex = Math.min(Math.max(index, 0), currentScenes.length - 1);
  sceneViewer.classList.add("is-open");
  sceneViewer.setAttribute("aria-hidden", "false");
  document.body.classList.add("viewer-open");
  updateSceneViewer();
  viewerClose.focus();
}

function closeSceneViewer() {
  sceneViewer.classList.remove("is-open");
  sceneViewer.setAttribute("aria-hidden", "true");
  document.body.classList.remove("viewer-open");
}

function showScene(index) {
  if (!currentScenes.length) {
    return;
  }
  activeSceneIndex = (index + currentScenes.length) % currentScenes.length;
  updateSceneViewer();
}

function updateSceneViewer() {
  if (!currentScenes.length) {
    closeSceneViewer();
    return;
  }

  const scene = currentScenes[activeSceneIndex];
  const fileName = scene.image_url.split("/").pop();
  const timeLabel = scene.timestamp_seconds === null || scene.timestamp_seconds === undefined
    ? ""
    : `${formatDuration(scene.timestamp_seconds)} · `;

  viewerCounter.textContent = `${activeSceneIndex + 1} / ${currentScenes.length}`;
  viewerTitle.textContent = `${timeLabel}${fileName}`;
  viewerImage.src = scene.image_url;
  viewerCaption.innerHTML = "";
  viewerCaption.append(renderViewerCaptions(scene.captions_by_language || {}));
}

function renderViewerCaptions(captionsByLanguage) {
  const wrapper = document.createElement("div");
  wrapper.className = "viewer-captions";
  const entries = Object.entries(captionsByLanguage).filter(([, text]) => text);

  if (!entries.length) {
    const empty = document.createElement("p");
    empty.className = "viewer-caption-line empty";
    empty.textContent = "이 순간에 겹치는 자막이 없습니다.";
    wrapper.append(empty);
    return wrapper;
  }

  for (const [language, text] of entries) {
    const line = document.createElement("p");
    line.className = "viewer-caption-line";
    const badge = document.createElement("strong");
    badge.textContent = language;
    const body = document.createElement("span");
    body.textContent = text;
    line.append(badge, body);
    wrapper.append(line);
  }
  return wrapper;
}

function renderSceneCaptions(captionsByLanguage) {
  const list = document.createElement("div");
  list.className = "scene-captions";

  const entries = Object.entries(captionsByLanguage);
  if (!entries.length || entries.every(([, text]) => !text)) {
    const empty = document.createElement("p");
    empty.className = "scene-caption empty";
    empty.textContent = "이 순간에 겹치는 자막이 없습니다.";
    list.append(empty);
    return list;
  }

  for (const [language, text] of entries) {
    if (!text) {
      continue;
    }
    const line = document.createElement("p");
    line.className = "scene-caption";
    const badge = document.createElement("strong");
    badge.textContent = language;
    const body = document.createElement("span");
    body.textContent = text;
    line.append(badge, body);
    list.append(line);
  }

  return list;
}

function renderSubtitles(subtitles) {
  subtitleCount.textContent = String(subtitles.length);
  subtitleList.innerHTML = "";
  if (!subtitles.length) {
    subtitleList.innerHTML = `<p class="empty-state">아직 저장된 자막이 없습니다.</p>`;
    return;
  }

  for (const subtitle of subtitles) {
    const item = document.createElement("div");
    item.className = subtitle.error ? "subtitle-item error" : "subtitle-item";

    if (subtitle.url) {
      const link = document.createElement("a");
      link.href = subtitle.url;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = `${subtitle.language} Markdown 열기`;
      const preview = document.createElement("pre");
      preview.className = "subtitle-preview";
      preview.textContent = "자막을 불러오는 중입니다...";
      item.append(link, preview);
      loadSubtitlePreview(subtitle.url, preview);
    } else {
      item.textContent = `${subtitle.language}: ${subtitle.error}`;
    }

    subtitleList.append(item);
  }
}

async function loadSubtitlePreview(url, previewElement) {
  try {
    if (subtitlePreviewCache.has(url)) {
      previewElement.textContent = subtitlePreviewCache.get(url);
      return;
    }

    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const text = await response.text();
    subtitlePreviewCache.set(url, text);
    previewElement.textContent = text;
  } catch (error) {
    previewElement.textContent = `자막을 불러오지 못했습니다. ${String(error)}`;
  }
}

function clearResults() {
  setProgress(0, 0, null);
  subtitlePreviewCache.clear();
  renderScenes([], []);
  renderSubtitles([]);
}

function setWorking(isWorking) {
  submitButton.disabled = isWorking;
  submitButton.textContent = isWorking ? "분석 중..." : "분석 시작";
}

function clearPoll() {
  if (pollTimer) {
    window.clearTimeout(pollTimer);
    pollTimer = null;
  }
}
