(function () {
    const initialDataElement = document.getElementById("coach-requests-initial-data");
    const configElement = document.getElementById("coach-requests-config");
    if (!initialDataElement || !configElement) {
        return;
    }

    const DUMMY_UUID = "00000000-0000-0000-0000-000000000000";
    const initialData = JSON.parse(initialDataElement.textContent);
    const config = JSON.parse(configElement.textContent);
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";

    const elements = {
        pendingCount: document.getElementById("pending-count"),
        approvedCount: document.getElementById("approved-count"),
        lastUpdated: document.getElementById("last-updated"),
        loadingState: document.getElementById("loading-state"),
        emptyState: document.getElementById("empty-state"),
        errorState: document.getElementById("error-state"),
        errorMessage: document.getElementById("error-message"),
        tableWrap: document.getElementById("table-wrap"),
        tableBody: document.getElementById("requests-table-body"),
        feedbackBanner: document.getElementById("feedback-banner"),
        refreshButton: document.getElementById("refresh-button"),
        retryButton: document.getElementById("retry-button"),
        certificateModal: document.getElementById("certificate-modal"),
        certificateImage: document.getElementById("certificate-image"),
        certificateEmpty: document.getElementById("certificate-empty"),
        certificateOpenLink: document.getElementById("certificate-open-link"),
        closeModalButton: document.getElementById("close-modal-button"),
    };

    const state = {
        data: initialData,
        loading: false,
        error: "",
        actionByCoachId: {},
        pollTimer: null,
        bannerTimer: null,
    };

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

    function formatLastUpdated(dateString) {
        if (!dateString) {
            return "Last updated just now";
        }
        const date = new Date(dateString);
        return `Last updated ${date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#39;");
    }

    function buildActionUrl(template, coachId) {
        return template.replace(DUMMY_UUID, coachId);
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

    function renderTableRows() {
        const requests = state.data?.requests || [];
        elements.tableBody.innerHTML = requests.map((request) => {
            const fullName = `${request.first_name || ""} ${request.last_name || ""}`.trim() || "Unnamed coach";
            const busyAction = state.actionByCoachId[request.id];
            const isBusy = Boolean(busyAction);
            const certificateButton = request.certificate_url
                ? `<button type="button" class="button button--secondary button--inline" data-action="view" data-id="${request.id}" data-certificate-url="${escapeHtml(request.certificate_url)}">View Certificate</button>`
                : `<span class="muted-value">Not provided</span>`;

            return `
                <tr>
                    <td data-label="Coach">
                        <p class="coach-name">${escapeHtml(fullName)}</p>
                    </td>
                    <td data-label="Contact">
                        <p class="coach-name">${escapeHtml(request.email)}</p>
                        <div class="coach-meta">${escapeHtml(request.phone_number || "Phone not provided")}</div>
                    </td>
                    <td data-label="Certificate">${certificateButton}</td>
                    <td data-label="Status">
                        <span class="status-chip status-chip--${request.status.toLowerCase()}">${escapeHtml(request.status)}</span>
                    </td>
                    <td data-label="Created">${escapeHtml(formatDate(request.created_at))}</td>
                    <td data-label="Actions">
                        <div class="row-actions">
                            <button type="button" class="button button--success button--inline" data-action="approve" data-id="${request.id}" ${isBusy ? "disabled" : ""}>${busyAction === "approve" ? "Approving..." : "Approve"}</button>
                            <button type="button" class="button button--danger button--inline" data-action="reject" data-id="${request.id}" ${isBusy ? "disabled" : ""}>${busyAction === "reject" ? "Rejecting..." : "Reject"}</button>
                        </div>
                    </td>
                </tr>
            `;
        }).join("");
    }

    function render() {
        const requests = state.data?.requests || [];

        elements.pendingCount.textContent = String(state.data?.summary?.pending_requests ?? 0);
        elements.approvedCount.textContent = String(state.data?.summary?.approved_coaches ?? 0);
        elements.lastUpdated.textContent = formatLastUpdated(state.data?.last_updated);
        elements.loadingState.classList.toggle("hidden", !state.loading || Boolean(requests.length) || Boolean(state.error));
        elements.errorState.classList.toggle("hidden", !state.error);
        elements.emptyState.classList.toggle("hidden", state.loading || Boolean(state.error) || Boolean(requests.length));
        elements.tableWrap.classList.toggle("hidden", !requests.length);

        if (state.error) {
            elements.errorMessage.textContent = state.error;
        }

        if (requests.length) {
            renderTableRows();
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
                throw new Error("The admin panel could not refresh. Please try again.");
            }

            state.data = await response.json();
        } catch (error) {
            state.error = error.message || "The admin panel could not refresh. Please try again.";
        } finally {
            state.loading = false;
            render();
        }
    }

    async function runAction(coachId, action) {
        if (state.actionByCoachId[coachId]) {
            return;
        }

        const confirmed = window.confirm(
            action === "approve"
                ? "Approve this coach request?"
                : "Reject this coach request?"
        );
        if (!confirmed) {
            return;
        }

        state.actionByCoachId[coachId] = action;
        render();

        const url = action === "approve"
            ? buildActionUrl(config.approveUrlTemplate, coachId)
            : buildActionUrl(config.rejectUrlTemplate, coachId);

        try {
            const response = await fetch(url, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: action === "reject" ? JSON.stringify({ reason: "" }) : JSON.stringify({}),
            });

            if (!response.ok) {
                throw new Error(`Could not ${action} this request.`);
            }

            setBanner(
                action === "approve"
                    ? "Coach approved successfully."
                    : "Coach request rejected successfully.",
                action === "approve" ? "success" : "error"
            );
            await refreshData();
        } catch (error) {
            setBanner(error.message || "Something went wrong while updating the request.", "error");
        } finally {
            delete state.actionByCoachId[coachId];
            render();
        }
    }

    function openCertificateModal(url) {
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
        elements.certificateModal.classList.add("hidden");
        elements.certificateModal.setAttribute("aria-hidden", "true");
        elements.certificateImage.removeAttribute("src");
    }

    function startPolling() {
        if (state.pollTimer) {
            return;
        }
        state.pollTimer = window.setInterval(() => {
            refreshData();
        }, config.pollIntervalMs || 5000);
    }

    function stopPolling() {
        if (!state.pollTimer) {
            if (state.bannerTimer) {
                window.clearTimeout(state.bannerTimer);
                state.bannerTimer = null;
            }
            return;
        }
        window.clearInterval(state.pollTimer);
        state.pollTimer = null;
        if (state.bannerTimer) {
            window.clearTimeout(state.bannerTimer);
            state.bannerTimer = null;
        }
    }

    elements.refreshButton.addEventListener("click", () => refreshData({ showBlockingState: true }));
    elements.retryButton.addEventListener("click", () => refreshData({ showBlockingState: true }));

    elements.tableBody.addEventListener("click", (event) => {
        const button = event.target.closest("[data-action]");
        if (!button) {
            return;
        }

        const action = button.dataset.action;
        const coachId = button.dataset.id;
        if (!coachId) {
            return;
        }

        if (action === "view") {
            openCertificateModal(button.dataset.certificateUrl || "");
            return;
        }

        runAction(coachId, action);
    });

    elements.closeModalButton.addEventListener("click", closeCertificateModal);
    elements.certificateModal.addEventListener("click", (event) => {
        if (event.target.dataset.closeModal === "true") {
            closeCertificateModal();
        }
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeCertificateModal();
        }
    });
    elements.certificateImage.addEventListener("error", () => {
        openCertificateModal("");
    });
    window.addEventListener("beforeunload", stopPolling);

    render();
    refreshData({ showBlockingState: true });
    startPolling();
})();
