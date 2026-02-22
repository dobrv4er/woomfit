(function () {
  const INTEGRATION_JS_URL = "https://integrationjs.tbank.ru/integration.js";
  let integrationLoadPromise = null;

  function loadIntegrationJs() {
    if (window.PaymentIntegration) {
      return Promise.resolve(window.PaymentIntegration);
    }
    if (integrationLoadPromise) {
      return integrationLoadPromise;
    }

    integrationLoadPromise = new Promise(function (resolve, reject) {
      const existing = document.querySelector('script[src="' + INTEGRATION_JS_URL + '"]');
      if (existing) {
        existing.addEventListener("load", function () {
          if (window.PaymentIntegration) {
            resolve(window.PaymentIntegration);
          } else {
            reject(new Error("Библиотека T-Bank загружена с ошибкой."));
          }
        });
        existing.addEventListener("error", function () {
          reject(new Error("Не удалось загрузить integration.js."));
        });
        return;
      }

      const script = document.createElement("script");
      script.src = INTEGRATION_JS_URL;
      script.async = true;
      script.onload = function () {
        if (window.PaymentIntegration) {
          resolve(window.PaymentIntegration);
        } else {
          reject(new Error("Библиотека T-Bank загружена с ошибкой."));
        }
      };
      script.onerror = function () {
        reject(new Error("Не удалось загрузить integration.js."));
      };
      document.head.appendChild(script);
    });

    return integrationLoadPromise;
  }

  function showError(node, message) {
    if (!node) return;
    node.textContent = message;
    node.hidden = false;
  }

  function clearError(node) {
    if (!node) return;
    node.textContent = "";
    node.hidden = true;
  }

  function validateForm(form) {
    const fields = Array.from(form.querySelectorAll("[required]"));
    for (let i = 0; i < fields.length; i += 1) {
      const field = fields[i];
      if (typeof field.checkValidity === "function" && !field.checkValidity()) {
        if (typeof field.reportValidity === "function") {
          field.reportValidity();
        }
        return false;
      }
    }
    return true;
  }

  function getWidgetRequiredError(form) {
    const fields = Array.from(form.querySelectorAll("[data-widget-required='1']"));
    for (let i = 0; i < fields.length; i += 1) {
      const field = fields[i];
      const value = "value" in field ? field.value : field.textContent;
      if (!String(value || "").trim()) {
        return field.dataset.widgetRequiredMessage || "Заполните обязательные поля формы.";
      }
    }
    return "";
  }

  async function requestPaymentUrl(endpoint, form, forcedMethod, methodData) {
    const formData = new FormData(form);
    formData.set("integration_widget", "1");
    if (forcedMethod) {
      formData.set("method", forcedMethod);
    }
    if (methodData !== undefined) {
      formData.set("widget_method_data", JSON.stringify(methodData));
    }

    const response = await fetch(endpoint, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
      body: formData,
    });

    let payload = {};
    try {
      payload = await response.json();
    } catch (e) {
      payload = {};
    }

    if (!response.ok) {
      throw new Error(payload.error || "Не удалось создать онлайн-оплату.");
    }

    const paymentUrl = payload.paymentUrl || payload.PaymentURL;
    if (!paymentUrl) {
      throw new Error("Сервер не вернул ссылку на оплату.");
    }
    return paymentUrl;
  }

  async function mountPaymentWidget(PaymentIntegration, options) {
    const integration = await PaymentIntegration.init({
      terminalKey: options.terminalKey,
      product: options.product,
      features: {
        payment: {},
      },
    });

    if (
      !integration ||
      !integration.payments ||
      typeof integration.payments.setPaymentStartCallback !== "function"
    ) {
      throw new Error("Не удалось инициализировать модуль оплаты T-Bank.");
    }

    await integration.payments.setPaymentStartCallback(async function (paymentType) {
      clearError(options.errorNode);
      if (!validateForm(options.form)) {
        throw new Error("Проверьте обязательные поля формы.");
      }

      const customError = getWidgetRequiredError(options.form);
      if (customError) {
        throw new Error(customError);
      }

      try {
        return await requestPaymentUrl(options.endpoint, options.form, options.paymentMethod, {
          paymentType: paymentType,
          widgetName: options.integrationName,
        });
      } catch (error) {
        showError(
          options.errorNode,
          error && error.message ? error.message : "Не удалось создать онлайн-оплату."
        );
        throw error;
      }
    });

    if (typeof integration.payments.create !== "function") {
      throw new Error("Модуль оплаты T-Bank недоступен.");
    }

    const paymentIntegration = await integration.payments.create(options.integrationName, {});
    if (!paymentIntegration || typeof paymentIntegration.mount !== "function") {
      throw new Error("Не удалось создать виджет оплаты T-Bank.");
    }
    await paymentIntegration.mount(options.container);
  }

  function initWidget(node, index) {
    const containerId = node.dataset.containerId;
    const formId = node.dataset.formId;
    const endpoint = node.dataset.endpoint || "";
    const terminalKey = node.dataset.terminalKey || "";
    const product = node.dataset.product || "eacq";
    const paymentMethod = node.dataset.paymentMethod || "";
    const errorId = node.dataset.errorId;
    const fallbackButtonId = node.dataset.fallbackButtonId;
    const integrationName = node.dataset.integrationName || "main-integration-" + String(index + 1);

    const container = containerId ? document.getElementById(containerId) : null;
    const form = formId ? document.getElementById(formId) : null;
    const errorNode = errorId ? document.getElementById(errorId) : null;
    const fallbackButton = fallbackButtonId ? document.getElementById(fallbackButtonId) : null;

    if (!container || !form || !endpoint || !terminalKey) {
      return;
    }

    clearError(errorNode);
    loadIntegrationJs()
      .then(function (PaymentIntegration) {
        return mountPaymentWidget(PaymentIntegration, {
          container: container,
          form: form,
          endpoint: endpoint,
          terminalKey: terminalKey,
          product: product,
          paymentMethod: paymentMethod,
          errorNode: errorNode,
          integrationName: integrationName,
        });
      })
      .then(function () {
        container.hidden = false;
        if (fallbackButton) {
          fallbackButton.hidden = true;
          fallbackButton.disabled = true;
        }
      })
      .catch(function (error) {
        if (fallbackButton) {
          fallbackButton.hidden = false;
          fallbackButton.disabled = false;
        }
        showError(
          errorNode,
          error && error.message ? error.message : "Онлайн-оплата временно недоступна."
        );
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    const widgets = Array.from(document.querySelectorAll("[data-tbank-widget]"));
    widgets.forEach(function (node, index) {
      initWidget(node, index);
    });
  });
})();
