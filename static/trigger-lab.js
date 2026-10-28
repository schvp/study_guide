const triggerLab = document.querySelector("[data-trigger-lab]");

if (triggerLab) {
    const state = { data: 0, clock: 0, output: 0 };
    const events = [];
    const snapshots = [{ action: "Начальное состояние", ...state }];
    const target = [1, 0, 1];
    const controls = Array.from(triggerLab.querySelectorAll("[data-trigger-input]"));
    const checkButton = triggerLab.querySelector("[data-trigger-check]");
    const resetButton = triggerLab.querySelector("[data-trigger-reset]");
    const hintButton = triggerLab.querySelector("[data-trigger-hint]");
    const hintText = triggerLab.querySelector("[data-trigger-hint-text]");
    const status = triggerLab.querySelector("[data-trigger-status]");
    const timeline = triggerLab.querySelector("[data-trigger-timeline]");
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfMeta ? csrfMeta.content : "";
    const hints = [
        "Установите D = 1, затем поднимите CLK с 0 до 1. Именно переход 0 → 1 является положительным фронтом.",
        "Когда CLK = 1 и Q = 1, измените D на 0: Q должен остаться равным 1. Затем опустите CLK и поднимите его снова, чтобы сохранить 0.",
        "Повторите фронт с D = 1, чтобы получить третье состояние Q = 1. В итоге после фронтов должно быть 1 → 0 → 1.",
    ];
    let hintsShown = 0;

    function setStatus(message, result = "") {
        status.textContent = message;
        status.dataset.state = result;
    }

    function renderTimeline() {
        timeline.replaceChildren();
        snapshots.forEach((snapshot, index) => {
            const row = document.createElement("tr");
            const step = document.createElement("th");
            step.scope = "row";
            step.textContent = String(index);
            row.append(step);

            [snapshot.action, snapshot.data, snapshot.clock, snapshot.output].forEach(
                (value) => {
                    const cell = document.createElement("td");
                    cell.textContent = String(value);
                    row.append(cell);
                },
            );
            timeline.append(row);
        });
    }

    function updateView() {
        controls.forEach((button) => {
            const input = button.dataset.triggerInput;
            const value = state[input];
            button.setAttribute("aria-pressed", String(value === 1));
            triggerLab.querySelector(`[data-trigger-value="${input}"]`).textContent =
                String(value);
        });
        triggerLab.querySelector('[data-trigger-value="output"]').textContent =
            String(state.output);
        triggerLab.querySelector("[data-trigger-output]").dataset.triggerOutput =
            String(state.output);
        triggerLab.querySelector("[data-trigger-progress]").textContent =
            `Зафиксировано фронтов: ${snapshots.filter((item) => item.action === "Положительный фронт").length} из ${target.length}`;
        const limitReached = events.length >= 24;
        controls.forEach((button) => {
            button.disabled = limitReached;
        });
        checkButton.disabled = events.length === 0;
        renderTimeline();
    }

    function toggleInput(button) {
        const input = button.dataset.triggerInput;
        const value = 1 - state[input];
        events.push({ type: input, value });
        state[input] = value;
        let action = `D установлено в ${value}`;
        if (input === "clock") {
            action = value === 1 ? "CLK ↑" : "CLK ↓";
            if (value === 1) {
                state.output = state.data;
                action = "Положительный фронт";
            }
        }
        snapshots.push({ action, ...state });
        setStatus("");
        updateView();
    }

    controls.forEach((button) => {
        button.addEventListener("click", () => toggleInput(button));
    });

    resetButton.addEventListener("click", () => {
        state.data = 0;
        state.clock = 0;
        state.output = 0;
        events.length = 0;
        snapshots.length = 0;
        snapshots.push({ action: "Начальное состояние", ...state });
        setStatus("");
        updateView();
    });

    hintButton.addEventListener("click", () => {
        hintText.textContent = hints[hintsShown];
        hintText.hidden = false;
        hintsShown += 1;
        if (hintsShown === hints.length) {
            hintButton.hidden = true;
        } else {
            hintButton.textContent = "Следующая подсказка";
        }
    });

    checkButton.addEventListener("click", async () => {
        checkButton.disabled = true;
        setStatus("Проверяем фронты и сохранение состояния…");

        try {
            const response = await fetch(triggerLab.dataset.submitUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": csrfToken,
                },
                body: JSON.stringify({ events }),
            });
            let result;
            try {
                result = await response.json();
            } catch {
                throw new Error(`Сервер вернул некорректный ответ (${response.status}).`);
            }

            if (response.status === 422) {
                setStatus(result.message, "error");
                hintButton.hidden = false;
                return;
            }
            if (!response.ok) {
                throw new Error(result.error || "Не удалось проверить работу триггера.");
            }

            setStatus("Последовательность верна: триггер хранит состояние между фронтами.", "success");
            await window.completeLaboratoryAttempt?.("trigger");
            window.location.reload();
        } catch (error) {
            setStatus(
                error instanceof TypeError
                    ? "Не удалось связаться с сервером. Попробуйте ещё раз."
                    : error.message,
                "error",
            );
        } finally {
            checkButton.disabled = events.length === 0;
        }
    });

    updateView();
}
