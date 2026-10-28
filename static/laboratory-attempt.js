(() => {
    const token = document.querySelector('meta[name="csrf-token"]')?.content;

    async function completeLaboratoryAttempt(slug) {
        const storageKey = `laboratory-attempt:${slug}`;
        const attemptId = window.sessionStorage.getItem(storageKey);
        if (!attemptId || !token) {
            return null;
        }

        const response = await fetch(
            `/api/laboratories/attempts/${attemptId}/complete`,
            {
                method: "POST",
                headers: {"X-CSRF-Token": token},
            },
        );
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || "Не удалось сохранить результат лабораторной работы.");
        }

        window.sessionStorage.removeItem(storageKey);
        return data;
    }

    window.completeLaboratoryAttempt = completeLaboratoryAttempt;
})();
