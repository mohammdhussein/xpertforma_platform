(function () {
    const form = document.querySelector("[data-auth-form]");
    if (!form) {
        return;
    }

    const passwordInput = form.querySelector("[data-password-input]");
    const passwordToggle = form.querySelector("[data-password-toggle]");
    const submitButton = form.querySelector("[data-submit-button]");
    const buttonLabel = submitButton?.querySelector(".button__label");

    if (passwordInput && passwordToggle) {
        passwordToggle.addEventListener("click", () => {
            const isHidden = passwordInput.type === "password";
            passwordInput.type = isHidden ? "text" : "password";
            passwordToggle.textContent = isHidden ? "Hide" : "Show";
            passwordToggle.setAttribute("aria-label", isHidden ? "Hide password" : "Show password");
            passwordToggle.setAttribute("aria-pressed", isHidden ? "true" : "false");
        });
    }

    if (submitButton && buttonLabel) {
        form.addEventListener("submit", () => {
            submitButton.disabled = true;
            submitButton.classList.add("button--loading");
            buttonLabel.textContent = submitButton.dataset.loadingLabel || "Signing in...";
        });
    }
})();
