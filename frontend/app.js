/* ============================================================================
   PulseSim: Client Application Logic (Vanilla JS)
   ============================================================================ */

const API_BASE = `${window.location.protocol}//${window.location.host}`;
const WS_BASE = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`;

// --- Application State ---
let simId = null;
let ws = null;
let currentCaseTitle = "";
let totalCostSpent = 0;
let isEnded = false;

// --- DOM References ---
const setupControls = document.getElementById("setupControls");
const activeControls = document.getElementById("activeControls");
const studentEmailInput = document.getElementById("studentEmail");
const caseSelect = document.getElementById("caseSelect");
const activeCaseTitle = document.getElementById("activeCaseTitle");

const btnStart = document.getElementById("btnStart");
const btnStop = document.getElementById("btnStop");
const btnRestart = document.getElementById("btnRestart");

// Telemetry Counters
const valHr = document.getElementById("valHr");
const valBp = document.getElementById("valBp");
const valSpo2 = document.getElementById("valSpo2");
const valTemp = document.getElementById("valTemp");
const valAnxiety = document.getElementById("valAnxiety");

const fillSpo2 = document.getElementById("fillSpo2");
const fillAnxiety = document.getElementById("fillAnxiety");

const cardHr = document.getElementById("cardHr");
const cardBp = document.getElementById("cardBp");
const cardSpo2 = document.getElementById("cardSpo2");
const cardTemp = document.getElementById("cardTemp");
const cardAnxiety = document.getElementById("cardAnxiety");

const descBp = document.getElementById("descBp");
const descTemp = document.getElementById("descTemp");

const valSimTime = document.getElementById("valSimTime");
const valBudget = document.getElementById("valBudget");
const vitalsStatus = document.getElementById("vitalsStatus");
const heartIcon = document.getElementById("heartIcon");

// Chat
const chatMessages = document.getElementById("chatMessages");
const chatInput = document.getElementById("chatInput");
const btnSend = document.getElementById("btnSend");

// Interventions
const tabButtons = document.querySelectorAll(".tab-btn");
const tabContents = document.querySelectorAll(".tab-content");
const interventionButtons = document.querySelectorAll(".int-btn");

// Modal
const modalSummary = document.getElementById("modalSummary");
const summarySimId = document.getElementById("summarySimId");
const summaryCase = document.getElementById("summaryCase");
const summaryStatus = document.getElementById("summaryStatus");
const summaryCost = document.getElementById("summaryCost");
const summaryTime = document.getElementById("summaryTime");

const gradeAccuracy = document.getElementById("gradeAccuracy");
const valGradeAccuracy = document.getElementById("valGradeAccuracy");
const gradeEmpathy = document.getElementById("gradeEmpathy");
const valGradeEmpathy = document.getElementById("valGradeEmpathy");
const gradeResource = document.getElementById("gradeResource");
const valGradeResource = document.getElementById("valGradeResource");

// Toast
const toast = document.getElementById("toast");
const toastMessage = document.getElementById("toastMessage");

// --- Event Listeners ---
window.addEventListener("DOMContentLoaded", checkSessionRecovery);
btnStart.addEventListener("click", handleStartSimulation);
btnStop.addEventListener("click", () => handleEndSimulation(false));
btnSend.addEventListener("click", handleSendChat);
chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleSendChat();
});
btnRestart.addEventListener("click", resetApplication);

// Tab Navigation
tabButtons.forEach(btn => {
    btn.addEventListener("click", () => {
        tabButtons.forEach(b => b.classList.remove("active"));
        tabContents.forEach(c => c.classList.remove("active"));
        
        btn.classList.add("active");
        const tabId = `tab-${btn.dataset.tab}`;
        document.getElementById(tabId).classList.add("active");
    });
});

// Intervention Buttons
interventionButtons.forEach(btn => {
    btn.addEventListener("click", () => {
        const id = btn.dataset.id;
        executeIntervention(id);
    });
});

// --- State Recovery ---
async function checkSessionRecovery() {
    const savedSimId = localStorage.getItem("pulsesim_sim_id");
    const savedCaseTitle = localStorage.getItem("pulsesim_case_title");
    
    if (savedSimId && savedCaseTitle) {
        showToast("Attempting simulation state recovery...", "info");
        try {
            const res = await fetch(`${API_BASE}/api/simulation/${savedSimId}/state`);
            if (res.ok) {
                const data = await res.json();
                simId = savedSimId;
                currentCaseTitle = savedCaseTitle;
                
                // If it recovered but was already failed/completed
                if (data.status !== "running") {
                    localStorage.removeItem("pulsesim_sim_id");
                    localStorage.removeItem("pulsesim_case_title");
                    return;
                }
                
                resumeActiveState(data);
            } else {
                localStorage.removeItem("pulsesim_sim_id");
                localStorage.removeItem("pulsesim_case_title");
            }
        } catch (err) {
            console.error("Recovery failed:", err);
        }
    }
}

// --- Start Simulation ---
async function handleStartSimulation() {
    const email = studentEmailInput.value.trim();
    const caseId = caseSelect.value;
    
    if (!email) {
        showToast("Please enter a valid student email.", "warning");
        return;
    }
    
    btnStart.disabled = true;
    appendSystemMessage("Connecting to Neo4j and launching simulation state...", "info");
    
    try {
        const response = await fetch(`${API_BASE}/api/simulation/start`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_email: email, case_id: caseId })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || "Server failed to initiate case.");
        }
        
        const data = await response.json();
        simId = data.simulation_id;
        currentCaseTitle = data.case.title;
        
        // Cache parameters locally
        localStorage.setItem("pulsesim_sim_id", simId);
        localStorage.setItem("pulsesim_case_title", currentCaseTitle);
        
        // UI Layout Adjustments
        setupControls.classList.add("hidden");
        activeControls.classList.remove("hidden");
        activeCaseTitle.innerText = `${currentCaseTitle} (${data.case.difficulty})`;
        
        // Clear old logs and messages
        chatMessages.innerHTML = "";
        appendSystemMessage(`Case Started: ${currentCaseTitle}. Clinical records retrieved.`, "info");
        appendPatientMessage(`Help me doctor... I am having severe symptoms.`, false);
        
        // Enable Controls
        enableControls(true);
        
        // Connect to Stream
        initWebSocket(simId);
        showToast("Simulation Active. Monitor telemetry.", "success");
    } catch (err) {
        console.error(err);
        appendSystemMessage(`Error initiating case: ${err.message}`, "error");
        btnStart.disabled = false;
    }
}

function resumeActiveState(stateData) {
    simId = stateData.sim_id;
    setupControls.classList.add("hidden");
    activeControls.classList.remove("hidden");
    activeCaseTitle.innerText = currentCaseTitle;
    
    chatMessages.innerHTML = "";
    appendSystemMessage(`Resumed active session ${simId.substring(0,8)}...`, "info");
    
    enableControls(true);
    updateTelemetryUI(stateData);
    initWebSocket(simId);
}

// --- Live Websocket Channels ---
function initWebSocket(simId) {
    if (ws) ws.close();
    
    const wsUrl = `${WS_BASE}/ws/sim/${simId}`;
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        vitalsStatus.innerText = "STREAM ONLINE";
        vitalsStatus.className = "status-indicator";
        vitalsStatus.style.borderColor = "var(--color-safe)";
        vitalsStatus.style.color = "var(--color-safe)";
    };
    
    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.type === "vitals_update") {
            updateTelemetryUI(message);
        } else if (message.type === "simulation_ended") {
            handleEndSimulation(true, message.reason);
        }
    };
    
    ws.onclose = () => {
        if (!isEnded) {
            vitalsStatus.innerText = "STREAM RECONNECTING";
            vitalsStatus.className = "status-indicator blinking";
            vitalsStatus.style.borderColor = "var(--color-warning)";
            vitalsStatus.style.color = "var(--color-warning)";
            setTimeout(() => initWebSocket(simId), 2000);
        } else {
            vitalsStatus.innerText = "STREAM CLOSED";
            vitalsStatus.style.borderColor = "var(--border-card)";
            vitalsStatus.style.color = "var(--text-muted)";
        }
    };
}

// --- Render Telemetry UI ---
function updateTelemetryUI(data) {
    // 1. Heart Rate
    valHr.innerText = Math.round(data.vitals_hr);
    applyVitalColorState(cardHr, data.vitals_hr, 60, 100, 50, 120);
    
    // Adjust heart icon animation speed based on HR
    const heartSecs = Math.max(0.3, Math.min(2.0, 60 / data.vitals_hr));
    heartIcon.style.animationDuration = `${heartSecs}s`;
    
    // 2. Blood Pressure
    const sys = Math.round(data.vitals_bps);
    const dia = Math.round(data.vitals_bpd);
    valBp.innerText = `${sys}/${dia}`;
    applyVitalColorState(cardBp, sys, 90, 130, 80, 150);
    
    if (sys < 90) {
        descBp.innerText = "Status: Hypotensive Shock";
        descBp.style.color = "var(--color-critical)";
    } else if (sys > 140) {
        descBp.innerText = "Status: Hypertensive Urgency";
        descBp.style.color = "var(--color-warning)";
    } else {
        descBp.innerText = "Status: Stable";
        descBp.style.color = "var(--color-safe)";
    }
    
    // 3. SpO2
    valSpo2.innerText = Math.round(data.vitals_spo2);
    fillSpo2.style.width = `${data.vitals_spo2}%`;
    applyVitalColorState(cardSpo2, data.vitals_spo2, 95, 100, 90, 100);
    if (data.vitals_spo2 < 90) {
        fillSpo2.className = "progress-bar-fill progress-bar-red";
    } else {
        fillSpo2.className = "progress-bar-fill";
    }
    
    // 4. Temperature
    valTemp.innerText = data.vitals_temp.toFixed(1);
    applyVitalColorState(cardTemp, data.vitals_temp, 36.5, 37.5, 35.5, 38.5);
    if (data.vitals_temp > 38.0) {
        descTemp.innerText = "Status: Febrile / Pyrexia";
        descTemp.style.color = "var(--color-warning)";
    } else if (data.vitals_temp < 36.0) {
        descTemp.innerText = "Status: Hypothermic";
        descTemp.style.color = "var(--color-warning)";
    } else {
        descTemp.innerText = "Status: Normothermic";
        descTemp.style.color = "var(--color-safe)";
    }
    
    // 5. Anxiety
    valAnxiety.innerText = Math.round(data.anxiety);
    fillAnxiety.style.width = `${data.anxiety}%`;
    applyVitalColorState(cardAnxiety, data.anxiety, 0, 40, 0, 75);
    
    // 6. Footer clock/budget
    valSimTime.innerText = `${data.elapsed_seconds} sec (Sim: ${data.simulated_minutes} mins)`;
    valBudget.innerText = `$${data.budget_remaining.toFixed(2)}`;
    totalCostSpent = 1000 - data.budget_remaining;
}

function applyVitalColorState(cardElement, val, normalMin, normalMax, warningMin, warningMax) {
    cardElement.classList.remove("card-safe", "card-warning", "card-critical");
    
    if (val >= normalMin && val <= normalMax) {
        cardElement.classList.add("card-safe");
    } else if (val >= warningMin && val <= warningMax) {
        cardElement.classList.add("card-warning");
    } else {
        cardElement.classList.add("card-critical");
    }
}

// --- Execute Clinical Intervention ---
async function executeIntervention(interventionId) {
    if (!simId) return;
    
    showToast(`Ordering ${interventionId.replace(/_/g, " ")}...`, "info");
    
    try {
        const response = await fetch(`${API_BASE}/api/simulation/${simId}/intervention`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ intervention_id: interventionId })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || "Intervention failed.");
        }
        
        const data = await response.json();
        showToast(`${data.display_name} executed!`, "success");
        appendSystemMessage(`[Intervention] ${data.display_name} (Cost: $${data.cost.toFixed(2)}, Time Penalty: +${data.time_penalty_minutes}m)`, "info");
        
    } catch (err) {
        console.error(err);
        showToast(err.message, "danger");
        appendSystemMessage(`Failed to execute intervention: ${err.message}`, "error");
    }
}

// --- Dialogue Conversational Channel ---
async function handleSendChat() {
    const text = chatInput.value.trim();
    if (!text || !simId) return;
    
    chatInput.value = "";
    appendStudentMessage(text);
    
    // Fallback: until Phase 3 LLM agent orchestrator is built, we check if endpoint exists.
    // If not, we generate a mock patient response based on the active case.
    try {
        const chatRes = await fetch(`${API_BASE}/api/simulation/${simId}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text })
        });
        
        if (chatRes.ok) {
            const responseData = await chatRes.json();
            appendPatientMessage(responseData.reply, responseData.distressed);
        } else {
            // Mock clinical dialog responses to maintain user interactivity
            generateMockPatientResponse(text);
        }
    } catch (err) {
        generateMockPatientResponse(text);
    }
}

function generateMockPatientResponse(text) {
    const isAnaphylaxis = currentCaseTitle.toLowerCase().includes("respiratory") || currentCaseTitle.toLowerCase().includes("anaphylaxis");
    let reply = "";
    let distressed = false;

    if (isAnaphylaxis) {
        distressed = true;
        const lowered = text.toLowerCase();
        if (lowered.includes("breathe") || lowered.includes("chest") || lowered.includes("throat")) {
            reply = "My... throat is... closing up... can't get... air...";
        } else if (lowered.includes("allergy") || lowered.includes("allerge") || lowered.includes("eat")) {
            reply = "I had... a peanut cookie... a few minutes... ago...";
        } else if (lowered.includes("pain") || lowered.includes("hurt")) {
            reply = "Just chest... tight... skin is itching... so bad...";
        } else {
            reply = "Help... please... dizzy... can't... breathe...";
        }
    } else {
        // Appendicitis
        const lowered = text.toLowerCase();
        if (lowered.includes("hurt") || lowered.includes("pain") || lowered.includes("where")) {
            reply = "It's my right side, down low. It hurts so bad if you touch it, or even if I move my leg.";
        } else if (lowered.includes("nausea") || lowered.includes("throw up") || lowered.includes("vomit")) {
            reply = "Yeah, I threw up once this morning. I feel really nauseous and don't want to eat anything.";
        } else if (lowered.includes("fever") || lowered.includes("hot")) {
            reply = "I feel hot and shivery. I think I have a temperature.";
        } else {
            reply = "My stomach is just in agony. Is there something you can give me for the pain?";
        }
    }

    setTimeout(() => {
        appendPatientMessage(reply, distressed);
    }, 800);
}

// --- Close & Grade Session ---
async function handleEndSimulation(isVitalsFailure, failureReason = "") {
    if (!simId) return;
    
    isEnded = true;
    enableControls(false);
    
    if (ws) {
        ws.close();
        ws = null;
    }
    
    // UI clean cache
    localStorage.removeItem("pulsesim_sim_id");
    localStorage.removeItem("pulsesim_case_title");
    
    let outcome = "Completed";
    if (isVitalsFailure) {
        outcome = "Failed (Patient Coded)";
    }
    
    // Prepare mock/local metrics if the server doesn't support the full grading pipeline yet.
    // This allows complete demonstration of the PDF / grading requirements in PRD.
    const mockGrading = calculateMockGrades(isVitalsFailure);

    // Populate modal values
    summarySimId.innerText = simId;
    summaryCase.innerText = currentCaseTitle;
    summaryStatus.innerText = outcome;
    if (isVitalsFailure) {
        summaryStatus.style.color = "var(--color-critical)";
        summaryStatus.innerText += ` - ${failureReason}`;
    } else {
        summaryStatus.style.color = "var(--color-safe)";
    }
    
    summaryCost.innerText = `$${totalCostSpent.toFixed(2)} / $1,000.00`;
    summaryTime.innerText = valSimTime.innerText;
    
    // Set Grades
    gradeAccuracy.style.width = `${mockGrading.accuracy * 100}%`;
    valGradeAccuracy.innerText = `${(mockGrading.accuracy * 100).toFixed(0)}%`;
    
    gradeEmpathy.style.width = `${mockGrading.empathy * 100}%`;
    valGradeEmpathy.innerText = `${(mockGrading.empathy * 100).toFixed(0)}%`;
    
    gradeResource.style.width = `${mockGrading.resource * 100}%`;
    valGradeResource.innerText = `${(mockGrading.resource * 100).toFixed(0)}%`;

    // Show modal
    modalSummary.classList.remove("hidden");
}

function calculateMockGrades(isVitalsFailure) {
    if (isVitalsFailure) {
        return { accuracy: 0.1, empathy: 0.5, resource: 0.8 };
    }
    
    // If successful, grade based on cost efficiency
    let accuracy = 1.0;
    let empathy = 0.85;
    
    // Less spent = higher financial score
    let resource = Math.max(0.3, 1.0 - (totalCostSpent / 1000));
    
    return { accuracy, empathy, resource };
}

function resetApplication() {
    modalSummary.classList.add("hidden");
    resetUI();
}

function resetUI() {
    simId = null;
    isEnded = false;
    currentCaseTitle = "";
    totalCostSpent = 0;
    
    activeControls.classList.add("hidden");
    setupControls.classList.remove("hidden");
    btnStart.disabled = false;
    
    // Vitals Reset
    valHr.innerText = "--";
    valBp.innerText = "--/--";
    valSpo2.innerText = "--";
    valTemp.innerText = "--";
    valAnxiety.innerText = "--";
    fillSpo2.style.width = "0%";
    fillAnxiety.style.width = "0%";
    
    cardHr.className = "vital-card";
    cardBp.className = "vital-card";
    cardSpo2.className = "vital-card";
    cardTemp.className = "vital-card";
    cardAnxiety.className = "vital-card full-width";
    
    valSimTime.innerText = "0 seconds";
    valBudget.innerText = "$1,000.00";
    vitalsStatus.innerText = "Awaiting Sim...";
    vitalsStatus.className = "status-indicator";
    vitalsStatus.style.borderColor = "var(--border-card)";
    vitalsStatus.style.color = "var(--text-muted)";
    
    chatMessages.innerHTML = `
        <div class="message system-msg">
            <i class="fa-solid fa-circle-info"></i> Enter a student email and select a clinical case to begin the simulation.
        </div>
    `;
    
    enableControls(false);
}

// --- Helpers ---
function enableControls(enabled) {
    chatInput.disabled = !enabled;
    btnSend.disabled = !enabled;
    interventionButtons.forEach(btn => {
        btn.disabled = !enabled;
    });
}

function appendStudentMessage(text) {
    const msg = document.createElement("div");
    msg.className = "message student-msg";
    msg.innerText = text;
    chatMessages.appendChild(msg);
    scrollChat();
}

function appendPatientMessage(text, distressed = false) {
    const msg = document.createElement("div");
    msg.className = `message patient-msg ${distressed ? "distressed" : ""}`;
    msg.innerHTML = `<strong>Patient:</strong> ${text}`;
    chatMessages.appendChild(msg);
    scrollChat();
}

function appendSystemMessage(text, type = "info") {
    const msg = document.createElement("div");
    msg.className = `message system-msg ${type === "error" ? "system-msg-error" : ""}`;
    msg.innerHTML = `<i class="fa-solid fa-circle-info"></i> ${text}`;
    chatMessages.appendChild(msg);
    scrollChat();
}

function scrollChat() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showToast(message, type = "info") {
    toastMessage.innerText = message;
    toast.className = `toast ${type}`;
    
    // Choose icon
    const icon = document.getElementById("toastIcon");
    icon.className = "fa-solid toast-icon";
    if (type === "success") icon.classList.add("fa-circle-check");
    else if (type === "warning") icon.classList.add("fa-triangle-exclamation");
    else if (type === "danger") icon.classList.add("fa-circle-xmark");
    else icon.classList.add("fa-circle-info");
    
    toast.classList.remove("hidden");
    
    // Fade out
    setTimeout(() => {
        toast.classList.add("hidden");
    }, 3000);
}
