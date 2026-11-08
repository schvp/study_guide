const libraryProgressButtons = document.querySelectorAll("[data-library-progress]");
const libraryProgressStatus = document.querySelector("[data-library-progress-status]");
const libraryCsrfMeta = document.querySelector('meta[name="csrf-token"]');
const libraryCsrfToken = libraryCsrfMeta ? libraryCsrfMeta.content : "";

const progressLabels = {
    favorite: ["В избранное", "В избранном"],
    completion: ["Отметить прочитанным", "Прочитано"],
};

libraryProgressButtons.forEach((button) => {
    button.addEventListener("click", async () => {
        const action = button.dataset.libraryProgress;
        const nextValue = button.getAttribute("aria-pressed") !== "true";
        button.disabled = true;
        if (libraryProgressStatus) {
            libraryProgressStatus.textContent = "Сохраняем…";
        }

        try {
            const response = await fetch(button.dataset.endpoint, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": libraryCsrfToken,
                },
                body: JSON.stringify({ value: nextValue }),
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || "Не удалось сохранить изменение.");
            }
            button.setAttribute("aria-pressed", String(nextValue));
            button.classList.toggle("is-active", nextValue);
            button.textContent = progressLabels[action][nextValue ? 1 : 0];
            if (libraryProgressStatus) {
                libraryProgressStatus.textContent = "Сохранено";
            }
        } catch (error) {
            if (libraryProgressStatus) {
                libraryProgressStatus.textContent = error.message;
            }
        } finally {
            button.disabled = false;
        }
    });
});
