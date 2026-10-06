# Ready: F7 accessibility and responsiveness

## Done

Reduced motion
- CSS `@media (prefers-reduced-motion: reduce)`: busy halo pulse off (static glow stays), no body/particle/thread transitions. Already present since F3/F4, unchanged.
- JavaScript: `createRenderer` defaults `reducedMotion` from the media query and now listens for changes (`watchReducedMotion`). With it on, particles appear at the recipient as instant markers, threads appear fully drawn, snaps remove at once.
- `app.js`: `?motion=reduce` / `?motion=full` force the JavaScript behavior for testing (CSS keeps following the OS).

Keyboard and screen readers
- Bodies: `tabindex="0"`, `role="img"`, `aria-label` "`<name>`, `<state>`, `<role>`, folder `<folder>`", visible focus ring (`.body:focus-visible .core`).
- Particles: already focusable buttons from F6 (Enter/Space open the panel).
- Timeline ticks: now `<button class="tick">` with `aria-label` "Message from X to Y at HH:MM:SS" and tooltip; click or Enter opens the side panel for that message (`onTick`, new `timeline.messages()`), so history is browsable while scrubbed. Focus style on ticks. Slider and Live button are native controls. Status badge has `aria-live="polite"`.

Phone width
- `html, body { overflow-x: hidden }`, `.stage { overflow: hidden }` so SVG labels that stick out never cause horizontal scroll. 16 px gutters everywhere.
- Under 600 px: panel docks to the bottom (F6), ring labels grow (name 30, role 23, empty label 40 viewBox units), tighter top bar and strip. Orbit height budget accounts for the strip.
- Measured in a 390 px iframe: `scrollWidth === clientWidth === 386`, stage padding 16 px, name font 30 px. Both `messages` and `many` (15 sessions) fixtures render without overflow.

Docs: `docs/frontend/timeline.md` (`messages()`, `onTick`, tick buttons), `render.md` (focusable bodies, aria-label example, reduced-motion watcher and override), `app.md` (motion override, tick → panel, responsive notes), `README.md` (query parameters).

SPEC.md §8.2 F7 marked `[~] path-finder-18`.

## How to test

```
python3 -m http.server 8787 --bind 127.0.0.1 --directory frontend
```

1. `?fixture=messages&motion=reduce`: particles never fly; each appears as a resting dot at the recipient the moment the message arrives. The notify thread appears fully drawn at once and vanishes at once when `path-finder-e5` goes idle. (The halo still pulses because CSS follows the OS setting; enable "Reduce motion" in System Settings → Accessibility → Display to see the pulse stop and the transitions go away.)
2. Keyboard: press Tab from the page start. Order: status is skipped, bodies in ring order (focus ring on the body, label lights up), then arrived particles, then Live, ticks, slider, and the panel close button when open. Enter on a particle or tick opens the panel; Escape closes it.
3. Ticks: click the second tick (index 1): panel shows `path-finder-18` → `path-finder-e5` with the badge. Scrub the slider first, then click a tick: the panel still opens and the ring stays at the scrubbed instant.
4. Phone width: with DevTools device toolbar at 390×844 (or any viewport under 600 px): no horizontal scrollbar, 16 px gutters, panel docked at the bottom when a particle or tick is clicked, labels readable. Check `document.documentElement.scrollWidth === document.documentElement.clientWidth`.
5. Node: `timeline.md` example additions (`messages().at(-1).data.from` is `null`). DOM stub: a body has `tabindex="0"` and the documented `aria-label`; `button.tick` count is 7 after recording `messages.json` with `mountTimelineStrip` (needs the footer markup from `index.html`).

## Requests

1. Validator: the DOM-stub check of `mountTimelineStrip` needs `document.createElement`, `querySelector`, `addEventListener`, and `style` on elements; if the stub lacks those, test `timeline.messages()` in Node and the ticks in a browser.
2. Manager: F8 is next per your message. Everything public already has a one-line comment and a docs section; F8 will be a sweep for drift plus the DOM-stub-friendly notes the validator asked for.

## Blocked

Nothing.
