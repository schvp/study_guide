const byteExercise = document.querySelector("[data-byte-exercise]");

if (byteExercise) {
    const bitButtons = Array.from(byteExercise.querySelectorAll("[data-byte-bit]"));
    const submitButton = byteExercise.querySelector("[data-byte-submit]");
    const status = byteExercise.querySelector("[data-byte-status]");
    const bits = bitButtons.map(() => 0);
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfMeta ? csrfMeta.content : "";

    function updateByteDisplay() {
        const binary = bits.join("");
        const decimal = bits.reduce(
            (value, bit, index) => value + bit * Number(bitButtons[index].dataset.weight),
            0,
        );

        bitButtons.forEach((button, index) => {
            button.setAttribute("aria-pressed", String(bits[index] === 1));
            button.setAttribute(
                "aria-label",
                `Разряд ${button.dataset.weight}, значение ${bits[index]}`,
            );
            button.querySelector("[data-byte-bit-value]").textContent = String(bits[index]);
        });
        byteExercise.querySelector("[data-byte-binary]").textContent = binary;
        byteExercise.querySelector("[data-byte-decimal]").textContent = String(decimal);
        byteExercise.querySelector("[data-byte-hex]").textContent = decimal
            .toString(16)
            .toUpperCase()
            .padStart(2, "0");
    }

    bitButtons.forEach((button, index) => {
        button.addEventListener("click", () => {
            bits[index] = bits[index] === 0 ? 1 : 0;
            status.textContent = "";
            status.dataset.state = "";
            updateByteDisplay();
        });
    });

    submitButton.addEventListener("click", async () => {
        submitButton.disabled = true;
        status.textContent = "Проверяем код…";
        status.dataset.state = "";

        try {
            const response = await fetch(byteExercise.dataset.submitUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": csrfToken,
                },
                body: JSON.stringify({ bits }),
            });
            let result;
            try {
                result = await response.json();
            } catch {
                throw new Error(`Сервер вернул некорректный ответ (${response.status}).`);
            }

            if (response.status === 422) {
                status.textContent = `${result.message} Сейчас получилось ${result.value}.`;
                status.dataset.state = "error";
                return;
            }
            if (!response.ok) {
                throw new Error(result.error || "Не удалось проверить ответ.");
            }

            status.textContent = "Верно! Открываем следующий раздел…";
            status.dataset.state = "success";
            await window.completeLaboratoryAttempt?.("byte-assembly");
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

    updateByteDisplay();
}
