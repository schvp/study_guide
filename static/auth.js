const authDialog = document.querySelector("#auth-dialog");
const authOpenButton = document.querySelector("[data-auth-open]");
const authCloseButton = document.querySelector("[data-auth-close]");
const authModeButtons = document.querySelectorAll("[data-auth-mode]");
const authForms = document.querySelectorAll("[data-auth-form]");
const authStatus = document.querySelector("[data-auth-status]");
const defaultAuthStatus = authStatus ? authStatus.textContent.trim() : "";
const csrfMeta = document.querySelector('meta[name="csrf-token"]');
const csrfToken = csrfMeta ? csrfMeta.content : "";

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

    authStatus.textContent = defaultAuthStatus;
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
                        ...(form.dataset.authForm === "register"
                            ? {
                                username: form.elements.username.value,
                                email: form.elements.email.value,
                            }
                            : { login: form.elements.login.value }),
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

const completeChapterButton = document.querySelector("[data-complete-chapter]");
if (completeChapterButton) {
    completeChapterButton.addEventListener("click", async () => {
        const status = document.querySelector("[data-complete-status]");
        completeChapterButton.disabled = true;
        status.textContent = "Сохраняем прогресс…";

        try {
            const response = await fetch(
                `/api/progress/${completeChapterButton.dataset.completeChapter}`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRF-Token": csrfToken,
                    },
                    body: JSON.stringify({ completed: true }),
                },
            );
            const result = await readApiResponse(response);

            if (!response.ok) {
                throw new Error(result.error || "Не удалось сохранить прогресс.");
            }

            window.location.reload();
        } catch (error) {
            status.textContent = error instanceof TypeError
                ? "Не удалось связаться с сервером. Попробуйте ещё раз."
                : error.message;
            completeChapterButton.disabled = false;
        }
    });
}
