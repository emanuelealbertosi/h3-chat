// Each input keeps its own expansion state while the chat refreshes.
const expanded = new Set();

export const inputMedia = message => message.role === 'user' ? (message.display_media ?? message.media ?? []) : (message.media ?? []);

export function collapseInput(article, message) {
  if (message.role !== 'user') return;
  const details = document.createElement('details');
  details.className = 'message-input';
  details.open = expanded.has(message.id);
  const summary = document.createElement('summary');
  const header = article.querySelector('.message-head');
  const label = document.createElement('span');
  label.className = 'input-label';
  label.textContent = 'Richiesta';
  const preview = document.createElement('span');
  preview.className = 'input-preview';
  preview.textContent = (message.content || '').replace(/\s+/g, ' ').trim().slice(0, 160);
  const count = document.createElement('span');
  count.className = 'input-count';
  const attachments = inputMedia(message).length;
  count.textContent = attachments ? attachments + (attachments === 1 ? ' allegato' : ' allegati') : '';
  header.append(label, preview, count);
  summary.append(header);
  details.append(summary, article.querySelector('.message-content'), article.querySelector('.message-actions'));
  details.addEventListener('toggle', () => {
    if (!details.isConnected) return;
    if (details.open) expanded.add(message.id); else expanded.delete(message.id);
  });
  article.replaceChildren(details);
}
