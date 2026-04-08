(function () {
    const configElement = document.getElementById("directory-page-config");
    if (!configElement) {
        return;
    }

    const DUMMY_UUID = "00000000-0000-0000-0000-000000000000";
    const config = JSON.parse(configElement.textContent);
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";

    const elements = {
        summaryTotal: document.getElementById("summary-total"),
        summaryApproved: document.getElementById("summary-approved"),
        summaryActive: document.getElementById("summary-active"),
        summaryAssigned: document.getElementById("summary-assigned"),
        summaryNeedsSetup: document.getElementById("summary-needs-setup"),
        loadingState: document.getElementById("directory-loading-state"),
        emptyState: document.getElementById("directory-empty-state"),
        errorState: document.getElementById("directory-error-state"),
        errorMessage: document.getElementById("directory-error-message"),
        retryButton: document.getElementById("directory-retry-button"),
        tableWrap: document.getElementById("directory-table-wrap"),
        tableBody: document.getElementById("directory-table-body"),
        feedbackBanner: document.getElementById("directory-feedback-banner"),
    };

    const state = {
        data: null,
        loading: false,
        error: "",
        actionById: {},
        bannerTimer: null,
    };

    function escapeHtml(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#39;");
    }

    function formatDate(dateString) {
        if (!dateString) {
            return "Not available";
        }
        const date = new Date(dateString);
        return new Intl.DateTimeFormat(undefined, {
            year: "numeric",
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit",
        }).format(date);
    }

    function statusClass(status) {
        const normalized = String(status || "").trim().toLowerCase().replaceAll("_", "-");
        if (normalized === "needs-setup") {
            return "needs-setup";
        }
        if (["pending", "approved", "rejected", "inactive", "active"].includes(normalized)) {
            return normalized;
        }
        return "inactive";
    }

    function setBanner(message, tone) {
        if (state.bannerTimer) {
            window.clearTimeout(state.bannerTimer);
            state.bannerTimer = null;
        }

        if (!message) {
            elements.feedbackBanner.className = "alert hidden";
            elements.feedbackBanner.textContent = "";
            return;
        }

        elements.feedbackBanner.className = `alert alert--${tone}`;
        elements.feedbackBanner.textContent = message;
        state.bannerTimer = window.setTimeout(() => {
            setBanner("", tone);
        }, 3500);
    }

    function renderSummary() {
        if (!state.data) {
            return;
        }

        if (config.kind === "coaches") {
            elements.summaryTotal.textContent = String(state.data.summary.total_coaches ?? 0);
            elements.summaryApproved.textContent = String(state.data.summary.approved_coaches ?? 0);
            elements.summaryActive.textContent = String(state.data.summary.active_coaches ?? 0);
            return;
        }

        elements.summaryTotal.textContent = String(state.data.summary.total_players ?? 0);
        elements.summaryAssigned.textContent = String(state.data.summary.assigned_players ?? 0);
        elements.summaryNeedsSetup.textContent = String(state.data.summary.needs_setup_players ?? 0);
    }

    function buildCoachRow(row) {
        const busy = Boolean(state.actionById[row.id]);
        const actionLabel = row.is_active ? "Disable" : "Activate";
        const loadingLabel = row.is_active ? "Disabling..." : "Activating...";
        const certificateButton = row.certificate_url
            ? `<a class="button button--secondary button--inline" href="${escapeHtml(row.certificate_url)}" target="_blank" rel="noopener noreferrer">View Certificate</a>`
            : "";

        return `
            <tr>
                <td data-label="Coach">
                    <p class="coach-name">${escapeHtml(row.full_name)}</p>
                </td>
                <td data-label="Contact">
                    <p class="coach-name">${escapeHtml(row.email)}</p>
                    <div class="coach-meta">${escapeHtml(row.phone_number || "Phone not provided")}</div>
                </td>
                <td data-label="Status">
                    <span class="status-chip status-chip--${statusClass(row.status)}">${escapeHtml(row.status)}</span>
                </td>
                <td data-label="Players">${escapeHtml(row.player_count)}</td>
                <td data-label="Joined">${escapeHtml(formatDate(row.joined_at))}</td>
                <td data-label="Actions">
                    <div class="row-actions row-actions--stacked">
                        ${certificateButton}
                        <button
                            type="button"
                            class="button ${row.is_active ? "button--danger" : "button--success"} button--inline"
                            data-action="toggle-active"
                            data-id="${row.id}"
                            ${busy ? "disabled" : ""}
                        >
                            ${busy ? loadingLabel : actionLabel}
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }

    function buildPlayerRow(row) {
        return `
            <tr>
                <td data-label="Player">
                    <p class="coach-name">${escapeHtml(row.full_name)}</p>
                </td>
                <td data-label="Email">${escapeHtml(row.email)}</td>
                <td data-label="Assigned Coach">${escapeHtml(row.assigned_coach || "Unassigned")}</td>
                <td data-label="Status">
                    <span class="status-chip status-chip--${statusClass(row.status)}">${escapeHtml(row.status)}</span>
                </td>
                <td data-label="Joined">${escapeHtml(formatDate(row.joined_at))}</td>
            </tr>
        `;
    }

    function renderTable() {
        const rows = config.kind === "coaches" ? (state.data?.coaches || []) : (state.data?.players || []);
        elements.tableBody.innerHTML = rows.map((row) => (
            config.kind === "coaches" ? buildCoachRow(row) : buildPlayerRow(row)
        )).join("");
    }

    function render() {
        const rows = config.kind === "coaches" ? (state.data?.coaches || []) : (state.data?.players || []);
        renderSummary();

        elements.loadingState.classList.toggle("hidden", !state.loading || Boolean(rows.length) || Boolean(state.error));
        elements.errorState.classList.toggle("hidden", !state.error);
        elements.emptyState.classList.toggle("hidden", state.loading || Boolean(state.error) || Boolean(rows.length));
        elements.tableWrap.classList.toggle("hidden", !rows.length);

        if (state.error) {
            elements.errorMessage.textContent = state.error;
        }

        if (rows.length) {
            renderTable();
        } else {
            elements.tableBody.innerHTML = "";
        }
    }

    async function refreshData(options = {}) {
        if (state.loading) {
            return;
        }

        state.loading = true;
        state.error = "";
        if (options.showBlockingState) {
            render();
        }

        try {
            const response = await fetch(config.dataUrl, {
                headers: { "X-Requested-With": "XMLHttpRequest" },
                credentials: "same-origin",
            });

            if (!response.ok) {
                throw new Error("The admin panel could not refresh this list.");
            }

            state.data = await response.json();
        } catch (error) {
            state.error = error.message || "The admin panel could not refresh this list.";
        } finally {
            state.loading = false;
            render();
        }
    }

    async function toggleCoachActive(coachId) {
        if (!config.toggleUrlTemplate || state.actionById[coachId]) {
            return;
        }

        state.actionById[coachId] = true;
        render();
        const url = config.toggleUrlTemplate.replace(DUMMY_UUID, coachId);

        try {
            const response = await fetch(url, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "X-CSRFToken": csrfToken,
                    "X-Requested-With": "XMLHttpRequest",
                },
            });

            if (!response.ok) {
                throw new Error("Could not update this coach.");
            }

            const payload = await response.json();
            setBanner(
                payload.is_active ? "Coach activated successfully." : "Coach disabled successfully.",
                payload.is_active ? "success" : "error"
            );
            await refreshData();
        } catch (error) {
            setBanner(error.message || "Something went wrong while updating the coach.", "error");
        } finally {
            delete state.actionById[coachId];
            render();
        }
    }

    if (config.kind === "coaches") {
        elements.tableBody.addEventListener("click", (event) => {
            const button = event.target.closest("[data-action='toggle-active']");
            if (!button) {
                return;
            }
            toggleCoachActive(button.dataset.id);
        });
    }

    elements.retryButton.addEventListener("click", () => refreshData({ showBlockingState: true }));

    render();
    refreshData({ showBlockingState: true });
})();
