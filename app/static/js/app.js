function toggleAll(source) {
  document.querySelectorAll('input[name="selected"]').forEach((el) => {
    el.checked = source.checked;
  });
}

function confirmAction(form, message) {
  const overlay = document.getElementById("confirm-overlay");
  const text = document.getElementById("confirm-text");
  const ok = document.getElementById("confirm-ok");
  if (!overlay) {
    if (window.confirm(message)) form.submit();
    return false;
  }
  text.textContent = message;
  overlay.classList.add("show");
  const hide = () => overlay.classList.remove("show");
  document.getElementById("confirm-cancel").onclick = hide;
  ok.onclick = () => {
    hide();
    form.submit();
  };
  return false;
}

document.addEventListener("submit", (event) => {
  const form = event.target;
  if (form.dataset.confirm && !form.dataset.confirmed) {
    event.preventDefault();
    if (window.confirm(form.dataset.confirm)) {
      form.dataset.confirmed = "1";
      form.submit();
    }
  }
});
