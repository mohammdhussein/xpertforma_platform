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
        certificateModal: document.getElementById("directory-certificate-modal"),
        certificateImage: document.getElementById("directory-certificate-image"),
        certificateEmpty: document.getElementById("directory-certificate-empty"),
        certificateOpenLink: document.getElementById("directory-certificate-open-link"),
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

    function initials(value) {
        return String(value || "?")
            .trim()
            .split(/\s+/)
            .slice(0, 2)
            .map((part) => part[0]?.toUpperCase() || "")
            .join("") || "?";
    }

    function statusBadge(status) {
        const normalized = statusClass(status);
        const label = String(status || "")
            .trim()
            .replaceAll("_", " ")
            .replaceAll("-", " ")
            .toLowerCase()
            .replace(/\b\w/g, (letter) => letter.toUpperCase());
        return `
            <span class="status-pill status-pill--${normalized}">
                <span class="status-pill__dot"></span>
                ${escapeHtml(label)}
            </span>
        `;
    }

    function buildIdentityCell(name, meta) {
        return `
            <div class="entity-cell">
                <span class="entity-avatar">${escapeHtml(initials(name))}</span>
                <span class="entity-cell__text">
                    <strong>${escapeHtml(name || "Unnamed")}</strong>
                    ${meta ? `<small>${escapeHtml(meta)}</small>` : ""}
                </span>
            </div>
        `;
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
        const certificateButton = row.certificate_url
            ? `<button type="button" class="table-icon-button table-icon-button--primary" aria-label="View certificate for ${escapeHtml(row.full_name)}" title="View certificate" data-action="view-certificate" data-certificate-url="${escapeHtml(row.certificate_url)}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg></button>`
            : `<span class="muted-value">Not provided</span>`;

        return `
            <tr>
                <td data-label="Coach">
                    ${buildIdentityCell(row.full_name)}
                </td>
                <td data-label="Contact">
                    <span class="table-meta">${escapeHtml(row.phone_number || "Phone not provided")}</span>
                </td>
                <td data-label="Certificate">${certificateButton}</td>
                <td data-label="Status">
                    ${statusBadge(row.status)}
                </td>
                <td data-label="Players"><strong class="table-number">${escapeHtml(row.player_count)}</strong></td>
                <td data-label="Joined">${escapeHtml(formatDate(row.joined_at))}</td>
                <td data-label="Actions">
                    <div class="table-icon-actions">
                        <button
                            type="button"
                            class="table-icon-button ${row.is_active ? "table-icon-button--danger" : "table-icon-button--success"}"
                            aria-label="${actionLabel} ${escapeHtml(row.full_name)}"
                            title="${actionLabel}"
                            data-action="toggle-active"
                            data-id="${row.id}"
                            ${busy ? "disabled" : ""}
                        >
                            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2v10"/><path d="M18.4 6.6a9 9 0 1 1-12.8 0"/></svg>
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
                    ${buildIdentityCell(row.full_name)}
                </td>
                <td data-label="Email"><span class="table-meta">${escapeHtml(row.email)}</span></td>
                <td data-label="Assigned Coach">${row.assigned_coach ? escapeHtml(row.assigned_coach) : `<span class="muted-value">Unassigned</span>`}</td>
                <td data-label="Status">
                    ${statusBadge(row.status)}
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

    function openCertificateModal(url) {
        if (!elements.certificateModal || !elements.certificateImage || !elements.certificateEmpty || !elements.certificateOpenLink) {
            return;
        }

        elements.certificateModal.classList.remove("hidden");
        elements.certificateModal.setAttribute("aria-hidden", "false");

        if (url) {
            elements.certificateImage.src = url;
            elements.certificateImage.classList.remove("hidden");
            elements.certificateOpenLink.href = url;
            elements.certificateOpenLink.classList.remove("hidden");
            elements.certificateEmpty.classList.add("hidden");
            return;
        }

        elements.certificateImage.removeAttribute("src");
        elements.certificateImage.classList.add("hidden");
        elements.certificateOpenLink.removeAttribute("href");
        elements.certificateOpenLink.classList.add("hidden");
        elements.certificateEmpty.classList.remove("hidden");
    }

    function closeCertificateModal() {
        if (!elements.certificateModal || !elements.certificateImage) {
            return;
        }

        elements.certificateModal.classList.add("hidden");
        elements.certificateModal.setAttribute("aria-hidden", "true");
        elements.certificateImage.removeAttribute("src");
    }

    if (config.kind === "coaches") {
        elements.tableBody.addEventListener("click", (event) => {
            const button = event.target.closest("[data-action]");
            if (!button) {
                return;
            }

            if (button.dataset.action === "view-certificate") {
                openCertificateModal(button.dataset.certificateUrl || "");
                return;
            }

            if (button.dataset.action === "toggle-active") {
                toggleCoachActive(button.dataset.id);
            }
        });
    }

    elements.certificateModal?.addEventListener("click", (event) => {
        if (event.target.dataset.closeDirectoryCertificate === "true") {
            closeCertificateModal();
        }
    });
    elements.certificateImage?.addEventListener("error", () => {
        openCertificateModal("");
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeCertificateModal();
        }
    });

    elements.retryButton.addEventListener("click", () => refreshData({ showBlockingState: true }));

    render();
    refreshData({ showBlockingState: true });
})();
