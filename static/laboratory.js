(() => {
    const token = document.querySelector('meta[name="csrf-token"]')?.content;
    const launchLinks = document.querySelectorAll("[data-laboratory-start]");

    if (!token || launchLinks.length === 0) {
        return;
    }

    function showLaunchError(card, message) {
        let status = card.querySelector("[data-laboratory-status]");
        if (!status) {
            status = document.createElement("p");
            status.dataset.laboratoryStatus = "";
            status.setAttribute("role", "status");
            card.querySelector(".laboratory-card-content")?.append(status);
        }
        status.textContent = message;
    }

    async function startLaboratory(event) {
        event.preventDefault();
        const link = event.currentTarget;
        const card = link.closest(".laboratory-card");
        link.setAttribute("aria-disabled", "true");
        try {
            const response = await fetch(
                `/api/laboratories/${link.dataset.laboratorySlug}/attempts`,
                {
                    method: "POST",
                    headers: {"X-CSRF-Token": token},
                },
            );
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || "Не удалось начать лабораторную работу.");
            }
            window.location.assign(link.href);
        } catch (error) {
            showLaunchError(card, error.message);
            link.removeAttribute("aria-disabled");
        }
    }

    launchLinks.forEach((link) => {
        link.addEventListener("click", startLaboratory);
    });
})();
