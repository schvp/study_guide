const registerCounterLab = document.querySelector("[data-register-counter-lab]");

if (registerCounterLab) {
    const targetBits = Array.from(registerCounterLab.dataset.targetBits, Number);
    const state = { data: 0, clock: 0, register: 0, counter: 0 };
    const events = [];
    const snapshots = [{ data: null, register: 0, counter: 0 }];
    const inputButton = registerCounterLab.querySelector("[data-register-input]");
    const clockButton = registerCounterLab.querySelector("[data-register-clock]");
    const resetButton = registerCounterLab.querySelector("[data-register-reset]");
    const checkButton = registerCounterLab.querySelector("[data-register-check]");
    const status = registerCounterLab.querySelector("[data-register-status]");
    const timeline = registerCounterLab.querySelector("[data-register-timeline]");
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfMeta ? csrfMeta.content : "";

    function binary(value, width) {
        return value.toString(2).padStart(width, "0");
    }

    function setStatus(message, result = "") {
        status.textContent = message;
        status.dataset.state = result;
    }

    function renderTimeline() {
        timeline.replaceChildren();
        snapshots.forEach((snapshot, index) => {
            const row = document.createElement("tr");
            const values = [
                index,
                snapshot.data === null ? "—" : snapshot.data,
                binary(snapshot.register, 4),
                `${binary(snapshot.counter, 3)} (${snapshot.counter})`,
            ];
            values.forEach((value, cellIndex) => {
                const cell = document.createElement(cellIndex === 0 ? "th" : "td");
                if (cellIndex === 0) {
                    cell.scope = "row";
                }
                cell.textContent = String(value);
                row.append(cell);
            });
            timeline.append(row);
        });
    }

    function updateView() {
        inputButton.setAttribute("aria-pressed", String(state.data === 1));
        clockButton.setAttribute("aria-pressed", String(state.clock === 1));
        registerCounterLab.querySelector("[data-register-data]").textContent =
            String(state.data);
        registerCounterLab.querySelector("[data-register-clock-value]").textContent =
            String(state.clock);
        const registerWord = binary(state.register, 4);
        registerCounterLab.querySelector("[data-register-word]").textContent =
            registerWord;
        registerWord.split("").forEach((bit, index) => {
            registerCounterLab.querySelector(`[data-register-bit="${index}"]`).textContent =
                bit;
        });
        const counterOutput = registerCounterLab.querySelector("[data-counter-state]");
        counterOutput.dataset.counterState = String(state.counter);
        registerCounterLab.querySelector("[data-counter-binary]").textContent =
            binary(state.counter, 3);
        registerCounterLab.querySelector("[data-counter-decimal]").textContent =
            String(state.counter);
        const pulses = snapshots.length - 1;
        registerCounterLab.querySelector("[data-counter-progress]").textContent =
            `Импульсов: ${pulses} из ${targetBits.length}`;
        const limitReached = events.length >= 32;
        inputButton.disabled = limitReached;
        clockButton.disabled = limitReached;
        checkButton.disabled = events.length === 0;
        renderTimeline();
    }

    inputButton.addEventListener("click", () => {
        state.data = 1 - state.data;
        events.push({ type: "data", value: state.data });
        setStatus("");
        updateView();
    });

    clockButton.addEventListener("click", () => {
        const previousClock = state.clock;
        state.clock = 1 - state.clock;
        events.push({ type: "clock", value: state.clock });
        if (previousClock === 0 && state.clock === 1) {
            state.register = ((state.register << 1) | state.data) & 0b1111;
            state.counter = (state.counter + 1) % 6;
            snapshots.push({
                data: state.data,
                register: state.register,
                counter: state.counter,
            });
        }
        setStatus("");
        updateView();
    });

    resetButton.addEventListener("click", () => {
        state.data = 0;
        state.clock = 0;
        state.register = 0;
        state.counter = 0;
        events.length = 0;
        snapshots.length = 0;
        snapshots.push({ data: null, register: 0, counter: 0 });
        setStatus("");
        updateView();
    });

    checkButton.addEventListener("click", async () => {
        checkButton.disabled = true;
        setStatus("Проверяем переданные биты, сдвиг регистра и цикл счётчика…");

        try {
            const response = await fetch(registerCounterLab.dataset.submitUrl, {
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
                return;
            }
            if (!response.ok) {
                throw new Error(result.error || "Не удалось проверить передачу.");
            }

            setStatus("Пакет принят: регистр и счётчик работают верно.", "success");
            await window.completeLaboratoryAttempt?.("register-counter");
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
