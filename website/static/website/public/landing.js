(function () {
    const toggle = document.querySelector("[data-nav-toggle]");
    const menu = document.querySelector("[data-nav-menu]");

    if (!toggle || !menu) {
        return;
    }

    function setExpanded(isOpen) {
        toggle.setAttribute("aria-expanded", String(isOpen));
        menu.classList.toggle("is-open", isOpen);
    }

    toggle.addEventListener("click", () => {
        const nextState = toggle.getAttribute("aria-expanded") !== "true";
        setExpanded(nextState);
    });

    menu.querySelectorAll("a").forEach((link) => {
        link.addEventListener("click", () => setExpanded(false));
    });

    window.addEventListener("resize", () => {
        if (window.innerWidth > 920) {
            setExpanded(false);
        }
    });
})();
