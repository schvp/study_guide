const authDialog = document.querySelector("#auth-dialog");
const authOpenButton = document.querySelector("[data-auth-open]");
const authCloseButton = document.querySelector("[data-auth-close]");
const authModeButtons = document.querySelectorAll("[data-auth-mode]");
const authForms = document.querySelectorAll("[data-auth-form]");
const authStatus = document.querySelector("[data-auth-status]");

function setAuthMode(mode) {
    authModeButtons.forEach((button) => {
        button.setAttribute("aria-pressed", String(button.dataset.authMode === mode));
    });

    authForms.forEach((form) => {
        form.hidden = form.dataset.authForm !== mode;
    });

    authStatus.textContent = "Демонстрационный интерфейс: данные не отправляются.";
}

authOpenButton.addEventListener("click", () => {
    setAuthMode("login");
    authDialog.showModal();
});

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

    form.addEventListener("submit", (event) => {
        event.preventDefault();

        if (passwordConfirmation && password.value !== passwordConfirmation.value) {
            passwordConfirmation.setCustomValidity("Пароли не совпадают.");
            passwordConfirmation.reportValidity();
            return;
        }

        authStatus.textContent = "Интерфейс готов к подключению авторизации. Данные не отправляются.";
    });
});
