const authDialog = document.querySelector("#auth-dialog");
const authOpenButton = document.querySelector("[data-auth-open]");
const authCloseButton = document.querySelector("[data-auth-close]");
const authModeButtons = document.querySelectorAll("[data-auth-mode]");
const authForms = document.querySelectorAll("[data-auth-form]");
const authStatus = document.querySelector("[data-auth-status]");
const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

async function readApiResponse(response) {
    try {
        return await response.json();
    } catch {
        throw new Error(`Сервер вернул некорректный ответ (${response.status}).`);
    }
}

function setAuthMode(mode) {
    authModeButtons.forEach((button) => {
        button.setAttribute("aria-pressed", String(button.dataset.authMode === mode));
    });

    authForms.forEach((form) => {
        form.hidden = form.dataset.authForm !== mode;
    });

    authStatus.textContent = "Пароль сохраняется в виде криптографического хеша.";
}

if (authOpenButton) {
    authOpenButton.addEventListener("click", () => {
        setAuthMode("login");
        authDialog.showModal();
    });
}

if (authCloseButton) {
    authCloseButton.addEventListener("click", () => {
        authDialog.close();
    });

    authDialog.addEventListener("click", (event) => {
        if (event.target === authDialog) {
            authDialog.close();
        }
    });

    authModeButtons.forEach((button) => {
        button.addEventListener("click", () => {
            setAuthMode(button.dataset.authMode);
        });
    });

    authForms.forEach((form) => {
        const passwordConfirmation = form.querySelector('[name="password-confirmation"]');
        const password = form.querySelector('[name="password"]');

        if (passwordConfirmation) {
            const clearPasswordMismatch = () => {
                passwordConfirmation.setCustomValidity("");
            };

            passwordConfirmation.addEventListener("input", clearPasswordMismatch);
            password.addEventListener("input", clearPasswordMismatch);
        }

        form.addEventListener("submit", async (event) => {
            event.preventDefault();

            if (passwordConfirmation && password.value !== passwordConfirmation.value) {
                passwordConfirmation.setCustomValidity("Пароли не совпадают.");
                passwordConfirmation.reportValidity();
                return;
            }

            const submitButton = form.querySelector('[type="submit"]');
            submitButton.disabled = true;
            authStatus.textContent = "Выполняется запрос…";

            try {
                const response = await fetch(form.action, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRF-Token": csrfToken,
                    },
                    body: JSON.stringify({
                        email: form.elements.email.value,
                        password: password.value,
                    }),
                });
                const result = await readApiResponse(response);

                if (!response.ok) {
                    authStatus.textContent = result.error || "Не удалось выполнить запрос.";
                    return;
                }

                window.location.reload();
            } catch (error) {
                authStatus.textContent = error instanceof TypeError
                    ? "Не удалось связаться с сервером. Попробуйте ещё раз."
                    : error.message;
            } finally {
                submitButton.disabled = false;
            }
        });
    });
}

const logoutButton = document.querySelector("[data-auth-logout]");
if (logoutButton) {
    logoutButton.addEventListener("click", async () => {
        logoutButton.disabled = true;
        try {
            const response = await fetch("/api/auth/logout", {
                method: "POST",
                headers: { "X-CSRF-Token": csrfToken },
            });

            const result = await readApiResponse(response);
            if (!response.ok) {
                throw new Error(result.error || "Не удалось выполнить выход.");
            }

            window.location.reload();
        } catch (error) {
            logoutButton.disabled = false;
            window.alert(error.message);
        }
    });
}

const progressToggles = document.querySelectorAll(".progress-toggle:not(:disabled)");
const progressStatus = document.querySelector("[data-progress-status]");
const progressCount = document.querySelector("[data-progress-count]");
const progressBar = document.querySelector("[data-progress-bar]");

function updateProgressSummary() {
    if (!progressCount || !progressBar) {
        return;
    }

    const completedCount = document.querySelectorAll(".progress-toggle:checked").length;
    progressCount.textContent = String(completedCount);
    progressBar.value = completedCount;
}

progressToggles.forEach((toggle) => {
    toggle.addEventListener("change", async () => {
        const completed = toggle.checked;
        toggle.disabled = true;
        progressStatus.textContent = "Сохраняем прогресс…";

        try {
            const response = await fetch(`/api/progress/${toggle.dataset.chapterId}`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": csrfToken,
                },
                body: JSON.stringify({ completed }),
            });
            const result = await readApiResponse(response);

            if (!response.ok) {
                throw new Error(result.error || "Не удалось сохранить прогресс.");
            }

            updateProgressSummary();
            progressStatus.textContent = "Прогресс сохранён.";
        } catch (error) {
            toggle.checked = !completed;
            progressStatus.textContent = error.message || "Не удалось связаться с сервером.";
        } finally {
            toggle.disabled = false;
        }
    });
});
