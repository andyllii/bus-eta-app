// Inline SVG icons — identical path data to web-app/src/components/icons.tsx
// so the mockups match the real app pixel-for-pixel. Each returns an <svg>
// string; colour is inherited from currentColor.
const SVG = `fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"`;

export const Icons = {
  bus: `<svg ${SVG} aria-hidden="true"><rect x="4" y="4" width="16" height="13" rx="2"/><path d="M4 11h16M8 17v3M16 17v3"/><circle cx="8" cy="14" r="1" fill="currentColor" stroke="none"/><circle cx="16" cy="14" r="1" fill="currentColor" stroke="none"/></svg>`,
  thunderstorm: `<svg ${SVG} aria-hidden="true"><path d="M19 14.5a3.5 3.5 0 0 0-.9-6.88A4.5 4.5 0 0 0 9.9 6.2 3 3 0 0 0 7 14"/><path d="M12.5 11.5l-2 3.5h3l-2 3.5"/></svg>`,
  rain: `<svg ${SVG} aria-hidden="true"><path d="M19 14.5a3.5 3.5 0 0 0-.9-6.88A4.5 4.5 0 0 0 9.9 6.2 3 3 0 0 0 7 14"/><path d="M8 18l-1 2.5M12 18l-1 2.5M16 18l-1 2.5"/></svg>`,
  warning: `<svg ${SVG} aria-hidden="true"><path d="M12 3l9 16H3z"/><path d="M12 10v4M12 17h.01"/></svg>`,
  alert: `<svg ${SVG} aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></svg>`,
  mappin: `<svg ${SVG} aria-hidden="true"><path d="M12 21s7-6.3 7-11a7 7 0 1 0-14 0c0 4.7 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/></svg>`,
  typhoon: `<svg ${SVG} aria-hidden="true"><path d="M12 12c3-3 8-2 8 2a3.5 3.5 0 0 1-6 2.4"/><path d="M12 12c-3 3-8 2-8-2a3.5 3.5 0 0 1 6-2.4"/><circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none"/></svg>`,
  fire: `<svg ${SVG} aria-hidden="true"><path d="M12 3c1.5 3 4 4.5 4 8a4 4 0 0 1-8 0c0-1.2.4-2 1-3 .2 1 .8 1.6 1.5 1.8C9.5 6.8 11 4.5 12 3z"/><path d="M12 21a4 4 0 0 0 4-4c0-2-1.5-3-2.5-4.5C12.8 13 12.5 14 12 14c-.8 0-1.3-1-1.6-1.8C9 13.5 8 14.7 8 17a4 4 0 0 0 4 4z"/></svg>`,
  hot: `<svg ${SVG} aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2 12h2M20 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4"/></svg>`,
};

// iOS-style status bar (time + signal / wifi / battery glyphs)
export function statusBar(time = "9:41") {
  return `
  <div class="statusbar">
    <span>${time}</span>
    <span class="right">
      <svg width="18" height="12" viewBox="0 0 18 12" fill="currentColor"><rect x="0" y="8" width="3" height="4" rx="1"/><rect x="5" y="5" width="3" height="7" rx="1"/><rect x="10" y="2.5" width="3" height="9.5" rx="1"/><rect x="15" y="0" width="3" height="12" rx="1"/></svg>
      <svg width="17" height="12" viewBox="0 0 17 12" fill="currentColor"><path d="M8.5 2.5c2.5 0 4.8 1 6.5 2.6l-1.2 1.3A7 7 0 0 0 8.5 4.6 7 7 0 0 0 3.2 6.4L2 5.1A9 9 0 0 1 8.5 2.5z"/><path d="M8.5 6.2c1.5 0 2.9.6 3.9 1.6l-1.2 1.3a3.5 3.5 0 0 0-5.4 0L4.6 7.8A5.5 5.5 0 0 1 8.5 6.2z"/><circle cx="8.5" cy="10.4" r="1.4"/></svg>
      <svg width="26" height="13" viewBox="0 0 26 13" fill="none"><rect x="1" y="1" width="21" height="11" rx="3" stroke="currentColor" stroke-width="1.3"/><rect x="3" y="3" width="16" height="7" rx="1.5" fill="currentColor"/><rect x="23" y="4" width="2" height="5" rx="1" fill="currentColor"/></svg>
    </span>
  </div>`;
}

// Phone device wrapper. `inner` is the .app-scroll content (TopBar + screen).
export function phone(inner, { notch = true } = {}) {
  return `<div class="phone">${notch ? '<div class="notch"></div>' : ''}<div class="screen"><div class="app-scroll">${inner}</div></div></div>`;
}
