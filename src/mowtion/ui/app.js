const state = {
  mode: "script",
  preset: "clean-light",
  aspect: "9:16",
  file: null,
};

const scriptBox = document.getElementById("script");
const drop = document.getElementById("drop");
const fileInput = document.getElementById("file");
const fileName = document.getElementById("file-name");
const go = document.getElementById("go");
const statusEl = document.getElementById("status");
const bar = document.getElementById("bar");
const result = document.getElementById("result");
const player = document.getElementById("player");
const links = document.getElementById("links");
const seoOut = document.getElementById("seo-out");

function setMode(mode) {
  state.mode = mode;
  document.getElementById("mode-script").classList.toggle("active", mode === "script");
  document.getElementById("mode-file").classList.toggle("active", mode === "file");
  scriptBox.style.display = mode === "script" ? "block" : "none";
  drop.classList.toggle("show", mode === "file");
}
document.getElementById("mode-script").onclick = () => setMode("script");
document.getElementById("mode-file").onclick = () => setMode("file");

document.querySelectorAll(".aspects button").forEach((button) => {
  button.onclick = () => {
    state.aspect = button.dataset.aspect;
    document.querySelectorAll(".aspects button").forEach((other) => other.classList.toggle("active", other === button));
  };
});

document.getElementById("browse").onclick = () => fileInput.click();
fileInput.onchange = () => {
  state.file = fileInput.files[0] || null;
  fileName.textContent = state.file ? state.file.name : "";
};
["dragover", "dragenter"].forEach((name) => drop.addEventListener(name, (event) => {
  event.preventDefault();
  drop.classList.add("hot");
}));
["dragleave", "drop"].forEach((name) => drop.addEventListener(name, (event) => {
  event.preventDefault();
  drop.classList.remove("hot");
}));
drop.addEventListener("drop", (event) => {
  state.file = event.dataTransfer.files[0] || null;
  fileName.textContent = state.file ? state.file.name : "";
});

async function loadPresets() {
  const response = await fetch("/api/presets");
  const data = await response.json();
  const root = document.getElementById("presets");
  data.presets.forEach((preset) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "preset" + (preset.id === state.preset ? " active" : "");
    button.innerHTML = `<div class="swatch">
      <i style="background:${preset.bg}"></i>
      <i style="background:${preset.accent}"></i>
      <i style="background:${preset.accent2}"></i>
    </div><b>${preset.name}</b><span>${preset.tagline}</span>`;
    button.onclick = () => {
      state.preset = preset.id;
      root.querySelectorAll(".preset").forEach((other) => other.classList.toggle("active", other === button));
    };
    root.appendChild(button);
  });
}

async function health() {
  const response = await fetch("/api/health");
  const data = await response.json();
  const slot = document.getElementById("health");
  if (!data.ffmpeg) {
    slot.innerHTML = `<div class="note warn">ffmpeg is not installed, so export will fail. Install it, then restart mowtion. Windows: winget install ffmpeg. Mac: brew install ffmpeg.</div>`;
  } else if (!data.kokoro) {
    slot.innerHTML = `<div class="note">The voice model downloads the first time you make a video. It takes a few minutes and then stays on this computer.</div>`;
  }
}

function link(href, label) {
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.textContent = label;
  anchor.target = "_blank";
  return anchor;
}

async function poll(id) {
  const response = await fetch(`/api/jobs/${id}`);
  const job = await response.json();
  bar.hidden = false;
  bar.firstElementChild.style.width = `${Math.round((job.progress || 0) * 100)}%`;
  statusEl.textContent = job.message || "";
  if (job.status === "running") {
    setTimeout(() => poll(id), 600);
    return;
  }
  go.disabled = false;
  if (job.status === "error") {
    statusEl.textContent = job.message || "Something went wrong.";
    return;
  }
  result.hidden = false;
  player.src = `/api/jobs/${id}/video`;
  links.replaceChildren(
    link(`/api/jobs/${id}/video`, "Download video"),
    link(`/api/jobs/${id}/project`, "project.json"),
  );
  if (job.result && job.result.thumbnail) {
    links.append(link(`/api/jobs/${id}/thumb`, "Thumbnail"), link(`/api/jobs/${id}/cover`, "Cover"));
  }
  if (job.result && job.result.seo) {
    const seoRes = await fetch(`/api/jobs/${id}/seo`);
    seoOut.hidden = false;
    seoOut.textContent = await seoRes.text();
  }
}

go.onclick = async () => {
  result.hidden = true;
  seoOut.hidden = true;
  go.disabled = true;
  statusEl.textContent = "Starting…";
  const seoOn = document.querySelector("details").open;
  const params = new URLSearchParams({
    preset: state.preset,
    aspect: state.aspect,
    seo: seoOn ? "1" : "0",
    title: document.getElementById("title").value,
    description: document.getElementById("description").value,
    tags: document.getElementById("tags").value,
  });
  let response;
  if (state.mode === "file") {
    if (!state.file) {
      statusEl.textContent = "Drop a clip first.";
      go.disabled = false;
      return;
    }
    params.set("filename", state.file.name);
    response = await fetch(`/api/jobs?${params}`, {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: state.file,
    });
  } else {
    const script = scriptBox.value.trim();
    if (!script) {
      statusEl.textContent = "Write a few words first.";
      go.disabled = false;
      return;
    }
    response = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        script,
        preset: state.preset,
        aspect: state.aspect,
        seo: seoOn,
        title: document.getElementById("title").value,
        description: document.getElementById("description").value,
        tags: document.getElementById("tags").value,
      }),
    });
  }
  const data = await response.json();
  if (!response.ok) {
    statusEl.textContent = data.error || "Could not start.";
    go.disabled = false;
    return;
  }
  poll(data.id);
};

loadPresets();
health();
