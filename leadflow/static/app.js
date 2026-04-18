const state = {
  prompts: Array.isArray(window.__INITIAL_PROMPTS__) ? window.__INITIAL_PROMPTS__ : [],
  selectedPromptId: document.body.dataset.selectedPromptId || "",
  prompt: null,
  prospects: [],
  selectedProspectId: null,
  pollHandle: null,
  lastPromptSignature: "",
};

const els = {
  promptForm: document.querySelector("#prompt-form"),
  promptInput: document.querySelector("#prompt-input"),
  limitInput: document.querySelector("#limit-input"),
  composerStatus: document.querySelector("#composer-status"),
  promptList: document.querySelector("#prompt-list"),
  promptTitle: document.querySelector("#prompt-title"),
  metricStatus: document.querySelector("#metric-status"),
  metricDiscovered: document.querySelector("#metric-discovered"),
  metricScored: document.querySelector("#metric-scored"),
  metricEnriched: document.querySelector("#metric-enriched"),
  briefGrid: document.querySelector("#brief-grid"),
  promptError: document.querySelector("#prompt-error"),
  prospectTable: document.querySelector("#prospect-table"),
  inspector: document.querySelector(".inspector"),
  inspectorName: document.querySelector("#inspector-name"),
  inspectorRole: document.querySelector("#inspector-role"),
  inspectorScorebar: document.querySelector("#inspector-scorebar span"),
  detailCompany: document.querySelector("#detail-company"),
  detailLocation: document.querySelector("#detail-location"),
  detailDecision: document.querySelector("#detail-decision"),
  detailPhone: document.querySelector("#detail-phone"),
  detailReason: document.querySelector("#detail-reason"),
  phoneList: document.querySelector("#phone-list"),
  detailProfile: document.querySelector("#detail-profile"),
  callButton: document.querySelector("#call-button"),
  callStatus: document.querySelector("#call-status"),
  retryButton: document.querySelector("#retry-button"),
};

async function fetchJson(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    const detail = payload.detail || `HTTP ${response.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return payload;
}

function setComposerStatus(message, isError = false) {
  els.composerStatus.textContent = message || "";
  els.composerStatus.style.color = isError ? "var(--danger)" : "var(--muted)";
}

function renderPromptList() {
  els.promptList.innerHTML = state.prompts
    .map(
      (prompt) => `
        <a class="promptlink ${prompt.id === state.selectedPromptId ? "active" : ""}" href="/prompts/${prompt.id}">
          <span class="promptstatus status-${prompt.status}">${prompt.status}</span>
          <strong>${escapeHtml(trimText(prompt.raw_prompt, 72))}</strong>
          <span class="promptmeta">${prompt.discovered_count} leads · ${prompt.enriched_count} enriched</span>
        </a>
      `
    )
    .join("");
}

function renderBrief(brief = {}) {
  const entries = [
    ["Roles", (brief.target_roles || []).join(", ") || "Not set"],
    ["Industries", (brief.industries || []).join(", ") || "Not set"],
    ["Geographies", (brief.geographies || []).join(", ") || "Not set"],
    ["Seniority", (brief.seniority_hints || []).join(", ") || "Not set"],
    ["Exclusions", (brief.exclusions || []).join(", ") || "None"],
    ["Outreach angle", brief.outreach_angle || "Not set"],
  ];
  els.briefGrid.innerHTML = entries
    .map(
      ([label, value]) => `
        <div class="briefitem">
          <span class="metriclabel">${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </div>
      `
    )
    .join("");
}

function renderPrompt() {
  const prompt = state.prompt;
  if (!prompt) {
    els.promptTitle.textContent = "Select a prompt";
    els.metricStatus.textContent = "Idle";
    els.metricDiscovered.textContent = "0";
    els.metricScored.textContent = "0";
    els.metricEnriched.textContent = "0";
    renderBrief({});
    els.promptError.textContent = "";
    return;
  }
  els.promptTitle.textContent = trimText(prompt.raw_prompt, 120);
  els.metricStatus.textContent = prompt.status;
  els.metricDiscovered.textContent = String(prompt.discovered_count);
  els.metricScored.textContent = String(prompt.scored_count);
  els.metricEnriched.textContent = String(prompt.enriched_count);
  renderBrief(prompt.canonical_brief_json || {});
  els.promptError.textContent = prompt.error_text || "";
}

function renderProspects() {
  els.prospectTable.innerHTML = state.prospects
    .map((item, index) => {
      const selected = item.prompt_prospect_id === state.selectedProspectId ? "selected" : "";
      const score = Number(item.confidence_score || 0);
      return `
        <tr class="${selected}" data-id="${item.prompt_prospect_id}" style="--stagger:${index}">
          <td>
            <div class="leadname">
              <strong>${escapeHtml(item.full_name || "Unnamed lead")}</strong>
              <span class="muted">${escapeHtml(item.company_name || "Unknown company")} · ${escapeHtml(item.job_title || "Unknown role")}</span>
            </div>
          </td>
          <td>
            <a
              class="profilelink"
              href="${escapeHtml(item.profile_url || "#")}"
              target="_blank"
              rel="noreferrer"
              onclick="event.stopPropagation()"
            >
              Open
            </a>
          </td>
          <td>
            <div class="scorewrap">
              <strong>${score}</strong>
              <div class="scorebar"><span style="width:${score}%"></span></div>
            </div>
          </td>
          <td><span class="decision">${escapeHtml(item.ai_decision || "pending")}</span></td>
          <td>${escapeHtml(item.enrichment_status || "-")}</td>
          <td>${escapeHtml(item.best_phone_e164 || "-")}</td>
        </tr>
      `;
    })
    .join("");

  document.querySelectorAll("#prospect-table tr").forEach((row) => {
    row.addEventListener("click", () => {
      state.selectedProspectId = row.dataset.id;
      renderProspects();
      renderInspector();
    });
  });
}

function renderInspector() {
  const item = state.prospects.find((entry) => entry.prompt_prospect_id === state.selectedProspectId);
  if (!item) {
    els.inspectorName.textContent = "No lead selected";
    els.inspectorRole.textContent = "";
    els.inspectorScorebar.style.width = "0%";
    els.detailCompany.textContent = "-";
    els.detailLocation.textContent = "-";
    els.detailDecision.textContent = "-";
    els.detailPhone.textContent = "-";
    els.detailReason.textContent = "Select a prospect to inspect the confidence rationale.";
    els.phoneList.innerHTML = "";
    els.detailProfile.href = "#";
    els.callButton.disabled = true;
    els.callStatus.textContent = "";
    return;
  }

  els.inspector.classList.remove("flash");
  void els.inspector.offsetWidth;
  els.inspector.classList.add("flash");
  els.inspectorName.textContent = item.full_name || "Unnamed lead";
  els.inspectorRole.textContent = [item.job_title, item.company_name].filter(Boolean).join(" at ");
  els.inspectorScorebar.style.width = `${item.confidence_score || 0}%`;
  els.detailCompany.textContent = item.company_name || "-";
  els.detailLocation.textContent = item.location || "-";
  els.detailDecision.textContent = item.ai_decision || "-";
  els.detailPhone.textContent = item.best_phone_e164 || "-";
  els.detailReason.textContent = item.score_reason || "No scoring rationale yet.";
  els.phoneList.innerHTML = (item.phones_json || []).map((phone) => `<li>${escapeHtml(String(phone))}</li>`).join("") || "<li>No enriched phones</li>";
  els.detailProfile.href = item.profile_url || "#";
  els.callButton.disabled = false;
}

async function refreshPrompts() {
  const payload = await fetchJson("/api/prompts");
  state.prompts = payload.items || [];
  renderPromptList();
}

function promptSignature(prompt) {
  if (!prompt) return "";
  return [
    prompt.status,
    prompt.discovered_count,
    prompt.scored_count,
    prompt.enriched_count,
    prompt.error_text || "",
    prompt.updated_at || "",
  ].join("|");
}

function isPromptActive(prompt) {
  return Boolean(prompt && ["queued", "planning", "discovering", "scoring", "enriching"].includes(prompt.status));
}

async function refreshSelectedPrompt() {
  if (!state.selectedPromptId) {
    if (state.prompts[0]) {
      state.selectedPromptId = state.prompts[0].id;
      history.replaceState({}, "", `/prompts/${state.selectedPromptId}`);
    } else {
      state.prompt = null;
      state.prospects = [];
      renderPrompt();
      renderProspects();
      renderInspector();
      return;
    }
  }
  state.prompt = await fetchJson(`/api/prompts/${state.selectedPromptId}`);
  const signature = promptSignature(state.prompt);
  const shouldRefreshProspects = signature !== state.lastPromptSignature || state.prospects.length === 0;
  if (shouldRefreshProspects) {
    const prospectsPayload = await fetchJson(`/api/prompts/${state.selectedPromptId}/prospects`);
    state.prospects = prospectsPayload.items || [];
    if (!state.prospects.find((item) => item.prompt_prospect_id === state.selectedProspectId)) {
      state.selectedProspectId = state.prospects[0]?.prompt_prospect_id || null;
    }
  }
  state.lastPromptSignature = signature;
  renderPrompt();
  renderProspects();
  renderInspector();
}

async function pollSelectedPrompt() {
  if (!state.selectedPromptId) return;
  const previousSignature = state.lastPromptSignature;
  const previousStatus = state.prompt?.status || "";
  const nextPrompt = await fetchJson(`/api/prompts/${state.selectedPromptId}`);
  const nextSignature = promptSignature(nextPrompt);
  const stageChanged = nextPrompt.status !== previousStatus;
  const promptChanged = nextSignature !== previousSignature;

  state.prompt = nextPrompt;
  state.lastPromptSignature = nextSignature;

  if (promptChanged) {
    if (stageChanged || nextPrompt.discovered_count !== state.prospects.length || nextPrompt.enriched_count > 0) {
      const prospectsPayload = await fetchJson(`/api/prompts/${state.selectedPromptId}/prospects`);
      state.prospects = prospectsPayload.items || [];
      if (!state.prospects.find((item) => item.prompt_prospect_id === state.selectedProspectId)) {
        state.selectedProspectId = state.prospects[0]?.prompt_prospect_id || null;
      }
    }
    if (stageChanged) {
      await refreshPrompts();
    }
    renderPrompt();
    renderProspects();
    renderInspector();
  }
}

function stopPolling() {
  if (state.pollHandle) {
    window.clearInterval(state.pollHandle);
    state.pollHandle = null;
  }
}

function startPolling() {
  stopPolling();
  if (!isPromptActive(state.prompt)) {
    return;
  }
  state.pollHandle = window.setInterval(() => {
    pollSelectedPrompt()
      .then(() => {
        if (!isPromptActive(state.prompt)) {
          stopPolling();
          refreshPrompts().catch((error) => {
            els.promptError.textContent = error.message;
          });
        }
      })
      .catch((error) => {
        els.promptError.textContent = error.message;
      });
  }, 4000);
}

async function bootstrap() {
  renderPromptList();
  await refreshPrompts();
  await refreshSelectedPrompt();
  startPolling();
}

els.promptForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const prompt = els.promptInput.value.trim();
  const requested_limit = Number(els.limitInput.value || 5);
  if (!prompt) {
    setComposerStatus("Prompt is required.", true);
    return;
  }
  setComposerStatus("Queueing prompt...");
  try {
    const payload = await fetchJson("/api/prompts", {
      method: "POST",
      body: JSON.stringify({ prompt, requested_limit }),
    });
    state.selectedPromptId = payload.id;
    history.pushState({}, "", `/prompts/${payload.id}`);
    els.promptInput.value = "";
    setComposerStatus("Prompt queued.");
    await refreshPrompts();
    await refreshSelectedPrompt();
    startPolling();
  } catch (error) {
    setComposerStatus(error.message, true);
  }
});

els.retryButton?.addEventListener("click", async () => {
  if (!state.selectedPromptId) return;
  els.promptError.textContent = "";
  try {
    await fetchJson(`/api/prompts/${state.selectedPromptId}/retry`, { method: "POST" });
    await refreshPrompts();
    await refreshSelectedPrompt();
    startPolling();
  } catch (error) {
    els.promptError.textContent = error.message;
  }
});

els.callButton?.addEventListener("click", async () => {
  if (!state.selectedProspectId) return;
  els.callStatus.textContent = "Sending to voicecall...";
  try {
    const result = await fetchJson(`/api/prompt-prospects/${state.selectedProspectId}/call`, { method: "POST" });
    els.callStatus.textContent = `Voicecall queued: ${result.voicecall_call_id}`;
    await refreshSelectedPrompt();
  } catch (error) {
    els.callStatus.textContent = error.message;
  }
});

document.querySelector("#prompt-list")?.addEventListener("click", (event) => {
  const link = event.target.closest("a[href^='/prompts/']");
  if (!link) return;
  event.preventDefault();
  const promptId = link.getAttribute("href").split("/").pop();
  state.selectedPromptId = promptId;
  history.pushState({}, "", `/prompts/${promptId}`);
  refreshSelectedPrompt().catch((error) => {
    els.promptError.textContent = error.message;
  }).finally(() => {
    startPolling();
  });
});

window.addEventListener("popstate", () => {
  const parts = window.location.pathname.split("/");
  state.selectedPromptId = parts[1] === "prompts" ? parts[2] : "";
  refreshSelectedPrompt().catch((error) => {
    els.promptError.textContent = error.message;
  }).finally(() => {
    startPolling();
  });
});

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function trimText(value, length) {
  const text = String(value || "");
  return text.length > length ? `${text.slice(0, length)}...` : text;
}

bootstrap().catch((error) => {
  setComposerStatus(error.message, true);
});
