---
description: How to ensure all UI components and pages meet WCAG 2.1 AA accessibility standards
---

# Accessibility Standards (WCAG 2.1 AA)

Every frontend component and page in Arbiter AI **must** meet WCAG 2.1 Level AA compliance. Accessibility is not optional — it is a shipping requirement.

## Core Principles (POUR)

| Principle          | Meaning                           | Arbiter Examples                                               |
| ------------------ | --------------------------------- | -------------------------------------------------------------- |
| **Perceivable**    | Users can perceive the content    | Alt text on icons, color-contrast ratios, visible focus states |
| **Operable**       | Users can interact with the UI    | Keyboard navigation, no keyboard traps, touch targets ≥ 44px   |
| **Understandable** | Users can understand the content  | Clear labels, error messages, consistent navigation            |
| **Robust**         | Works with assistive technologies | Semantic HTML, ARIA roles, screen reader testing               |

## Steps for Every Component & Page

### 1. Semantic HTML First

Always use the correct semantic element — never `<div>` as a button or link.

```tsx
// ✅ CORRECT
<button onClick={handleUpload}>Upload Rulebook</button>
<nav aria-label="Main navigation">...</nav>
<main>...</main>

// ❌ WRONG
<div onClick={handleUpload} className="btn">Upload Rulebook</div>
<div className="nav">...</div>
```

### 2. ARIA Attributes Checklist

For every interactive component, verify:

- [ ] **Buttons** have descriptive text or `aria-label`
- [ ] **Icons** have `aria-hidden="true"` if decorative, or `aria-label` if meaningful
- [ ] **Form inputs** have associated `<label>` elements or `aria-label`
- [ ] **Modals/dialogs** use `role="dialog"`, `aria-modal="true"`, and `aria-labelledby`
- [ ] **Loading states** use `aria-busy="true"` and `aria-live="polite"` for status updates
- [ ] **Error messages** are linked via `aria-describedby` to their form field
- [ ] **Navigation landmarks** use `<nav>`, `<main>`, `<aside>`, `<header>`, `<footer>`
- [ ] **Dynamic content** (chat messages, verdicts) uses `aria-live="polite"`

### 3. Keyboard Navigation

Every interactive element must be:

- [ ] **Focusable** via Tab key (natural tab order, no positive `tabIndex` values)
- [ ] **Activatable** via Enter or Space
- [ ] **Escapable** — modals close with Escape key, focus returns to trigger element
- [ ] **No keyboard traps** — user can always Tab out of any component

**Arbiter-specific keyboard flows:**

| Flow             | Required Keyboard Support                       |
| ---------------- | ----------------------------------------------- |
| Chat interface   | Enter sends message, Shift+Enter for newline    |
| File upload      | Space/Enter opens file picker, Escape cancels   |
| Citation cards   | Enter/Space expands, Escape collapses           |
| Game catalog     | Arrow keys for grid navigation, Enter to select |
| Confidence badge | Tooltip accessible via focus (not hover-only)   |

### 4. Color & Contrast

- [ ] **Text contrast ratio ≥ 4.5:1** for normal text (≥ 3:1 for large text ≥ 18pt)
- [ ] **Interactive element contrast ≥ 3:1** against background
- [ ] **Never use color alone** to convey meaning
  - Confidence badge: use icon + text label, not just green/yellow/red
  - Error states: use icon + text + border, not just red color
  - Status indicators: combine color with shape or text

```tsx
// ✅ CORRECT — color + icon + text
<span className="confidence high">
  <CheckIcon aria-hidden="true" /> High Confidence (0.95)
</span>

// ❌ WRONG — color only
<span style={{ color: 'green' }}>0.95</span>
```

### 5. Focus Management

- [ ] Visible focus ring on all interactive elements (no `outline: none` without replacement)
- [ ] Focus moves logically into modals/dialogs when they open
- [ ] Focus returns to trigger element when modals close
- [ ] Skip-to-content link as the first focusable element on every page

```tsx
// Add to layout.tsx
<a href="#main-content" className="skip-link">
  Skip to main content
</a>
```

### 6. Media & Dynamic Content

- [ ] **Images** have alt text (`alt=""` for decorative images)
- [ ] **Icons** have `aria-label` or `aria-hidden`
- [ ] **Toast notifications** use `role="alert"` or `aria-live="assertive"`
- [ ] **Chat streaming responses** use `aria-live="polite"` on the message container
- [ ] **File upload progress** is announced via `aria-live`

### 7. Automated Accessibility Audit

Run `axe-core` or `eslint-plugin-jsx-a11y` on every component:

// turbo

```bash
# Install a11y linting (run once during setup)
cd frontend && npx eslint --ext .tsx,.ts src/ --rule '{"jsx-a11y/alt-text": "error", "jsx-a11y/anchor-is-valid": "error", "jsx-a11y/click-events-have-key-events": "error", "jsx-a11y/no-static-element-interactions": "error"}' 2>&1 | tail -30
```

### 8. Manual Screen Reader Checklist

Before shipping any page, test with VoiceOver (macOS):

- [ ] Page title is announced on navigation
- [ ] All interactive elements have accessible names
- [ ] Form fields announce their labels and error states
- [ ] Chat messages are read in order
- [ ] Citations announce source and page number
- [ ] Confidence level is announced (not just color)

## Component-Specific Requirements

| Component         | Accessibility Requirements                                                |
| ----------------- | ------------------------------------------------------------------------- |
| `ChatInterface`   | `aria-live="polite"` on message list, role="log", keyboard submit         |
| `CitationCard`    | Expandable with Enter/Space, `aria-expanded`, content announced on expand |
| `FileUpload`      | Drag-drop has keyboard alternative, progress announced, error associated  |
| `GameCard`        | Focusable, role="article" or semantic card, name announced                |
| `ConfidenceBadge` | Text label (not color-only), tooltip focusable, `aria-label`              |
| `ConflictAlert`   | `role="alert"`, `aria-live="assertive"`, icon + text (not color-only)     |
| `UpgradeBanner`   | Dismissable via keyboard, `role="banner"`, close button labeled           |
| `InstallPrompt`   | `role="dialog"`, keyboard dismissable, focus trapped while open           |

## Anti-Patterns to Avoid

- ❌ Using `<div onClick>` instead of `<button>`
- ❌ `outline: none` without a visible alternative focus indicator
- ❌ Color-only status indicators (red/green/yellow without text/icon)
- ❌ Mouse-only interactions (hover tooltips with no focus equivalent)
- ❌ Missing alt text on informational images
- ❌ Autoplaying animations without `prefers-reduced-motion` respect
- ❌ Form fields without labels
- ❌ Positive `tabIndex` values that break natural tab order
