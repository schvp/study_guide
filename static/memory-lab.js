const memoryLab = document.querySelector("[data-memory-lab]");

if (memoryLab) {
    const rom = memoryLab.dataset.rom.split(",");
    const ram = ["0000", "0000", "0000", "0000"];
    const events = [];
    const reads = [];
    let address = 0;
    let memoryType = "ram";
    let data = "0000";
    let powered = true;
    let powerCycleCompleted = false;

    const addressSelect = memoryLab.querySelector("[data-memory-address]");
    const powerButton = memoryLab.querySelector("[data-memory-power]");
    const readButton = memoryLab.querySelector("[data-memory-read]");
    const writeButton = memoryLab.querySelector("[data-memory-write]");
    const checkButton = memoryLab.querySelector("[data-memory-check]");
    const resetButton = memoryLab.querySelector("[data-memory-reset]");
    const status = memoryLab.querySelector("[data-memory-status]");
    const history = memoryLab.querySelector("[data-memory-history]");
    const readout = memoryLab.querySelector("[data-memory-readout]");
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfMeta ? csrfMeta.content : "";

    function binaryAddress(value) {
        return value.toString(2).padStart(2, "0");
    }

    function setStatus(message, result = "") {
        status.textContent = message;
        status.dataset.state = result;
    }

    function addHistory(action, value) {
        const row = document.createElement("tr");
        [events.length, action, binaryAddress(address), value].forEach(
            (cellValue, index) => {
                const cell = document.createElement(index === 0 ? "th" : "td");
                if (index === 0) {
                    cell.scope = "row";
                }
                cell.textContent = String(cellValue);
                row.append(cell);
            },
        );
        history.append(row);
    }

    function updateView() {
        memoryLab.querySelectorAll("[data-memory-type]").forEach((button) => {
            button.setAttribute(
                "aria-pressed",
                String(button.dataset.memoryType === memoryType),
            );
        });
        memoryLab.querySelectorAll("[data-memory-data-bit]").forEach((button) => {
            const index = Number(button.dataset.memoryDataBit);
            const bit = data[index];
            button.textContent = bit;
            button.setAttribute("aria-pressed", String(bit === "1"));
        });
        ram.forEach((word, index) => {
            memoryLab.querySelector(
                `[data-memory-cell="ram-${index}"] strong`,
            ).textContent = powered ? word : "----";
        });

        const powerState = memoryLab.querySelector("[data-memory-power-state]");
        powerState.textContent = powered
            ? "Питание включено"
            : "Питание отключено";
        powerState.dataset.state = powered ? "on" : "off";
        powerButton.textContent = powered
            ? "Выключить питание"
            : "Включить питание";
        powerButton.setAttribute("aria-pressed", String(powered));
        readButton.disabled = !powered;
        writeButton.disabled = !powered || memoryType !== "ram";
        checkButton.disabled = events.length === 0;

        const checks = [
            reads.some(
                (read) => read.memory === "ram"
                    && read.address === 2
                    && read.value === "1101"
                    && !read.afterPowerCycle,
            ),
            reads.some(
                (read) => read.memory === "rom"
                    && read.address === 1
                    && read.value === rom[1]
                    && !read.afterPowerCycle,
            ),
            reads.some(
                (read) => read.memory === "ram"
                    && read.address === 2
                    && read.value === "0000"
                    && read.afterPowerCycle,
            ),
            reads.some(
                (read) => read.memory === "rom"
                    && read.address === 1
                    && read.value === rom[1]
                    && read.afterPowerCycle,
            ),
        ].filter(Boolean).length;
        memoryLab.querySelector("[data-memory-progress]").textContent =
            `Выполнено проверок: ${checks} из 4`;
    }

    addressSelect.addEventListener("change", () => {
        address = Number(addressSelect.value);
        events.push({ type: "address", value: address });
        setStatus("");
    });

    memoryLab.querySelectorAll("[data-memory-type]").forEach((button) => {
        button.addEventListener("click", () => {
            memoryType = button.dataset.memoryType;
            setStatus("");
            updateView();
        });
    });

    memoryLab.querySelectorAll("[data-memory-data-bit]").forEach((button) => {
        button.addEventListener("click", () => {
            const bits = data.split("");
            const index = Number(button.dataset.memoryDataBit);
            bits[index] = bits[index] === "0" ? "1" : "0";
            data = bits.join("");
            events.push({ type: "data", value: data });
            setStatus("");
            updateView();
        });
    });

    writeButton.addEventListener("click", () => {
        if (!powered || memoryType !== "ram") {
            return;
        }
        events.push({ type: "write" });
        ram[address] = data;
        addHistory(`Запись RAM · ${data}`, data);
        setStatus(`Слово ${data} записано в RAM по адресу ${binaryAddress(address)}.`);
        updateView();
    });

    readButton.addEventListener("click", () => {
        if (!powered) {
            return;
        }
        events.push({ type: "read", memory: memoryType });
        const value = memoryType === "ram" ? ram[address] : rom[address];
        const read = {
            memory: memoryType,
            address,
            value,
            powered,
            afterPowerCycle: powerCycleCompleted,
        };
        reads.push(read);
        readout.textContent =
            `${memoryType.toUpperCase()}[${binaryAddress(address)}] = ${value}`;
        addHistory(`Чтение ${memoryType.toUpperCase()}`, value);
        setStatus("");
        updateView();
    });

    powerButton.addEventListener("click", () => {
        events.push({ type: "power" });
        powered = !powered;
        if (!powered) {
            ram.fill("0000");
        } else {
            powerCycleCompleted = true;
        }
        addHistory(
            powered ? "Питание включено" : "Питание отключено",
            powered ? "ON" : "OFF",
        );
        readout.textContent = powered
            ? "Питание восстановлено. Проверьте содержимое памяти."
            : "Питание отключено: данные RAM очищены.";
        setStatus("");
        updateView();
    });

    resetButton.addEventListener("click", () => {
        address = 0;
        memoryType = "ram";
        data = "0000";
        powered = true;
        powerCycleCompleted = false;
        ram.fill("0000");
        events.length = 0;
        reads.length = 0;
        history.replaceChildren();
        addressSelect.value = "0";
        readout.textContent = "Выберите адрес и выполните чтение.";
        setStatus("");
        updateView();
    });

    checkButton.addEventListener("click", async () => {
        checkButton.disabled = true;
        setStatus("Проверяем запись, чтение и сохранность данных…");

        try {
            const response = await fetch(memoryLab.dataset.submitUrl, {
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
                throw new Error(result.error || "Не удалось проверить эксперимент.");
            }

            setStatus("Эксперимент подтверждён: RAM и ROM ведут себя по-разному.", "success");
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
