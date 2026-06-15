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

let pollTimer = null;

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
    link.target = "_blank";
    link.rel = "noreferrer";
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
      item.append(link);
    } else {
      item.textContent = `${subtitle.language}: ${subtitle.error}`;
    }

    subtitleList.append(item);
  }
}

function clearResults() {
  setProgress(0, 0, null);
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
