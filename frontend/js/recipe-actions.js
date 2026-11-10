import { api } from './api.js';

/** Confirm and delete one owned recipe; resolves false when the user cancels. */
export function confirmAndDeleteRecipe(token, recipe, language = 'bn') {
  return new Promise((resolve) => {
    const isEnglish = language === 'en';
    const dialog = document.createElement('dialog');
    dialog.className = 'delete-confirm-dialog';
    dialog.setAttribute('aria-labelledby', 'delete-confirm-title');

    const heading = document.createElement('h2');
    heading.id = 'delete-confirm-title';
    heading.textContent = isEnglish ? 'Delete this recipe?' : 'রেসিপিটি মুছে ফেলবেন?';

    const message = document.createElement('p');
    message.textContent = isEnglish
      ? `“${recipe.title || 'Untitled recipe'}” and its saved versions will be permanently deleted.`
      : `“${recipe.title || 'নামহীন রেসিপি'}” এবং এর সংরক্ষিত সংস্করণ স্থায়ীভাবে মুছে যাবে।`;

    const error = document.createElement('p');
    error.className = 'delete-confirm-error';
    error.setAttribute('role', 'alert');
    error.hidden = true;

    const actions = document.createElement('div');
    actions.className = 'delete-confirm-actions';
    const cancel = document.createElement('button');
    cancel.type = 'button';
    cancel.className = 'delete-confirm-cancel';
    cancel.textContent = isEnglish ? 'Keep recipe' : 'রেসিপি রাখুন';
    const confirm = document.createElement('button');
    confirm.type = 'button';
    confirm.className = 'delete-confirm-submit';
    confirm.textContent = isEnglish ? 'Delete recipe' : 'মুছে ফেলুন';
    actions.append(cancel, confirm);
    dialog.append(heading, message, error, actions);
    document.body.appendChild(dialog);

    let settled = false;
    const finish = (deleted) => {
      if (settled) return;
      settled = true;
      if (dialog.open) dialog.close();
      dialog.remove();
      resolve(deleted);
    };

    cancel.addEventListener('click', () => finish(false));
    dialog.addEventListener('cancel', (event) => {
      event.preventDefault();
      finish(false);
    });
    dialog.addEventListener('click', (event) => {
      if (event.target === dialog) finish(false);
    });
    confirm.addEventListener('click', async () => {
      confirm.disabled = true;
      cancel.disabled = true;
      confirm.textContent = isEnglish ? 'Deleting…' : 'মুছে ফেলা হচ্ছে…';
      error.hidden = true;
      try {
        await api.deleteRecipe(token, recipe.id);
        finish(true);
      } catch (cause) {
        error.textContent = cause?.message || (isEnglish
          ? 'The recipe could not be deleted. Please try again.'
          : 'রেসিপিটি মুছে ফেলা যায়নি। আবার চেষ্টা করুন।');
        error.hidden = false;
        confirm.disabled = false;
        cancel.disabled = false;
        confirm.textContent = isEnglish ? 'Try again' : 'আবার চেষ্টা করুন';
      }
    });

    try {
      dialog.showModal();
      cancel.focus();
    } catch {
      finish(false);
    }
  });
}
