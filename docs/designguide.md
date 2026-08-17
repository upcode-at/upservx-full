# Upcode Product Design Guide

> Shared design standards for every Upcode product and customer-facing surface.

**Scope:** web applications, mobile and desktop interfaces, product websites, command-line tools, and transactional communication<br>
**Version:** 1.0<br>
**Last updated:** 2026-08-17

This guide defines the common Upcode experience. It is intentionally independent of a specific product, framework, or component library. A product may extend the system where its domain requires it, but must not silently redefine shared semantics.

Until a shared token and component package is available, this document is the normative source. Every product must maintain a short implementation profile that maps its technology to this guide and records approved exceptions.

---

## 1. Goals and principles

### One family, distinct products

Every product should be recognizable as Upcode without becoming visually indistinguishable from the rest of the portfolio. Typography, interaction, accessibility, spacing, and semantic color meaning are shared. Product identity comes from its name, icon, approved imagery, and an optional accent color.

### Clarity before decoration

The current state, primary task, and consequence of an action must be clear at a glance. Decoration must never compete with content or system feedback.

### Consistent semantics

The same color, icon, component variant, and phrase must retain the same meaning across products. “Destructive”, “warning”, and “success” are system meanings, not local styling choices.

### Safe and reversible

Products should prevent accidental loss, explain consequences before irreversible actions, and offer undo or recovery where technically possible.

### Inclusive by default

Accessibility, keyboard use, localization, reduced motion, and narrow layouts are design inputs from the beginning rather than final checks.

### Progressive complexity

Show the information needed for the current task first. Advanced configuration remains discoverable without overwhelming common workflows.

---

## 2. System architecture

The design system has four layers. A lower layer may extend a higher layer, but must preserve its meaning.

| Layer | Owns | Examples |
|---|---|---|
| Upcode foundation | Brand, typography, spacing, accessibility, semantic colors | Focus behavior, danger meaning, type scale |
| Platform | Conventions required by an interaction environment | Web navigation, mobile touch targets, CLI output |
| Product | Product identity and domain-specific patterns | Product icon, optional accent, infrastructure status |
| Feature | Local composition of existing patterns | Backup form, billing table, onboarding step |

### 2.1 Decision precedence

When rules appear to conflict, apply them in this order:

1. Accessibility and user safety
2. Upcode foundation
3. Platform convention
4. Product profile
5. Feature preference

A product exception must include a reason, owner, affected surfaces, and review date. A feature-level exception must not become an undocumented parallel design system.

### 2.2 Token model

Use four token levels rather than copying raw values into components:

```text
Primitive value → semantic token → component token → product override
#ef4444        → brand          → button-primary → optional product mapping
#dc2626        → danger         → alert-error     → no semantic override
```

- Primitive values define the palette and scale.
- Semantic tokens describe meaning: `background`, `foreground`, `brand`, `danger`.
- Component tokens describe a role: `button-primary-background`, `field-border-focus`.
- Product overrides may change identity tokens, never status meaning or accessibility behavior.

Implementations may adapt naming to their platform, but the semantic mapping must be documented in the product profile.

---

## 3. Brand architecture

### 3.1 Naming

- Use **Upcode** as the master brand.
- Use the approved product name consistently in navigation, metadata, installation flows, and support content.
- On first reference, prefer “Upcode [Product]”. A shortened product name may be used afterward when context is unambiguous.
- Feature names are descriptive and sentence case. Avoid inventing sub-brands for ordinary features.

### 3.2 Product identity

Each product identity consists of:

- the Upcode master brand;
- an approved product name and short description;
- a product icon or mark;
- optional approved product imagery;
- one optional accent color that does not change semantic status colors.

Identity must not depend on color alone. A product must remain identifiable in monochrome, high-contrast, print, and favicon-sized contexts.

### 3.3 Logos and marks

- Use approved source assets; do not redraw, stretch, rotate, outline, or add effects to a logo.
- Preserve the asset's aspect ratio and built-in padding.
- Use the light mark on dark or photographic surfaces and the dark mark on light surfaces.
- Keep a clear area around the mark of at least the height of its main symbol.
- Pair multiple Upcode product marks only when the relationship between the products is relevant.
- Product icons must remain legible at 16, 24, 32, and 48px.
- Alternative customer branding must follow the customization rules in section 13.

### 3.4 Voice

Upcode products are direct, calm, capable, and respectful. They explain what happened without blame or unnecessary enthusiasm. Technical language is appropriate where it improves precision, but should not be used to make an interface sound more advanced.

---

## 4. Color system

### 4.1 Shared foundation

These values form the common Upcode baseline. Platform implementations must expose equivalent semantic tokens.

| Semantic token | Light | Dark | Purpose |
|---|---:|---:|---|
| `background` | `#fafbfc` | `#0f172a` | Application or page canvas |
| `foreground` | `#0f172a` | `#f8fafc` | Primary content |
| `surface` | `#ffffff` | `#1e293b` | Cards, panels, and controls |
| `surface-foreground` | `#1e293b` | `#f1f5f9` | Content on surfaces |
| `surface-subtle` | `#f8fafc` | `#334155` | Quiet grouping and selected rows |
| `muted-foreground` | `#64748b` | `#94a3b8` | Supporting content |
| `border` | `#e2e8f0` | `#334155` | Dividers and control borders |
| `input` | `#f1f5f9` | `#475569` | Input and unchecked-control surface |
| `brand` | `#ef4444` | `#f87171` | Upcode identity; not a text background |
| `primary` | `#dc2626` | `#f87171` | Primary action background |
| `on-primary` | `#ffffff` | `#1e1b4b` | Content on primary-action surfaces |
| `accent` | `#4f46e5` | `#818cf8` | Secondary emphasis and optional product identity |
| `on-accent` | `#ffffff` | `#1e1b4b` | Content on accent surfaces |
| `focus` | `#dc2626` | `#f87171` | Keyboard focus indication |

Products may map existing token names such as `card`, `popover`, `primary`, or `ring` to these roles. They must not make consuming components depend directly on hex values.

### 4.2 Semantic status colors

Status colors retain the same meaning in every product.

| Meaning | Light foreground | Dark foreground | Subtle surface |
|---|---:|---:|---:|
| Success / healthy / completed | `#15803d` | `#4ade80` | `currentColor` at 10% opacity |
| Warning / degraded / attention | `#b45309` | `#fbbf24` | `currentColor` at 10% opacity |
| Danger / failed / destructive | `#b91c1c` | `#f87171` | `currentColor` at 10% opacity |
| Information / running | `#1d4ed8` | `#60a5fa` | `currentColor` at 10% opacity |
| Inactive / unknown | `#64748b` | `#94a3b8` | Muted surface |

Rules:

- Pair status color with text and, where helpful, an icon or shape.
- Never use success green for a generic primary action.
- Never use warning or danger colors as a product accent.
- Brand red and danger red may be visually related, so destructive controls must also use explicit labels, a suitable icon, and confirmation when risk is material.
- Reserve pulsing indicators for genuinely live or changing state.

### 4.3 Product accent

An accent is optional. It may distinguish a product in illustrations, selected navigation, charts, or low-risk emphasis.

An accent must:

- have documented light and dark values;
- meet the required contrast in every intended foreground/background pairing;
- remain distinct from success, warning, danger, and information states;
- never replace focus indication or the Upcode master-brand mark;
- have a neutral fallback for monochrome and high-contrast contexts.

### 4.4 Data visualization

Use the shared series order for non-semantic categorical data:

| Series | Light | Dark |
|---|---:|---:|
| `data-1` | `#3b82f6` | `#60a5fa` |
| `data-2` | `#10b981` | `#34d399` |
| `data-3` | `#f59e0b` | `#fbbf24` |
| `data-4` | `#8b5cf6` | `#a78bfa` |
| `data-5` | `#ef4444` | `#f87171` |

- Use status colors only when the data actually carries that status meaning.
- Provide labels, legends, tooltips, or direct values; color alone is insufficient.
- Avoid more than five simultaneous categorical series without an alternate grouping strategy.
- Use a consistent scale and make zero, targets, and exceptional values explicit.

---

## 5. Typography

### 5.1 Families

| Role | Preferred stack | Use |
|---|---|---|
| Interface | `Inter, ui-sans-serif, system-ui, -apple-system, sans-serif` | Product UI and websites |
| Monospace | `ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace` | Code, IDs, paths, logs, tokens, and CLI |

Products may use the platform system font when loading Inter would harm performance, privacy, offline use, or native consistency. Do not introduce a different display font without brand approval.

### 5.2 Scale

| Role | Size | Weight | Line height |
|---|---:|---:|---:|
| Display | 36px | 700 | 1.15 |
| Page title | 30px | 700 | 1.2 |
| Section title | 20px | 600 | 1.3 |
| Card title | 18px | 600–700 | 1.3 |
| Body | 16px | 400 | 1.5 |
| UI / control | 14px | 500–600 | 1.4 |
| Metadata | 12px | 400–600 | 1.4 |

Native platforms may map the scale to their nearest standard text styles. Preserve hierarchy and readable line length rather than forcing a pixel value.

### 5.3 Usage

- Keep a logical heading order independent of visual size.
- Use no more than one page title per view.
- Use `muted-foreground` for supporting copy, not for essential instructions.
- Keep body text near 45–80 characters per line where content width is controllable.
- Use tabular numerals for changing metrics and aligned numeric tables when supported.
- Use monospace only for content whose structure benefits from fixed-width glyphs.

---

## 6. Spacing, shape, and elevation

### 6.1 Spacing scale

The base unit is 4px.

| Token | Value | Common use |
|---|---:|---|
| `space-1` | 4px | Tight icon or metadata spacing |
| `space-2` | 8px | Related controls, label to field |
| `space-3` | 12px | Compact groups |
| `space-4` | 16px | Standard component gap |
| `space-6` | 24px | Card padding and section gap |
| `space-8` | 32px | Large section or desktop page padding |
| `space-12` | 48px | Marketing and onboarding sections |
| `space-16` | 64px | Large editorial separation |

The parent owns layout spacing. Reusable components should not add unexplained external margins.

### 6.2 Radius

| Token | Value | Use |
|---|---:|---|
| `radius-sm` | 8px | Compact items and badges |
| `radius-md` | 12px | Fields, menus, alerts, dialogs |
| `radius-lg` | 16px | Cards and prominent controls |
| `radius-xl` | 20px | Large feature surfaces |
| `radius-full` | 9999px | Avatars, status dots, switches |

Product personality should not be created by arbitrary per-feature radii. A platform may use its native radius where that improves consistency.

### 6.3 Elevation

| Level | Purpose |
|---|---|
| 0 | Canvas and inline content |
| 1 | Cards and persistent panels |
| 2 | Menus, sticky controls, and hover elevation |
| 3 | Dialogs and critical overlays |

- Use borders for grouping before adding stronger shadows.
- Use translucency only when content remains readable over every possible background.
- Do not stack several glass or blurred surfaces.
- Elevation communicates hierarchy, not product identity.

---

## 7. Layout and responsive behavior

### 7.1 Grid

Use a 12-column desktop grid, an 8-column tablet grid, and a 4-column compact grid when a formal grid is needed. Ordinary application layouts may use simpler one-to-four-column compositions aligned to the same spacing scale.

Recommended web breakpoints:

| Name | Minimum width | Typical behavior |
|---|---:|---|
| Compact | 0 | One column, touch-safe actions |
| Small | 640px | Wider dialogs and paired controls |
| Medium | 768px | Two-column content, optional persistent navigation |
| Large | 1024px | Desktop shell and multi-column dashboards |
| Extra large | 1280px | Dense operational or analytical layouts |

Breakpoints describe available space, not a device model.

### 7.2 Page composition

A standard product view contains:

1. Context: breadcrumb or parent destination when needed
2. Page title and concise description
3. Primary action and relevant utilities
4. Status or summary information
5. Main task content
6. Secondary or advanced content

Rules:

- Start compact layouts with one column and add columns only when content benefits.
- Let action groups wrap; do not shrink labels into ambiguity.
- Keep primary content reachable when navigation collapses or becomes a drawer.
- Preserve horizontal scrolling for data that cannot be safely reformatted.
- Keep terminals, editors, maps, and log viewers edge-to-edge when their task benefits from maximum space.
- Test long names, localized copy, zoom at 200%, empty states, and validation messages.

### 7.3 Navigation

- Use destination nouns in navigation and action verbs in controls.
- Keep top-level choices stable and group them by user goal rather than internal architecture.
- Show the current location through more than color alone.
- Hide destinations the user cannot access when their existence is irrelevant; show disabled controls only when explaining the requirement helps the user.
- Use drawers, bottom navigation, or platform-native patterns on compact surfaces instead of squeezing a desktop sidebar.
- Preserve user context when moving between related destinations.

---

## 8. Core component behavior

The visual implementation may differ by platform, but behavior and semantics remain shared.

### 8.1 Buttons and actions

| Variant | Meaning |
|---|---|
| Primary | Main action in the current context; normally one per action group |
| Secondary | Valid alternative action with lower emphasis |
| Outline | Neutral utility or cancel action |
| Ghost | Compact navigation or low-emphasis utility |
| Success | Explicit positive operation when success itself is the meaning |
| Destructive | Delete, revoke, stop, disconnect, or another dangerous operation |
| Link | Navigation embedded in text or low-emphasis content |

Standard control heights are 32px compact, 40px default, and 48px prominent or touch-focused.

- Use specific verb-first labels: “Create workspace”, “Save changes”, “Restart service”.
- Use one primary action per group; a page may have separate groups with separate context.
- Keep async controls stable in width, indicate progress, and prevent duplicate activation.
- Icon-only actions need an accessible name and should be limited to universally understood or repeatedly learned actions.
- Cancellation is neutral, not destructive.
- Destructive actions name the affected resource and explain irreversible consequences.

### 8.2 Forms

- Every field has a persistent label; placeholders provide examples, not names.
- Put help and validation beside the relevant field.
- Validate format as the user works and validate business rules at submission.
- Preserve entered values after recoverable errors.
- Mark optional fields instead of marking every required field where most are required.
- Group fields by task and use progressive disclosure for advanced settings.
- A switch is for an immediate binary setting. Use a checkbox or explicit Save flow for staged changes.
- Sensitive values are masked by default and are never echoed into logs or notifications.

### 8.3 Cards and panels

- Use a card for meaningful grouping, selection, or elevation, not for every block of content.
- A card may have a title, description, compact action, content, and footer.
- Keep card action placement consistent within a product.
- Avoid nested cards. Use sections, dividers, or subtle surfaces inside a card.
- Entire-card click targets must still expose a clear accessible name and visible focus.

### 8.4 Status, badges, and progress

- Badges contain short, stable state labels.
- Success, warning, danger, information, and inactive states follow the shared semantic colors.
- Show progress as determinate when a reliable value exists; otherwise use an indeterminate indicator and status text.
- Explain long-running background tasks and allow the user to leave the view safely.
- Do not show “100%” before work is actually complete.

### 8.5 Alerts and notifications

- Success feedback confirms the result without interrupting the next task.
- Warning feedback explains risk before the user commits.
- Error feedback says what failed, what remains unchanged, and what the user can do next.
- Information feedback is neutral and actionable when an action is available.
- Persistent context belongs inline; transient operation feedback may use a toast or banner.
- Critical feedback must not disappear before it can be understood.
- Never expose stack traces, internal identifiers, or secrets in general user-facing feedback.

### 8.6 Dialogs

- Use dialogs for focused, interruptible decisions or short forms.
- Always provide a title and an accessible description when the purpose is not self-evident.
- Put the primary action last in left-to-right layouts.
- Stack footer actions on narrow screens.
- Do not use a dialog for a long, multi-stage workflow that needs navigation, history, or persistent context.
- Confirmation copy states the action, target, consequence, and recovery option.

### 8.7 Tabs

Tabs switch between peer views in the same context. They are not progress steps or global navigation. Keep labels short, preserve keyboard behavior, and allow scrolling or a different pattern when tabs do not fit.

### 8.8 Tables and collections

- Use tables for comparison across consistent attributes.
- Align numbers and units; put row actions in a predictable final column.
- Provide sorting or filtering only when it supports a real task.
- Show loading skeletons, useful empty states, and recoverable errors.
- Preserve horizontal scrolling or switch to an intentional list/card representation on narrow screens.
- Bulk selection states the number selected and keeps the scope visible.

### 8.9 Empty, loading, and error states

Every data-driven surface defines:

- first-use empty state with a primary next step;
- no-results state that preserves filters and offers a way back;
- initial loading state that reflects the eventual layout;
- background refresh state that does not erase existing content;
- partial failure state when some information remains usable;
- permission state that explains how access is obtained when appropriate.

---

## 9. Icons, illustration, and imagery

### 9.1 Icons

Lucide is the preferred interface icon family for web products. Other platforms may use an equivalent outline family or native system icons.

- Default UI icon: 16px.
- Touch or standalone action: 20–24px.
- Empty state or feature illustration: 24–48px when appropriate.
- Use a consistent stroke style in one context.
- Reuse the same icon for the same concept across products.
- Icons supplement unfamiliar labels; they do not replace them.
- Do not use emoji as structural interface icons.

### 9.2 Imagery

- Use imagery to explain a product, represent content, or establish tone—not to fill empty space.
- Apply one coherent illustration and photography style within the Upcode portfolio.
- Provide useful alternative text when an image conveys information; use empty alt text for decoration.
- Avoid screenshots containing real credentials, personal data, customer infrastructure, or unlicensed content.
- Optimize assets for the delivery context and avoid text baked into images.

---

## 10. Motion and feedback

Motion explains change, hierarchy, or direct manipulation.

| Motion | Duration | Use |
|---|---:|---|
| Immediate | 100–150ms | Hover, press, small color change |
| Standard | 200–250ms | Menus, tabs, compact layout transitions |
| Emphasized | 300–400ms | Dialogs or meaningful spatial transitions |

- Prefer opacity and transform over layout-heavy animation.
- Do not animate static status merely to attract attention.
- Keep repeated spinning and pulsing to active processes.
- Respect `prefers-reduced-motion` and native reduced-motion settings.
- A reduced-motion experience must retain all state information.
- Never delay a critical action solely to complete an animation.

---

## 11. Platform adaptations

### 11.1 Web applications

- Support keyboard, pointer, touch, browser zoom, and responsive reflow.
- Use semantic HTML and proven accessible primitives.
- Preserve URLs and browser history for destinations and shareable state where appropriate.
- Do not assume hover is available.

### 11.2 Mobile and touch

- Important touch targets are at least 44×44px.
- Use native gestures only when an equivalent visible control exists.
- Keep destructive actions away from common navigation targets.
- Respect safe areas, virtual keyboards, and platform back behavior.
- Prefer bottom sheets or full-screen flows over cramped desktop dialogs.

### 11.3 Desktop applications

- Respect platform menus, window behavior, shortcuts, and focus conventions.
- Persist window and panel state only when it improves return workflows.
- Do not reproduce browser chrome inside a native shell without a task need.

### 11.4 Product and marketing websites

- The product value and primary next step should be clear in the first meaningful viewport.
- Marketing hierarchy may use the display scale and more generous spacing, but shares brand, accessibility, and content rules.
- Claims, pricing, compatibility, and availability must be precise and current.
- Product screenshots must match a real or clearly labeled conceptual interface.

### 11.5 Command-line interfaces

- Plain text is the baseline; color and symbols add meaning but never carry it alone.
- Use stable exit codes, actionable errors, and predictable `--help` output.
- Send machine-readable results to stdout and diagnostics to stderr where applicable.
- Support `NO_COLOR`, non-interactive environments, and structured output when automation is expected.
- Never print secrets by default.

### 11.6 Transactional email and notifications

- Lead with the event, affected product/resource, and required action.
- Keep brand treatment secondary to the message.
- Include a plain-text alternative and a destination that remains understandable without imagery.
- Do not include credentials or unnecessarily sensitive operational data.

---

## 12. Accessibility

Upcode targets WCAG 2.2 AA for digital product interfaces.

All new and updated experiences must:

- support keyboard navigation and visible focus;
- use native semantics before adding custom roles;
- provide accessible names for icon-only controls;
- associate labels, help, and errors with form controls;
- preserve a logical heading and reading order;
- maintain at least 4.5:1 contrast for normal text and 3:1 for large text and essential UI boundaries;
- avoid relying on color, position, sound, or animation alone;
- support 200% zoom without loss of content or function;
- reflow at narrow widths without forcing two-dimensional scrolling except for inherently two-dimensional content;
- provide reduced-motion behavior;
- expose asynchronous status through an appropriate live-region or platform announcement;
- keep time limits adjustable unless they are essential;
- provide text alternatives for meaningful non-text content.

Automated checks are necessary but not sufficient. Test keyboard flow, screen-reader naming, zoom/reflow, contrast, reduced motion, and error recovery manually for every major workflow.

---

## 13. Themes, branding, and customization

### 13.1 Theme support

- Products should support light, dark, and system themes when their platform supports them.
- Themes preserve hierarchy and semantic meaning; they are not independent visual identities.
- Avoid theme transitions that flash, disorient, or expose an unreadable intermediate state.
- Store user preference without overriding an explicit system-accessibility requirement.

### 13.2 Customer branding

Products that allow customer branding must define controlled slots rather than exposing arbitrary CSS.

Allowed slots may include:

- organization name;
- approved logo formats;
- login or landing illustration;
- constrained accent color;
- support link and contact text.

Customization must not:

- remove legally or contractually required Upcode attribution;
- change success, warning, danger, information, focus, or permission semantics;
- reduce contrast below the accessibility target;
- inject executable markup or remote code;
- break product identification in support, security, or consent contexts.

Always provide a safe fallback when a customer asset is missing, invalid, unreadable, or unavailable.

---

## 14. Content and localization

### 14.1 Product language

- Use sentence case for headings, labels, and actions.
- Use nouns for destinations and verb-first phrases for actions.
- Prefer the user's goal over the implementation detail.
- State what happened before giving technical detail.
- Avoid blame, filler, idioms, and jokes in errors or critical workflows.
- Use an ellipsis only when an action opens another step before taking effect.
- Use the exact same term for the same concept across products.

Examples:

| Avoid | Prefer |
|---|---|
| `Submit` | `Create workspace` |
| `Invalid input` | `Enter a hostname without spaces.` |
| `Delete?` | `Delete “web-01”? This cannot be undone.` |
| `Something went wrong` | `The service could not be restarted. Check its logs and try again.` |

### 14.2 Localization

- Do not concatenate translated sentence fragments.
- Allow labels and controls to grow; do not assume English length.
- Use locale-aware dates, times, numbers, pluralization, and sorting.
- Store machine values independently from localized display values.
- Do not embed interface text in images.
- Specify the language of a page, document, or message for assistive technology.
- Product profiles list supported locales and the fallback locale.

### 14.3 Sensitive content

Format code, IDs, paths, versions, and logs with the monospace family. Never place secrets in URLs, notifications, screenshots, analytics labels, clipboard previews, or persistent activity text.

---

## 15. Product implementation profile

Every product keeps a profile beside its product documentation. Use this template:

```md
# [Product] design implementation profile

- Product owner:
- Design/engineering owner:
- Supported platforms:
- Supported themes:
- Supported locales and fallback:
- Foundation version:
- Component library or native toolkit:
- Token mapping location:
- Approved logo/icon assets:
- Optional product accent (light/dark):
- Primary navigation pattern:
- Domain-specific status vocabulary:
- Accessibility test workflow:
- Documented exceptions, owners, and review dates:
- Migration status and known legacy patterns:
```

Product profiles document implementation; they do not duplicate the foundation. Domain-specific components should reference the shared behavior they extend.

### 15.1 Adding a shared pattern

A pattern belongs in the Upcode foundation when it:

- appears or is planned in at least two products;
- carries a shared semantic meaning;
- solves a common accessibility or interaction problem; or
- would otherwise create visible portfolio inconsistency.

Before adding it, define its purpose, anatomy, states, keyboard/touch behavior, responsive behavior, content guidance, accessibility requirements, and token dependencies.

### 15.2 Changing the foundation

Foundation changes require:

1. A documented user or consistency problem
2. Review of impact across existing products and platforms
3. Accessible light/dark and responsive specifications
4. A versioned migration path
5. Updates to examples, profiles, and automated checks where applicable

Do not remove or silently redefine a token or pattern while a supported product still depends on it.

---

## 16. Cross-product review checklist

Before releasing a new or substantially changed interface, verify:

- [ ] The product follows the Upcode foundation and has a current implementation profile.
- [ ] Product identity remains recognizable without relying on color alone.
- [ ] Product accent and customization preserve semantic status meaning.
- [ ] Light, dark, system, monochrome, and high-contrast contexts remain understandable where supported.
- [ ] Typography, spacing, radii, elevation, and icons follow the shared system.
- [ ] Primary, secondary, success, warning, and destructive actions are semantically correct.
- [ ] Loading, empty, no-results, partial-error, permission, disabled, and success states are designed.
- [ ] Forms preserve input, explain errors, and protect sensitive data.
- [ ] Navigation works for keyboard, pointer, touch, narrow layouts, and browser/platform history as applicable.
- [ ] The experience works with long content, localization, and 200% zoom.
- [ ] Focus, contrast, semantics, announcements, and reduced motion were manually tested.
- [ ] Destructive actions state the target, consequence, and recovery option.
- [ ] Product claims, screenshots, links, support information, and compatibility details are current.
- [ ] Any exception has a reason, owner, scope, and review date.
