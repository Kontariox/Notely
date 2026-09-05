/**
 * Notely - Frontend Application Logic
 */

let currentLessonId = null;
let currentLessonData = null;
let activePollingInterval = null;
let currentAiPrepData = null;
let currentAiPrepActiveView = "prompt";

let allLessonsData = [];
let isOpeningFromHistory = false;
let currentSubjectFilter = "";
let currentDateSort = "date-desc";
let currentSearchQuery = "";

// Show/Hide View Helpers
function showUploadView() {
    const uploadGrid = document.getElementById("uploadGrid");
    const uploadHeader = document.getElementById("uploadPaneHeader");
    const resultSection = document.getElementById("lessonResultSection");
    const progressCard = document.getElementById("progressCard");

    if (uploadGrid) uploadGrid.classList.remove("hidden");
    if (uploadHeader) uploadHeader.classList.remove("hidden");
    if (resultSection) resultSection.classList.add("hidden");
    if (progressCard && !activePollingInterval) progressCard.classList.add("hidden");
}

function showLessonView() {
    const uploadGrid = document.getElementById("uploadGrid");
    const uploadHeader = document.getElementById("uploadPaneHeader");
    const resultSection = document.getElementById("lessonResultSection");
    const progressCard = document.getElementById("progressCard");

    if (uploadGrid) uploadGrid.classList.add("hidden");
    if (uploadHeader) uploadHeader.classList.add("hidden");
    if (progressCard) progressCard.classList.add("hidden");
    if (resultSection) resultSection.classList.remove("hidden");
}

// Simple Markdown to HTML parser
function renderMarkdown(md) {
    if (!md) return "";
    let html = md
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
        .replace(/^\> (.*$)/gim, '<blockquote>$1</blockquote>')
        .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/gim, '<em>$1</em>')
        .replace(/^- (.*$)/gim, '<li>$1</li>')
        .replace(/(<li>[\s\S]*?<\/li>)/gm, '<ul>$1</ul>')
        .replace(/\n\n/gim, '<p></p>')
        .replace(/\n/gim, '<br>');
    return html;
}

// Toast notification helper
function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// Copy to clipboard helper
async function copyTextToClipboard(text, successMsg = "Skopiowano do schowka!") {
    try {
        await navigator.clipboard.writeText(text);
        showToast(successMsg, "success");
    } catch (err) {
        // Fallback for older browsers
        const textarea = document.createElement("textarea");
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
        showToast(successMsg, "success");
    }
}

// Format duration
function formatDuration(seconds) {
    if (!seconds) return "0:00";
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
}

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
    initNavigation();
    initUploadForm();
    initSettingsForm();
    initCalendarControls();
    initHistoryControls();
    initAiPrepControls();
    loadRecentLessons();
    loadSettings();

    // Top nav in lesson result section
    const backToHistoryBtn = document.getElementById("backToHistoryBtn");
    if (backToHistoryBtn) {
        backToHistoryBtn.addEventListener("click", () => {
            document.querySelector('.nav-item[data-tab="tab-history"]')?.click();
        });
    }

    const backToUploadBtn = document.getElementById("backToUploadBtn");
    if (backToUploadBtn) {
        backToUploadBtn.addEventListener("click", () => {
            showUploadView();
            window.scrollTo({ top: 0, behavior: "smooth" });
        });
    }

    // Default today's date in upload form
    const today = new Date().toISOString().split("T")[0];
    const dateInput = document.getElementById("lessonDateInput");
    if (dateInput) dateInput.value = today;

    // Check query params for calendar callback
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has("calendar")) {
        showToast("Pomyślnie połączono z Kalendarzem Google!", "success");
        window.history.replaceState({}, document.title, window.location.pathname);
    } else if (urlParams.has("calendar_error")) {
        showToast(`Błąd łączenia z Kalendarzem: ${urlParams.get("calendar_error")}`, "error");
        window.history.replaceState({}, document.title, window.location.pathname);
    }
});

// Tab Navigation
function initNavigation() {
    const navItems = document.querySelectorAll(".nav-item");
    const tabPanes = document.querySelectorAll(".tab-pane");

    navItems.forEach(item => {
        item.addEventListener("click", () => {
            const targetTab = item.getAttribute("data-tab");
            navItems.forEach(n => n.classList.remove("active"));
            tabPanes.forEach(p => p.classList.remove("active"));

            item.classList.add("active");
            const activePane = document.getElementById(targetTab);
            if (activePane) activePane.classList.add("active");

            if (targetTab === "tab-upload" && !isOpeningFromHistory) {
                showUploadView();
            }
            if (targetTab === "tab-history") loadRecentLessons();
            if (targetTab === "tab-settings") loadSettings();
        });
    });

    // Subtabs for Lesson Workspace
    const subTabBtns = document.querySelectorAll(".sub-tab-btn");
    const subTabContents = document.querySelectorAll(".subtab-content");

    subTabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetSub = btn.getAttribute("data-subtab");
            subTabBtns.forEach(b => b.classList.remove("active"));
            subTabContents.forEach(c => c.classList.remove("active"));

            btn.classList.add("active");
            const activeContent = document.getElementById(targetSub);
            if (activeContent) activeContent.classList.add("active");

            if (targetSub === "subtab-ai-prep" && currentLessonId) {
                generateAiPrepContent();
            }
        });
    });
}

// Upload & Drag-and-Drop handling
function initUploadForm() {
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("mediaFileInput");
    const fileInfo = document.getElementById("selectedFileInfo");
    const fileNameSpan = document.getElementById("selectedFileName");
    const clearFileBtn = document.getElementById("clearFileBtn");
    const submitBtn = document.getElementById("startProcessBtn");
    const useDefault = document.getElementById("useDefaultSettings");
    const advancedOptions = document.getElementById("advancedOptions");
    const uploadForm = document.getElementById("uploadForm");

    useDefault.addEventListener("change", (e) => {
        if (e.target.checked) {
            advancedOptions.classList.add("hidden");
        } else {
            advancedOptions.classList.remove("hidden");
        }
    });

    // File selection
    fileInput.addEventListener("change", () => {
        if (fileInput.files.length > 0) {
            const file = fileInput.files[0];
            fileNameSpan.textContent = `${file.name} (${(file.size / (1024 * 1024)).toFixed(1)} MB)`;
            fileInfo.classList.remove("hidden");
            submitBtn.disabled = false;
        }
    });

    clearFileBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        fileInput.value = "";
        fileInfo.classList.add("hidden");
        submitBtn.disabled = true;
    });

    // Drag and Drop
    ['dragenter', 'dragover'].forEach(name => {
        dropzone.addEventListener(name, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(name => {
        dropzone.addEventListener(name, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove('dragover');
        });
    });

    dropzone.addEventListener('drop', (e) => {
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            const file = fileInput.files[0];
            fileNameSpan.textContent = `${file.name} (${(file.size / (1024 * 1024)).toFixed(1)} MB)`;
            fileInfo.classList.remove("hidden");
            submitBtn.disabled = false;
        }
    });

    // Submit form
    uploadForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!fileInput.files || fileInput.files.length === 0) {
            showToast("Wybierz plik nagrania.", "error");
            return;
        }

        const formData = new FormData(uploadForm);
        submitBtn.disabled = true;

        // Reveal progress card
        const progressCard = document.getElementById("progressCard");
        const errorAlert = document.getElementById("errorMessageAlert");
        const resultSection = document.getElementById("lessonResultSection");

        progressCard.classList.remove("hidden");
        errorAlert.classList.add("hidden");
        resultSection.classList.add("hidden");

        updateProgressUI(5, "Przesyłanie pliku na serwer...", "upload");

        try {
            const res = await fetch("/api/upload", {
                method: "POST",
                body: formData
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || "Błąd podczas przesyłania.");
            }

            const data = await res.json();
            currentLessonId = data.id;

            // Mark step 1 done
            setStepDone("step-upload");
            startStatusPolling(data.id);
        } catch (err) {
            showToast(err.message, "error");
            errorAlert.textContent = `Błąd: ${err.message}`;
            errorAlert.classList.remove("hidden");
            submitBtn.disabled = false;
        }
    });
}

// Progress UI Updates
function updateProgressUI(percent, stageText, activeStepKey) {
    const bar = document.getElementById("progressBar");
    const pText = document.getElementById("progressPercent");
    const stage = document.getElementById("currentStageText");

    if (bar) bar.style.width = `${percent}%`;
    if (pText) pText.textContent = `${percent}%`;
    if (stage) stage.textContent = stageText;

    if (activeStepKey) {
        document.querySelectorAll(".step-item").forEach(s => s.classList.remove("active"));
        const stepEl = document.getElementById(`step-${activeStepKey}`);
        if (stepEl) stepEl.classList.add("active");
    }
}

function setStepDone(stepId) {
    const el = document.getElementById(stepId);
    if (el) {
        el.classList.remove("active");
        el.classList.add("done");
        const bullet = el.querySelector(".step-bullet");
        if (bullet) bullet.textContent = "✓";
    }
}

// Polling status
function startStatusPolling(lessonId) {
    if (activePollingInterval) clearInterval(activePollingInterval);

    activePollingInterval = setInterval(async () => {
        try {
            const res = await fetch(`/api/lessons/${lessonId}/status`);
            if (!res.ok) return;

            const statusData = await res.json();

            // Match stages to step highlights
            let stepKey = "audio";
            if (statusData.status === "audio_processing") {
                stepKey = "audio";
                setStepDone("step-upload");
            } else if (statusData.status === "transcribing") {
                stepKey = "transcribe";
                setStepDone("step-audio");
            } else if (statusData.status === "analyzing") {
                stepKey = "nim";
                setStepDone("step-transcribe");
            }

            updateProgressUI(statusData.progress_percent, statusData.current_stage, stepKey);

            if (statusData.status === "completed") {
                clearInterval(activePollingInterval);
                activePollingInterval = null;
                setStepDone("step-nim");
                setStepDone("step-notes");
                updateProgressUI(100, "Przetwarzanie zakończone pomyślnie!", "notes");
                document.getElementById("startProcessBtn").disabled = false;
                showToast("Lekcja została pomyślnie przetworzona!", "success");
                showLessonView();
                loadLessonDetails(lessonId);
                loadRecentLessons();
            } else if (statusData.status === "failed") {
                clearInterval(activePollingInterval);
                activePollingInterval = null;
                document.getElementById("startProcessBtn").disabled = false;
                const errAlert = document.getElementById("errorMessageAlert");
                errAlert.textContent = statusData.error_message || "Wystąpił błąd przetwarzania.";
                errAlert.classList.remove("hidden");
                showToast("Przetwarzanie zakończone niepowodzeniem.", "error");
            }
        } catch (e) {
            console.error("Błąd odpytywania statusu:", e);
        }
    }, 1200);
}

// Load and display complete lesson details
async function loadLessonDetails(lessonId) {
    try {
        const res = await fetch(`/api/lessons/${lessonId}`);
        if (!res.ok) throw new Error("Nie udało się pobrać szczegółów lekcji.");

        const data = await res.json();
        currentLessonId = data.id;
        currentLessonData = data;
        currentAiPrepData = null;

        // If ai-prep subtab is currently visible, fetch its data
        const activeSubtab = document.querySelector(".sub-tab-btn.active");
        if (activeSubtab?.getAttribute("data-subtab") === "subtab-ai-prep") {
            generateAiPrepContent();
        }

        // Header info
        document.getElementById("resSubject").textContent = data.subject || "Ogólny";
        document.getElementById("resTopic").textContent = data.notes ? (data.notes.match(/# Temat(?: lekcji)?:\s*([^\n\r]+)/i)?.[1] || data.original_filename) : data.original_filename;
        document.getElementById("resDate").textContent = data.lesson_date ? `Data: ${data.lesson_date}` : "Brak daty";
        document.getElementById("resDuration").textContent = `Czas: ${formatDuration(data.duration)}`;
        document.getElementById("resEngine").textContent = data.transcription_engine;

        // Subtab 1: Notes
        const notesContainer = document.getElementById("notesMarkdownViewer");
        notesContainer.innerHTML = renderMarkdown(data.notes || "Brak notatki.");

        // Subtab 2: Events
        renderEventsList(data.detected_events || []);
        document.getElementById("eventCountBadge").textContent = (data.detected_events || []).length;

        // Subtab 3: Transcription
        const transViewer = document.getElementById("transcriptionTextViewer");
        transViewer.textContent = data.transcription || "Brak transkrypcji.";
        const wordCount = (data.transcription || "").trim().split(/\s+/).filter(Boolean).length;
        document.getElementById("transcriptionLenBadge").textContent = `${wordCount} słów`;

        // Configure Export & Copy Buttons
        initActionButtons(data);

        // Show section & ensure lesson view is active (no upload box, no live status)
        showLessonView();
        document.getElementById("lessonResultSection").scrollIntoView({ behavior: "smooth" });

    } catch (err) {
        showToast(err.message, "error");
    }
}

// Render Event Cards
function renderEventsList(events) {
    const container = document.getElementById("eventsListContainer");
    container.innerHTML = "";

    if (!events || events.length === 0) {
        container.innerHTML = "<p class='text-dim text-center'>Nie wykryto żadnych terminów ani sprawdzianów w treści nagrania.</p>";
        return;
    }

    events.forEach((ev, idx) => {
        const item = document.createElement("div");
        item.className = "event-card-item";

        const hasCalendarDate = Boolean(ev.date);
        const dateDisplay = ev.date || ev.raw_date_expression || "Brak określonej daty";
        const dateExtra = ev.is_date_calculated ? ` (Wyliczono z daty lekcji: ${ev.date_explanation || ''})` : '';

        item.innerHTML = `
            <input type="checkbox" class="event-checkbox" data-index="${idx}" ${hasCalendarDate ? "checked" : ""}>
            <div class="event-info">
                <div class="event-title-row">
                    <span class="event-title">${ev.title || "Wydarzenie"}</span>
                    <span class="event-type-badge ${ev.type || 'other'}">${ev.type || 'Inne'}</span>
                    <span class="badge-sub">${Math.round((ev.confidence || 0.8) * 100)}% pewności</span>
                </div>
                <div class="event-date-row">
                    <span>🗓️ ${dateDisplay}${dateExtra}</span>
                </div>
                <p class="event-desc">${ev.description || ''}</p>
                ${ev.source_text ? `<div class="event-source-quote">„${ev.source_text}”</div>` : ''}
            </div>
        `;
        container.appendChild(item);
    });
}

// Action Buttons: Copying and Downloads
function initActionButtons(data) {
    const lessonId = data.id;

    // Top action buttons
    document.getElementById("copyAllDataBtn").onclick = async () => {
        const res = await fetch(`/api/lessons/${lessonId}/export/all?format=txt`);
        const text = await res.text();
        copyTextToClipboard(text, "Skopiowano kompletny pakiet lekcji do schowka!");
    };

    document.getElementById("copyNotesBtn").onclick = () => {
        copyTextToClipboard(data.notes || "", "Skopiowano treść notatki!");
    };

    document.getElementById("downloadDocxBtn").onclick = () => {
        window.location.href = `/api/lessons/${lessonId}/export/note?format=docx`;
    };

    // Transcription subtab buttons
    document.getElementById("copyTranscriptionBtn").onclick = () => {
        copyTextToClipboard(data.transcription || "", "Skopiowano pełną transkrypcję!");
    };

    document.getElementById("downloadTranscriptionTxt").onclick = () => {
        window.location.href = `/api/lessons/${lessonId}/export/transcription?format=txt`;
    };
    document.getElementById("downloadTranscriptionMd").onclick = () => {
        window.location.href = `/api/lessons/${lessonId}/export/transcription?format=md`;
    };
    document.getElementById("downloadTranscriptionSrt").onclick = () => {
        window.location.href = `/api/lessons/${lessonId}/export/transcription?format=srt`;
    };
    document.getElementById("downloadTranscriptionVtt").onclick = () => {
        window.location.href = `/api/lessons/${lessonId}/export/transcription?format=vtt`;
    };
    document.getElementById("downloadTranscriptionJson").onclick = () => {
        window.location.href = `/api/lessons/${lessonId}/export/transcription?format=json`;
    };
}

// Google Calendar Sync
function initCalendarControls() {
    const syncBtn = document.getElementById("syncCalendarBtn");
    if (syncBtn) {
        syncBtn.addEventListener("click", async () => {
            if (!currentLessonId) return;

            const checkboxes = document.querySelectorAll(".event-checkbox:checked");
            const indices = Array.from(checkboxes).map(cb => parseInt(cb.getAttribute("data-index")));

            if (indices.length === 0) {
                showToast("Zaznacz co najmniej jedno wydarzenie do dodania.", "info");
                return;
            }

            syncBtn.disabled = true;
            syncBtn.textContent = "Dodawanie do kalendarza...";

            try {
                const res = await fetch("/api/calendar/sync", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        lesson_id: currentLessonId,
                        selected_indices: indices
                    })
                });

                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || "Błąd dodawania do kalendarza.");

                showToast(`Dodano ${data.synced_count} wydarzeń do Google Calendar!`, "success");
            } catch (err) {
                showToast(err.message, "error");
            } finally {
                syncBtn.disabled = false;
                syncBtn.textContent = "🗓️ Dodaj zaznaczone do Kalendarza Google";
            }
        });
    }

    const connectBtn = document.getElementById("connectGoogleBtn");
    if (connectBtn) {
        connectBtn.addEventListener("click", async () => {
            try {
                const res = await fetch("/api/calendar/auth-url");
                const data = await res.json();
                if (data.auth_url) {
                    window.location.href = data.auth_url;
                } else {
                    showToast("Brak skonfigurowanego Google OAuth.", "error");
                }
            } catch (e) {
                showToast("Błąd pobierania linku autoryzacji Google.", "error");
            }
        });
    }

    const disconnectBtn = document.getElementById("disconnectGoogleBtn");
    if (disconnectBtn) {
        disconnectBtn.addEventListener("click", async () => {
            if (!confirm("Czy na pewno chcesz odłączyć Kalendarz Google i usunąć zapisane tokeny?")) return;
            try {
                const res = await fetch("/api/calendar/disconnect", { method: "POST" });
                if (res.ok) {
                    showToast("Odłączono Kalendarz Google.", "success");
                    loadCalendarStatus();
                }
            } catch (e) {
                showToast("Błąd podczas odłączania.", "error");
            }
        });
    }
}

// External AI Preparation (Redesigned)
async function generateAiPrepContent() {
    if (!currentLessonId) return;

    const display = document.getElementById("aiPrepTextDisplay");
    if (display && !display.textContent) {
        display.textContent = "Generowanie materiałów dla zewnętrznego AI...";
    }

    try {
        const res = await fetch(`/api/lessons/${currentLessonId}/ai-prep`);
        if (!res.ok) throw new Error("Nie udało się pobrać materiałów AI.");
        currentAiPrepData = await res.json();
        updateAiPrepPreview();
    } catch (e) {
        console.error("Błąd AI Prep:", e);
        showToast(e.message, "error");
    }
}

function updateAiPrepPreview() {
    const display = document.getElementById("aiPrepTextDisplay");
    if (!display || !currentAiPrepData) return;

    if (currentAiPrepActiveView === "transcription") {
        display.textContent = currentAiPrepData.transcription || "Brak transkrypcji.";
    } else if (currentAiPrepActiveView === "combined") {
        display.textContent = currentAiPrepData.combined_text || "";
    } else {
        // Default to analytical prompt
        display.textContent = currentAiPrepData.analytical_prompt || "";
    }
}

function initAiPrepControls() {
    // 1. Download full transcription as .TXT
    document.getElementById("downloadTranscriptionTxtBtn")?.addEventListener("click", () => {
        if (!currentLessonId) {
            showToast("Brak wybranej lekcji.", "error");
            return;
        }
        window.location.href = `/api/lessons/${currentLessonId}/export/transcription?format=txt`;
        showToast("Pobieranie pełnej transkrypcji...", "info");
    });

    // 1b. Download full transcription as .MD
    document.getElementById("downloadTranscriptionMdBtn")?.addEventListener("click", () => {
        if (!currentLessonId) {
            showToast("Brak wybranej lekcji.", "error");
            return;
        }
        window.location.href = `/api/lessons/${currentLessonId}/export/transcription?format=md`;
        showToast("Pobieranie transkrypcji Markdown...", "info");
    });

    // 2. Copy full analytical prompt
    document.getElementById("copyAnalyticalPromptBtn")?.addEventListener("click", async () => {
        if (!currentLessonId) return;
        if (!currentAiPrepData) {
            await generateAiPrepContent();
        }
        const promptText = currentAiPrepData?.analytical_prompt || "";
        if (promptText) {
            copyTextToClipboard(
                promptText,
                "Skopiowano pełny prompt analityczny! Wklej go do ChatGPT, Claude lub Gemini."
            );
        } else {
            showToast("Nie udało się wygenerować promptu analitycznego.", "error");
        }
    });

    // 2b. Copy combined (prompt + transcription)
    document.getElementById("copyCombinedPromptBtn")?.addEventListener("click", async () => {
        if (!currentLessonId) return;
        if (!currentAiPrepData) {
            await generateAiPrepContent();
        }
        const combinedText = currentAiPrepData?.combined_text || "";
        if (combinedText) {
            copyTextToClipboard(
                combinedText,
                "Skopiowano kompletny prompt wraz z całą transkrypcją!"
            );
        } else {
            showToast("Brak danych do skopiowania.", "error");
        }
    });

    // 3. Copy active preview display text
    document.getElementById("copyActivePreviewBtn")?.addEventListener("click", () => {
        const text = document.getElementById("aiPrepTextDisplay")?.textContent || "";
        if (text) {
            copyTextToClipboard(text, "Skopiowano zawartość podglądu do schowka!");
        }
    });

    // 4. Preview tabs switching
    document.querySelectorAll(".preview-tab-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".preview-tab-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            currentAiPrepActiveView = btn.getAttribute("data-preview") || "prompt";
            updateAiPrepPreview();
        });
    });
}

// Helper to extract timestamp for sorting
function getLessonDateTimestamp(lesson) {
    if (lesson.lesson_date) {
        const d = new Date(lesson.lesson_date);
        if (!isNaN(d.getTime())) return d.getTime();
    }
    if (lesson.created_at) {
        const d = new Date(lesson.created_at);
        if (!isNaN(d.getTime())) return d.getTime();
    }
    return 0;
}

// Populate / update subject filter options from current data
function updateSubjectFilterDropdown() {
    const filterSelect = document.getElementById("historySubjectFilter");
    if (!filterSelect) return;

    const prevValue = filterSelect.value || currentSubjectFilter;

    // Extract unique non-empty subjects
    const subjects = Array.from(new Set(
        allLessonsData
            .map(l => (l.subject || "").trim())
            .filter(Boolean)
    )).sort((a, b) => a.localeCompare(b, "pl"));

    filterSelect.innerHTML = '<option value="">Wszystkie przedmioty</option>';
    subjects.forEach(subj => {
        const opt = document.createElement("option");
        opt.value = subj;
        opt.textContent = subj;
        if (subj.toLowerCase() === prevValue.toLowerCase()) {
            opt.selected = true;
        }
        filterSelect.appendChild(opt);
    });
}

// Filter and sort lessons table
function applyHistoryFilterAndSort() {
    let filtered = [...allLessonsData];

    // 1. Subject filter
    const subjectFilter = document.getElementById("historySubjectFilter")?.value || "";
    currentSubjectFilter = subjectFilter;
    if (subjectFilter) {
        filtered = filtered.filter(l => (l.subject || "").trim().toLowerCase() === subjectFilter.toLowerCase());
    }

    // 2. Search query filter
    const searchQuery = (document.getElementById("historySearchInput")?.value || "").trim().toLowerCase();
    currentSearchQuery = searchQuery;
    if (searchQuery) {
        filtered = filtered.filter(l =>
            (l.subject || "").toLowerCase().includes(searchQuery) ||
            (l.original_filename || "").toLowerCase().includes(searchQuery) ||
            (l.lesson_date || "").toLowerCase().includes(searchQuery)
        );
    }

    // 3. Date sorting
    const sortVal = document.getElementById("historyDateSort")?.value || currentDateSort;
    currentDateSort = sortVal;

    // Update th icon
    const thIcon = document.getElementById("thDateSortIcon");
    if (thIcon) {
        thIcon.textContent = (sortVal === "date-asc" || sortVal === "created-asc") ? "↑" : "↓";
    }

    filtered.sort((a, b) => {
        if (sortVal === "date-desc") {
            return getLessonDateTimestamp(b) - getLessonDateTimestamp(a);
        } else if (sortVal === "date-asc") {
            return getLessonDateTimestamp(a) - getLessonDateTimestamp(b);
        } else if (sortVal === "created-desc") {
            return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime();
        } else if (sortVal === "created-asc") {
            return new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime();
        }
        return 0;
    });

    renderHistoryRows(filtered);

    // Update stats counter
    const stats = document.getElementById("historyStatsText");
    if (stats) {
        if (allLessonsData.length === 0) {
            stats.textContent = "Liczba lekcji: 0";
        } else if (filtered.length === allLessonsData.length) {
            stats.textContent = `Liczba lekcji: ${allLessonsData.length}`;
        } else {
            stats.textContent = `Wyświetlono: ${filtered.length} z ${allLessonsData.length}`;
        }
    }
}

// Render HTML table rows
function renderHistoryRows(lessons) {
    const tbody = document.getElementById("historyTableBody");
    if (!tbody) return;

    if (lessons.length === 0) {
        if (allLessonsData.length === 0) {
            tbody.innerHTML = "<tr><td colspan='6' class='text-center text-dim'>Brak zapisanych lekcji. Dodaj pierwsze nagranie!</td></tr>";
        } else {
            tbody.innerHTML = `<tr><td colspan='6' class='text-center text-dim'>
                Brak lekcji spełniających wybrane kryteria filtrów.
                <button class='btn btn-sm btn-outline' style='margin-left: 8px;' onclick='resetHistoryFilters()'>Wyczyść filtry</button>
            </td></tr>`;
        }
        return;
    }

    tbody.innerHTML = "";
    lessons.forEach(l => {
        const tr = document.createElement("tr");
        const statusClass = l.status === "completed" ? "dot-online" : (l.status === "failed" ? "dot-offline" : "");
        const formattedDate = l.lesson_date || (l.created_at ? l.created_at.split("T")[0] : 'Brak');
        tr.innerHTML = `
            <td><strong>${formattedDate}</strong></td>
            <td><span class="subject-badge">${l.subject || 'Ogólny'}</span></td>
            <td>${l.original_filename}</td>
            <td>${formatDuration(l.duration)}</td>
            <td>
                <span class="${statusClass}"></span> ${l.status === 'completed' ? 'Gotowa' : (l.current_stage || l.status)}
            </td>
            <td>
                <button class="btn btn-sm btn-primary" onclick="openLessonFromHistory('${l.id}')">Otwórz</button>
                <button class="btn btn-sm btn-danger" onclick="deleteLessonRecord('${l.id}')" title="Usuń lekcję">&times;</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// Reset history filters helper
window.resetHistoryFilters = () => {
    const subjSelect = document.getElementById("historySubjectFilter");
    if (subjSelect) subjSelect.value = "";
    const searchInp = document.getElementById("historySearchInput");
    if (searchInp) searchInp.value = "";
    const sortSelect = document.getElementById("historyDateSort");
    if (sortSelect) sortSelect.value = "date-desc";
    applyHistoryFilterAndSort();
};

// Initialize filter and sort listeners
function initHistoryControls() {
    document.getElementById("historySubjectFilter")?.addEventListener("change", applyHistoryFilterAndSort);
    document.getElementById("historyDateSort")?.addEventListener("change", applyHistoryFilterAndSort);
    document.getElementById("historySearchInput")?.addEventListener("input", applyHistoryFilterAndSort);

    // Clickable header for date sorting
    document.getElementById("thDateSort")?.addEventListener("click", () => {
        const sortSelect = document.getElementById("historyDateSort");
        if (!sortSelect) return;
        if (sortSelect.value === "date-desc") {
            sortSelect.value = "date-asc";
        } else {
            sortSelect.value = "date-desc";
        }
        applyHistoryFilterAndSort();
    });
}

// History table loading from API
async function loadRecentLessons() {
    try {
        const res = await fetch("/api/lessons?limit=200");
        if (!res.ok) return;
        allLessonsData = await res.json();

        const badge = document.getElementById("historyCountBadge");
        if (badge) badge.textContent = allLessonsData.length;

        updateSubjectFilterDropdown();
        applyHistoryFilterAndSort();
    } catch (e) {
        console.error("Błąd ładowania historii:", e);
    }
}

// Open lesson: hides upload grid and live status, displays only the opened lesson
window.openLessonFromHistory = (id) => {
    // Switch to first tab pane
    isOpeningFromHistory = true;
    const uploadTabBtn = document.querySelector('.nav-item[data-tab="tab-upload"]');
    if (uploadTabBtn) uploadTabBtn.click();
    isOpeningFromHistory = false;

    showLessonView();
    loadLessonDetails(id);
};

// Delete lesson
window.deleteLessonRecord = async (id) => {
    if (!confirm("Czy na pewno chcesz usunąć tę lekcję?")) return;
    try {
        const res = await fetch(`/api/lessons/${id}`, { method: "DELETE" });
        if (res.ok) {
            showToast("Lekcja została usunięta.", "success");
            loadRecentLessons();
            if (currentLessonId === id) {
                showUploadView();
            }
        }
    } catch (e) {
        showToast("Błąd podczas usuwania.", "error");
    }
};

// Settings Load & Save
async function loadSettings() {
    try {
        const res = await fetch("/api/settings");
        if (!res.ok) return;
        const s = await res.json();

        // Populate fields
        document.getElementById("setEngine").value = s.transcription_engine || "faster-whisper";
        document.getElementById("setModel").value = s.whisper_model || "large-v3";
        document.getElementById("setDevice").value = s.whisper_device || "auto";
        document.getElementById("setCompute").value = s.whisper_compute_type || "auto";
        document.getElementById("setLanguage").value = s.whisper_language || "pl";

        document.getElementById("setNimModel").value = s.nvidia_nim_model || "";
        document.getElementById("setNimApiKey").value = s.nvidia_api_key || "";
        document.getElementById("setNimBaseUrl").value = s.nvidia_base_url || "";
        document.getElementById("setNimTemp").value = s.nvidia_temperature ?? 0.2;
        document.getElementById("tempValueDisplay").textContent = Number(s.nvidia_temperature ?? 0.2).toFixed(2);

        document.getElementById("setAutoAddCalendar").checked = Boolean(s.google_calendar_auto_add);
        document.getElementById("setDeleteSource").checked = Boolean(s.delete_source_after_processing);

        // Update sidebar label
        const sideConfig = document.getElementById("sidebarConfigInfo");
        if (sideConfig) {
            sideConfig.textContent = `${s.transcription_engine} • NVIDIA NIM`;
        }

        loadCalendarStatus();
    } catch (e) {
        console.error("Błąd ładowania ustawień:", e);
    }
}

async function loadCalendarStatus() {
    try {
        const res = await fetch("/api/calendar/status");
        if (!res.ok) return;
        const cal = await res.json();

        const dot = document.getElementById("calStatusDot");
        const text = document.getElementById("calStatusText");
        const email = document.getElementById("calUserEmail");
        const connectBtn = document.getElementById("connectGoogleBtn");
        const disconnectBtn = document.getElementById("disconnectGoogleBtn");

        if (cal.is_connected) {
            dot.className = "dot-online";
            text.textContent = "Połączono z Google Calendar";
            email.textContent = cal.email ? `Zalogowano jako: ${cal.email}` : "";
            connectBtn.classList.add("hidden");
            disconnectBtn.classList.remove("hidden");
        } else {
            dot.className = "dot-offline";
            text.textContent = "Nie połączono";
            email.textContent = cal.is_configured ? "Gotowy do autoryzacji OAuth" : "Wymaga ustawienia GOOGLE_CLIENT_ID w .env";
            connectBtn.classList.remove("hidden");
            disconnectBtn.classList.add("hidden");
        }
    } catch (e) {
        console.error("Błąd statusu kalendarza:", e);
    }
}

function initSettingsForm() {
    const tempSlider = document.getElementById("setNimTemp");
    const tempVal = document.getElementById("tempValueDisplay");
    if (tempSlider && tempVal) {
        tempSlider.addEventListener("input", (e) => {
            tempVal.textContent = Number(e.target.value).toFixed(2);
        });
    }

    const form = document.getElementById("settingsForm");
    if (form) {
        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            const payload = {
                transcription_engine: document.getElementById("setEngine").value,
                whisper_model: document.getElementById("setModel").value,
                whisper_device: document.getElementById("setDevice").value,
                whisper_compute_type: document.getElementById("setCompute").value,
                whisper_language: document.getElementById("setLanguage").value,
                nvidia_nim_model: document.getElementById("setNimModel").value,
                nvidia_api_key: document.getElementById("setNimApiKey").value,
                nvidia_base_url: document.getElementById("setNimBaseUrl").value,
                nvidia_temperature: parseFloat(document.getElementById("setNimTemp").value),
                google_calendar_auto_add: document.getElementById("setAutoAddCalendar").checked,
                delete_source_after_processing: document.getElementById("setDeleteSource").checked
            };

            try {
                const res = await fetch("/api/settings", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });

                if (!res.ok) throw new Error("Błąd zapisu ustawień.");
                showToast("Ustawienia zostały pomyślnie zapisane!", "success");
                loadSettings();
            } catch (err) {
                showToast(err.message, "error");
            }
        });
    }
}
