(function () {
    const sidebar = document.getElementById("admin-sidebar");
    const openSidebarButton = document.querySelector("[data-sidebar-open]");
    const closeSidebarTargets = document.querySelectorAll("[data-sidebar-close]");

    function setSidebarOpen(isOpen) {
        document.body.classList.toggle("admin-sidebar-open", isOpen);
        if (openSidebarButton) {
            openSidebarButton.setAttribute("aria-expanded", String(isOpen));
        }
    }

    if (sidebar && openSidebarButton) {
        openSidebarButton.addEventListener("click", () => setSidebarOpen(true));
        closeSidebarTargets.forEach((target) => {
            target.addEventListener("click", () => setSidebarOpen(false));
        });
        sidebar.querySelectorAll("a").forEach((link) => {
            link.addEventListener("click", () => setSidebarOpen(false));
        });
        window.addEventListener("resize", () => {
            if (window.innerWidth > 980) {
                setSidebarOpen(false);
            }
        });
    }

    const tableBody = document.getElementById("users-table-body");
    const searchInput = document.getElementById("admin-global-search");
    const emptyState = document.getElementById("users-empty-state");
    const resultCount = document.getElementById("users-result-count");
    const addUserButtons = document.querySelectorAll("[data-open-user-modal]");
    const modal = document.getElementById("user-modal");
    const userForm = document.getElementById("user-form");
    const modalTitle = document.getElementById("user-modal-title");
    const initialUsersElement = document.getElementById("admin-users-initial-data");
    const fields = {
        name: document.getElementById("user-name"),
        email: document.getElementById("user-email"),
        status: document.getElementById("user-status"),
        created: document.getElementById("user-created"),
    };

    if (!tableBody || !modal || !userForm) {
        return;
    }

    let users = initialUsersElement ? JSON.parse(initialUsersElement.textContent) : [];
    let editingUserId = null;

    function escapeHtml(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#39;");
    }

    function filteredUsers() {
        const query = (searchInput?.value || "").trim().toLowerCase();
        if (!query) {
            return users;
        }
        return users.filter((user) => (
            user.name.toLowerCase().includes(query)
            || user.email.toLowerCase().includes(query)
        ));
    }

    function renderUsers() {
        const visibleUsers = filteredUsers();
        tableBody.innerHTML = visibleUsers.map((user) => `
            <tr>
                <td data-label="Name">
                    <p class="coach-name">${escapeHtml(user.name)}</p>
                </td>
                <td data-label="Email">${escapeHtml(user.email)}</td>
                <td data-label="Status">
                    <span class="status-dot-badge"><span></span>${escapeHtml(user.status)}</span>
                </td>
                <td data-label="Created">${escapeHtml(user.created)}</td>
                <td data-label="Actions">
                    <div class="table-icon-actions">
                        <button type="button" class="table-icon-button" aria-label="Edit ${escapeHtml(user.name)}" data-user-action="edit" data-user-id="${user.id}">
                            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
                        </button>
                        <button type="button" class="table-icon-button table-icon-button--danger" aria-label="Delete ${escapeHtml(user.name)}" data-user-action="delete" data-user-id="${user.id}">
                            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>
                        </button>
                    </div>
                </td>
            </tr>
        `).join("");

        emptyState.classList.toggle("hidden", Boolean(visibleUsers.length));
        resultCount.textContent = visibleUsers.length === users.length
            ? `Showing all ${users.length} users.`
            : `Showing ${visibleUsers.length} of ${users.length} users.`;
    }

    function openModal(user) {
        editingUserId = user?.id || null;
        modalTitle.textContent = editingUserId ? "Edit User" : "Add User";
        fields.name.value = user?.name || "";
        fields.email.value = user?.email || "";
        fields.status.value = user?.status || "Active";
        fields.created.value = user?.created || new Date().toLocaleDateString("en-US");
        modal.classList.remove("hidden");
        modal.setAttribute("aria-hidden", "false");
        fields.name.focus();
    }

    function closeModal() {
        modal.classList.add("hidden");
        modal.setAttribute("aria-hidden", "true");
        editingUserId = null;
        userForm.reset();
    }

    function saveUser(event) {
        event.preventDefault();
        const nextUser = {
            id: editingUserId || `local-${Date.now()}`,
            name: fields.name.value.trim(),
            email: fields.email.value.trim(),
            status: fields.status.value,
            created: fields.created.value.trim(),
        };

        if (editingUserId) {
            users = users.map((user) => (user.id === editingUserId ? nextUser : user));
        } else {
            users = [nextUser, ...users];
        }

        closeModal();
        renderUsers();
    }

    addUserButtons.forEach((button) => {
        button.addEventListener("click", () => openModal());
    });
    searchInput?.addEventListener("input", renderUsers);
    userForm.addEventListener("submit", saveUser);
    modal.querySelectorAll("[data-close-user-modal]").forEach((target) => {
        target.addEventListener("click", closeModal);
    });
    modal.addEventListener("click", (event) => {
        if (event.target.dataset.closeUserModal === "true") {
            closeModal();
        }
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !modal.classList.contains("hidden")) {
            closeModal();
        }
    });
    tableBody.addEventListener("click", (event) => {
        const button = event.target.closest("[data-user-action]");
        if (!button) {
            return;
        }

        const userId = button.dataset.userId;
        const action = button.dataset.userAction;
        const user = users.find((item) => item.id === userId);
        if (!user) {
            return;
        }

        if (action === "edit") {
            openModal(user);
            return;
        }

        if (window.confirm(`Delete ${user.name}?`)) {
            users = users.filter((item) => item.id !== userId);
            renderUsers();
        }
    });

    renderUsers();
})();
