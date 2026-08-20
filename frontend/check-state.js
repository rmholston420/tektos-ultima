// Check current state
const p = document.querySelector('p[aria-label]');
const wordmark = p ? {
  fontFamily: getComputedStyle(p).fontFamily,
  fontSize: getComputedStyle(p).fontSize,
  fontWeight: getComputedStyle(p).fontWeight,
  letterSpacing: getComputedStyle(p).letterSpacing,
  lineHeight: getComputedStyle(p).lineHeight,
  textTransform: getComputedStyle(p).textTransform,
  width: getComputedStyle(p).width,
  maxWidth: getComputedStyle(p).maxWidth,
  display: getComputedStyle(p).display,
  containerType: getComputedStyle(p).containerType
} : 'not found';

const el = document.querySelector('[data-slot=aui_intro]');
const introBody = el ? (() => {
  const body = el.querySelector('p:last-child');
  return body ? {
    fontSize: getComputedStyle(body).fontSize,
    lineHeight: getComputedStyle(body).lineHeight,
    color: getComputedStyle(body).color,
    textAlign: getComputedStyle(body).textAlign,
    maxWidth: getComputedStyle(body).maxWidth,
    text: body.textContent
  } : 'no body';
})() : 'not found';

const s = document.querySelector('[data-slot=composer-surface]');
const composerSurface = s ? {
  background: getComputedStyle(s).background,
  borderRadius: getComputedStyle(s).borderRadius,
  border: getComputedStyle(s).border,
  overflow: getComputedStyle(s).overflow
} : 'not found';

const mp = document.querySelector('.composer-model-pill');
const modelPill = mp ? {
  color: getComputedStyle(mp).color,
  background: getComputedStyle(mp).background,
  fontSize: getComputedStyle(mp).fontSize,
  height: getComputedStyle(mp).height,
  text: mp.textContent.trim()
} : 'not found';

const sb = document.querySelector('.composer-send-btn');
const sendBtn = sb ? {
  width: getComputedStyle(sb).width,
  height: getComputedStyle(sb).height,
  borderRadius: getComputedStyle(sb).borderRadius,
  background: getComputedStyle(sb).background,
  color: getComputedStyle(sb).color
} : 'not found';

console.log(JSON.stringify({ wordmark, introBody, composerSurface, modelPill, sendBtn }));