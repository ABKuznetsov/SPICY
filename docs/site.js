'use strict';
const expandButton = document.getElementById('expand-demo');
const presentation = document.getElementById('presentation');
const status = document.getElementById('fullscreen-status');
// The exported viewer delegates navigation to its parent when embedded.
// Keep it inside the page and route only messages from our own demo frame.
window.addEventListener('message', (event) => {
  if (event.source !== presentation.contentWindow || event.origin !== location.origin) return;
  if (event.data?.spicyPresenterRuntime !== 1 || event.data.type !== 'REQUEST') return;
  const { command, value } = event.data.payload || {};
  if (command === 'CLOSE') {
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    return;
  }
  if (!['NEXT', 'PREVIOUS', 'GOTO'].includes(command)) return;
  const frames = JSON.parse(presentation.contentDocument.getElementById('spicy-runtime-frames').textContent);
  const match = presentation.contentWindow.location.hash.match(/^#slide-(\d+)$/);
  const current = match ? Number(match[1]) - 1 : 0;
  const byId = typeof value === 'string' ? frames.findIndex(frame => frame.slideId === value) : -1;
  const requested = command === 'NEXT' ? current + 1 : command === 'PREVIOUS' ? current - 1 : byId >= 0 ? byId : Number(value);
  if (!Number.isInteger(requested)) return;
  const next = Math.max(0, Math.min(frames.length - 1, requested));
  presentation.contentWindow.location.hash = 'slide-' + (next + 1);
});
expandButton.addEventListener('click', async () => {
  try {
    if (!presentation.requestFullscreen) throw new Error('Fullscreen is unavailable');
    await presentation.requestFullscreen();
  } catch {
    status.classList.remove('sr-only');
    status.textContent = 'Fullscreen is unavailable here. Use “Open in a new tab” for a larger view.';
  }
});
