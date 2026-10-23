(() => {
    const token = document.querySelector('meta[name="csrf-token"]')?.content;
    const player = document.querySelector("[data-assessment-player]");
    const resultsPanel = document.querySelector("[data-assessment-results]");

    if (!token || !player || !resultsPanel) {
        return;
    }

    let activeAttempt = null;
    let timerId = null;

    function clearAttemptTimer() {
        if (timerId !== null) {
            window.clearInterval(timerId);
            timerId = null;
        }
    }

    async function postJson(url, payload) {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": token,
            },
            body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || "Не удалось выполнить запрос.");
        }
        return data;
    }

    function showStatus(container, message, isError = false) {
        let status = container.querySelector("[data-assessment-status]");
        if (!status) {
            status = document.createElement("p");
            status.dataset.assessmentStatus = "";
            status.setAttribute("role", "status");
            container.append(status);
        }
        status.textContent = message;
        status.dataset.state = isError ? "error" : "info";
    }

    function createQuestion(question, index) {
        const fieldset = document.createElement("fieldset");
        fieldset.className = "assessment-question";
        const legend = document.createElement("legend");
        const difficulty = {
            beginner: "Начальная",
            intermediate: "Средняя",
            advanced: "Продвинутая",
        }[question.difficulty];
        legend.textContent = `${index + 1}. ${question.prompt} (${difficulty} сложность)`;
        fieldset.append(legend);

        if (question.question_type === "numeric") {
            const label = document.createElement("label");
            label.className = "assessment-numeric-label";
            label.textContent = "Числовой ответ";
            const input = document.createElement("input");
            input.type = "number";
            input.step = "any";
            input.required = true;
            input.dataset.answer = "";
            label.append(input);
            fieldset.append(label);
            return fieldset;
        }

        const inputType = question.question_type === "multiple_choice" ? "checkbox" : "radio";
        question.options.forEach((option, optionIndex) => {
            const label = document.createElement("label");
            label.className = "assessment-option";
            const input = document.createElement("input");
            input.type = inputType;
            input.name = `question-${question.id}`;
            input.value = option.value;
            input.dataset.answer = "";
            if (inputType === "radio" && optionIndex === 0) {
                input.required = true;
            }
            const text = document.createElement("span");
            text.textContent = option.label;
            label.append(input, text);
            fieldset.append(label);
        });
        return fieldset;
    }

    function collectAnswers(form, questions) {
        const answers = {};
        for (const question of questions) {
            const fields = form.querySelectorAll(
                `[name="question-${question.id}"]`,
            );
            if (question.question_type === "numeric") {
                const input = form.querySelector(
                    `[data-question-id="${question.id}"] [data-answer]`,
                );
                if (!input.value.trim()) {
                    throw new Error("Ответьте на каждый вопрос перед отправкой.");
                }
                answers[question.id] = input.value;
            } else if (question.question_type === "multiple_choice") {
                answers[question.id] = Array.from(fields)
                    .filter((input) => input.checked)
                    .map((input) => input.value);
                if (answers[question.id].length === 0) {
                    throw new Error("Выберите хотя бы один вариант в каждом вопросе.");
                }
            } else {
                const selected = Array.from(fields).find((input) => input.checked);
                if (!selected) {
                    throw new Error("Ответьте на каждый вопрос перед отправкой.");
                }
                answers[question.id] = selected.value;
            }
        }
        return answers;
    }

    function answerLabel(answer, options) {
        const values = Array.isArray(answer) ? answer : [answer];
        const labels = values.map((value) => {
            const option = options.find((item) => item.value === value);
            return option ? option.label : String(value);
        });
        return labels.join(", ");
    }

    function addAttemptToHistory(chapterTitle, score, count) {
        const section = document.querySelector(".assessment-history");
        if (!section) {
            return;
        }
        let list = section.querySelector(".assessment-history-list");
        if (!list) {
            list = document.createElement("ol");
            list.className = "assessment-history-list";
            section.querySelector(".assessment-empty")?.remove();
            section.append(list);
        }
        const item = document.createElement("li");
        const title = document.createElement("span");
        const name = document.createElement("strong");
        name.textContent = chapterTitle;
        const time = document.createElement("small");
        time.textContent = "только что";
        title.append(name, time);
        const result = document.createElement("span");
        result.className = "assessment-history-score";
        result.textContent = `${score} / ${count}`;
        item.append(title, result);
        list.prepend(item);
    }

    function renderResults(data, chapterTitle) {
        resultsPanel.replaceChildren();
        const heading = document.createElement("h2");
        heading.textContent = `Результат: ${data.score} из ${data.question_count}`;
        resultsPanel.append(heading);

        const summary = document.createElement("p");
        summary.className = "assessment-result-summary";
        summary.textContent = data.score === data.question_count
            ? "Отличная работа — все ответы верны."
            : "Посмотрите разбор, чтобы закрепить сложные моменты.";
        resultsPanel.append(summary);

        const list = document.createElement("ol");
        list.className = "assessment-result-list";
        data.results.forEach((result, index) => {
            const item = document.createElement("li");
            item.className = result.correct
                ? "assessment-result is-correct"
                : "assessment-result is-incorrect";
            const title = document.createElement("h3");
            title.textContent = `${index + 1}. ${result.prompt}`;
            const outcome = document.createElement("p");
            outcome.className = "assessment-result-outcome";
            const difficulty = {
                beginner: "начальная",
                intermediate: "средняя",
                advanced: "продвинутая",
            }[result.difficulty];
            outcome.textContent = `${result.correct ? "Верно" : "Неверно"} · ${difficulty} сложность`;
            const answer = document.createElement("p");
            answer.textContent = `Ваш ответ: ${answerLabel(result.answer, result.options)}`;
            const expected = document.createElement("p");
            expected.textContent = `Правильный ответ: ${answerLabel(result.correct_answer, result.options)}`;
            const explanation = document.createElement("p");
            explanation.className = "assessment-explanation";
            explanation.textContent = result.explanation;
            item.append(title, outcome, answer, expected, explanation);
            list.append(item);
        });
        resultsPanel.append(list);
        resultsPanel.hidden = false;
        addAttemptToHistory(chapterTitle, data.score, data.question_count);
        resultsPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    async function startAttempt(button) {
        clearAttemptTimer();
        button.disabled = true;
        resultsPanel.hidden = true;
        player.replaceChildren();
        player.hidden = false;
        showStatus(player, "Загружаем вопросы…");
        try {
            const data = await postJson(
                `/api/assessments/${button.dataset.chapterId}/attempts`,
                {
                    difficulty: button
                        .closest(".assessment-quiz-card")
                        .querySelector("[data-assessment-difficulty]").value,
                },
            );
            activeAttempt = data;
            renderAttempt(data);
        } catch (error) {
            showStatus(player, error.message, true);
        } finally {
            button.disabled = false;
        }
    }

    function renderAttempt(data) {
        player.replaceChildren();
        const heading = document.createElement("h2");
        heading.textContent = data.chapter_title;
        const details = document.createElement("p");
        details.className = "assessment-attempt-details";
        if (data.attempts_remaining !== null) {
            details.textContent = `Осталось попыток после этой: ${data.attempts_remaining}`;
        }
        if (data.time_limit_seconds) {
            const timer = document.createElement("strong");
            timer.dataset.assessmentTimer = "";
            details.append(details.textContent ? " · " : "", timer);
            const updateTimer = () => {
                const remaining = Math.max(
                    0,
                    Math.ceil((Date.parse(data.expires_at) - Date.now()) / 1000),
                );
                const minutes = Math.floor(remaining / 60);
                const seconds = String(remaining % 60).padStart(2, "0");
                timer.textContent = `Осталось времени: ${minutes}:${seconds}`;
                if (remaining === 0) {
                    clearAttemptTimer();
                    showStatus(player, "Время истекло. Отправьте ответы, чтобы завершить попытку.", true);
                }
            };
            updateTimer();
            timerId = window.setInterval(updateTimer, 1000);
        }
        const form = document.createElement("form");
        form.className = "assessment-form";
        form.noValidate = true;

        data.questions.forEach((question, index) => {
            const fieldset = createQuestion(question, index);
            fieldset.dataset.questionId = question.id;
            form.append(fieldset);
        });
        const submit = document.createElement("button");
        submit.className = "primary-link";
        submit.type = "submit";
        submit.textContent = "Проверить ответы";
        form.append(submit);
        form.addEventListener("submit", submitAttempt);
        player.append(heading, details, form);
    }

    async function submitAttempt(event) {
        event.preventDefault();
        const form = event.currentTarget;
        const submit = form.querySelector('button[type="submit"]');
        let answers;
        try {
            answers = collectAnswers(form, activeAttempt.questions);
        } catch (error) {
            showStatus(player, error.message, true);
            return;
        }

        submit.disabled = true;
        showStatus(player, "Проверяем ответы…");
        try {
            const data = await postJson(
                `/api/assessments/attempts/${activeAttempt.attempt_id}/submit`,
                { answers },
            );
            form.remove();
            clearAttemptTimer();
            player.querySelector("[data-assessment-status]")?.remove();
            renderResults(data, activeAttempt.chapter_title);
        } catch (error) {
            showStatus(player, error.message, true);
            submit.disabled = false;
        }
    }

    document.querySelectorAll("[data-assessment-start]").forEach((button) => {
        button.addEventListener("click", () => startAttempt(button));
    });
})();
