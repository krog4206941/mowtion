const statusEl = document.getElementById("status");
const buttons = () => Array.from(document.querySelectorAll("button"));

let project = null;
let busy = false;

function setStatus(text, isError) {
  statusEl.textContent = text;
  statusEl.className = isError ? "status error" : "status";
}

function setBusy(on) {
  busy = on;
  buttons().forEach((button) => {
    button.disabled = on;
  });
}

async function poll(jobId) {
  while (true) {
    const response = await fetch("/api/job/" + jobId);
    const job = await response.json();
    if (!response.ok) throw new Error(job.error || "That step failed.");
    const pct = Math.round((job.progress || 0) * 100);
    setStatus((job.message || "Working...") + " " + pct + "%");
    if (job.status === "done") return job.result;
    if (job.status === "error") throw new Error(job.error || "That step failed.");
    await new Promise((resolve) => setTimeout(resolve, 800));
  }
}

async function startJob(url, options) {
  setBusy(true);
  setStatus("Starting...");
  try {
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "That step failed.");
    return await poll(data.job);
  } finally {
    setBusy(false);
  }
}

function showProject(next) {
  project = next;
  const transcript = document.getElementById("transcript");
  transcript.textContent = next.transcript || "No words were found.";
  const ideas = document.getElementById("ideas");
  ideas.innerHTML = "";
  (next.suggestions || []).forEach((idea) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "idea";
    button.innerHTML = "<strong></strong><small></small>";
    button.querySelector("strong").textContent = idea.label;
    button.querySelector("small").textContent = idea.preview || "";
    button.addEventListener("click", () => {
      document.getElementById("start").value = idea.start_text;
      document.getElementById("end").value = idea.end_text;
      setStatus("Using " + idea.label + ". You can still change the times.");
    });
    ideas.appendChild(button);
  });
  const headline = document.getElementById("headline");
  const source = document.getElementById("source");
  const date = document.getElementById("date");
  if (!headline.value && next.title) headline.value = next.title;
  if (!source.value && next.channel) source.value = next.channel;
  if (!date.value && next.date_label) date.value = next.date_label;
  if (next.clip_start != null) {
    document.getElementById("start").value = document.getElementById("start").value || "";
  }
}

function renderResults(view) {
  const box = document.getElementById("results");
  box.innerHTML = "";
  const outputs = view.outputs || [];
  if (!outputs.length) return;
  const wrap = document.createElement("div");
  wrap.className = "result";
  outputs.forEach((name) => {
    const src = "/api/media/" + view.id + "/" + name;
    const video = document.createElement("video");
    video.controls = true;
    video.src = src;
    wrap.appendChild(video);
    const link = document.createElement("a");
    link.href = src;
    link.download = name;
    link.textContent = name === "output_vertical.mp4" ? "Save the tall video" : "Save the video";
    wrap.appendChild(link);
  });
  box.appendChild(wrap);
}

document.getElementById("url-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const url = document.getElementById("url").value.trim();
  if (!url) {
    setStatus("Paste a link first.", true);
    return;
  }
  try {
    const result = await startJob("/api/import-url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    showProject(result);
    setStatus("Words are ready. Pick a start and an end, then make the video.");
  } catch (error) {
    setStatus(error.message, true);
  }
});

document.getElementById("file-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = document.getElementById("file").files[0];
  if (!file) {
    setStatus("Choose a file first.", true);
    return;
  }
  const body = new FormData();
  body.append("file", file);
  try {
    const result = await startJob("/api/import-file", { method: "POST", body });
    showProject(result);
    setStatus("Words are ready. Pick a start and an end, then make the video.");
  } catch (error) {
    setStatus(error.message, true);
  }
});

document.getElementById("make").addEventListener("click", async () => {
  if (!project) {
    setStatus("Get a video first.", true);
    return;
  }
  const music = document.querySelector("input[name=music]:checked").value === "on";
  const body = {
    project: project.id,
    start: document.getElementById("start").value,
    end: document.getElementById("end").value,
    hook1: document.getElementById("hook1").value,
    hook2: document.getElementById("hook2").value,
    headline: document.getElementById("headline").value,
    subtitle: document.getElementById("subtitle").value,
    source: document.getElementById("source").value,
    date: document.getElementById("date").value,
    end1: document.getElementById("end1").value,
    end2: document.getElementById("end2").value,
    accents: document.getElementById("accents").value,
    music,
    vertical: document.getElementById("vertical").checked,
    audio: document.getElementById("use-voice").checked ? "voice" : "clip",
  };
  try {
    const result = await startJob("/api/render", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    showProject(result);
    renderResults(result);
    setStatus("Your video is ready. Press Save the video.");
    document.getElementById("results").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    setStatus(error.message, true);
  }
});

document.getElementById("speak").addEventListener("click", async () => {
  const choice = document.querySelector("input[name=engine]:checked").value;
  const body = {
    text: document.getElementById("script").value,
    project: project ? project.id : "",
    engine: choice === "joe" ? "joe" : "kokoro",
    voice: choice === "female" ? "female" : "male",
  };
  try {
    const result = await startJob("/api/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!project) project = { id: result.id };
    else Object.assign(project, result);
    const box = document.getElementById("voice-box");
    box.innerHTML = "";
    const audio = document.createElement("audio");
    audio.controls = true;
    audio.src = "/api/media/" + result.id + "/voice.wav?t=" + Date.now();
    box.appendChild(audio);
    if (result.voice_transcript) {
      const pre = document.createElement("pre");
      pre.className = "transcript";
      pre.textContent = result.voice_transcript;
      box.appendChild(pre);
    }
    document.getElementById("use-voice").checked = true;
    setStatus("Voice is ready. In step 3, leave the box checked if you want this voice in the video.");
  } catch (error) {
    setStatus(error.message, true);
  }
});

function todayText() {
  return new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });
}

function fillPrompt(body) {
  const transcript = project && project.transcript ? project.transcript : "(No transcript yet. Paste the words here.)";
  const date = project && project.upload_date ? project.upload_date : "unknown. Treat the footage as old. Do not say BREAKING or just revealed.";
  const map = {
    TRANSCRIPT: transcript,
    DATE: date,
    TODAY: todayText(),
    SOURCE: (project && (project.channel || document.getElementById("source").value)) || "the source",
    URL: (project && project.url) || "(paste the public link)",
    TITLE: (project && project.title) || document.getElementById("headline").value || "the clip",
  };
  return body.replace(/\{\{([A-Z]+)\}\}/g, (_, key) => map[key] || "");
}

async function loadPrompts() {
  const response = await fetch("/api/prompts");
  const data = await response.json();
  const root = document.getElementById("prompts");
  (data.prompts || []).forEach((prompt) => {
    const block = document.createElement("div");
    block.className = "prompt";
    const title = document.createElement("h3");
    title.textContent = prompt.title;
    const pre = document.createElement("pre");
    pre.textContent = prompt.body;
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Copy";
    button.addEventListener("click", async () => {
      const text = fillPrompt(prompt.body);
      try {
        await navigator.clipboard.writeText(text);
      } catch (error) {
        const area = document.createElement("textarea");
        area.value = text;
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        area.remove();
      }
      setStatus("Copied. Paste it into free Grok or ChatGPT.");
    });
    block.append(title, button, pre);
    root.appendChild(block);
  });
}

async function loadHealth() {
  const response = await fetch("/api/health");
  const data = await response.json();
  const root = document.getElementById("health");
  root.innerHTML = "";
  let joeOk = false;
  (data.checks || []).forEach((row) => {
    const pill = document.createElement("span");
    pill.className = "pill " + (row.ok ? "good" : row.required ? "bad" : "");
    pill.textContent = row.label + ": " + (row.ok ? "ready" : row.detail);
    root.appendChild(pill);
    if (row.label === "Grandfather Joe") joeOk = row.ok;
  });
  document.getElementById("joe-note").hidden = joeOk;
}

document.getElementById("update-dl").addEventListener("click", async () => {
  try {
    const result = await startJob("/api/update-ytdlp", { method: "POST" });
    setStatus(result.message || "Downloader updated.");
    loadHealth();
  } catch (error) {
    setStatus(error.message, true);
  }
});

loadPrompts().catch(() => setStatus("Could not load the prompts.", true));
loadHealth().catch(() => {});
