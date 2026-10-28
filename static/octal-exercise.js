const octalExercise = document.querySelector("[data-octal-exercise]");

if (octalExercise) {
    const stepRows = Array.from(octalExercise.querySelectorAll("[data-octal-step]"));
    const submitButton = octalExercise.querySelector("[data-octal-submit]");
    const status = octalExercise.querySelector("[data-octal-status]");
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfMeta ? csrfMeta.content : "";

    submitButton.addEventListener("click", async () => {
        const inputs = Array.from(octalExercise.querySelectorAll("input"));
        const firstInvalidInput = inputs.find((input) => !input.checkValidity());
        if (firstInvalidInput) {
            firstInvalidInput.reportValidity();
            return;
        }

        const steps = stepRows.map((row) => ({
            quotient: Number(row.querySelector("[data-octal-quotient]").value),
            remainder: Number(row.querySelector("[data-octal-remainder]").value),
        }));
        submitButton.disabled = true;
        status.textContent = "Проверяем вычисления…";
        status.dataset.state = "";
        stepRows.forEach((row) => row.removeAttribute("data-error"));

        try {
            const response = await fetch(octalExercise.dataset.submitUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": csrfToken,
                },
                body: JSON.stringify({ steps }),
            });
            let result;
            try {
                result = await response.json();
            } catch {
                throw new Error(`Сервер вернул некорректный ответ (${response.status}).`);
            }

            if (response.status === 422) {
                const row = stepRows[result.step - 1];
                if (row) {
                    row.dataset.error = "true";
                }
                status.textContent = `${result.message} Здесь частное ${result.expected_quotient}, остаток ${result.expected_remainder}.`;
                status.dataset.state = "error";
                return;
            }
            if (!response.ok) {
                throw new Error(result.error || "Не удалось проверить вычисления.");
            }

            status.textContent = `Верно! Остатки снизу вверх дают ${result.octal}₈. Открываем следующий раздел…`;
            status.dataset.state = "success";
            await window.completeLaboratoryAttempt?.("octal-conversion");
            window.location.reload();
        } catch (error) {
            status.textContent = error instanceof TypeError
                ? "Не удалось связаться с сервером. Попробуйте ещё раз."
                : error.message;
            status.dataset.state = "error";
        } finally {
            submitButton.disabled = false;
        }
    });
}
