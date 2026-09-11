/* Helpers for external listing values interpolated into existing templates. */
function bbEscape(value) {
  return String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function bbURLAttribute(value) {
  try {
    const url = new URL(value);
    return ['https:', 'http:'].includes(url.protocol) ? bbEscape(url.href) : '';
  } catch { return ''; }
}
