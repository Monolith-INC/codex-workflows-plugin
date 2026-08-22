# Flutter Material 3 Design Rules

These rules are based on the [Material 3 Design Guidelines](https://m3.material.io/) and should be applied when refactoring Flutter widgets.

## 1. Layout & Adaptive Design

### Window Size Classes (Width Breakpoints)

- **Compact:** < 600dp (Phones in portrait) -> Use `NavigationBar`
- **Medium:** 600 – 839dp (Tablets in portrait, Foldables) -> Use `NavigationRail`
- **Expanded:** 840 – 1199dp (Tablets in landscape, Desktop) -> Use `NavigationRail` (Extended) or `NavigationDrawer` (Permanent)
- **Large:** 1200 – 1599dp (Laptops, Desktops)
- **Extra-large:** 1600dp+ (Large monitors)

### Canonical Layouts

- **List-detail:** Show list and detail side-by-side on Medium+ screens.
- **Supporting pane:** Show primary content with a side pane for filters/metadata on Medium+ screens.
- **Feed:** Single column on Compact/Medium, multi-column on Expanded+.

### Adaptive Implementation (Flutter)

- Use `AdaptiveScaffold` from `package:flutter_adaptive_scaffold`.
- Switch navigation components automatically using `AdaptiveScaffold.destinations`.
- Use `AdaptiveScaffold.secondaryBody` for List-detail or Supporting pane patterns.

## 2. Components

### Cards

- **Corner Radius:** 12dp.
- **Internal Padding:** 16dp.
- **Elevation:**
  - Elevated: Level 1 (Default), Level 2 (Hover).
  - Filled: Level 0.
  - Outlined: Level 0.

### Dialogs

- **Corner Radius:** 28dp.
- **Elevation:** Level 3.
- **Internal Padding:** 24dp for container, 16dp between content elements.
- **Adaptive Behavior:**
  - Compact: Center on screen or Full-screen dialog if content is complex.
  - Medium/Expanded: Fixed width or percentage of screen width (max-width typically 560dp).

### Buttons (Filled, Tonal, Outlined)

- **Height:** 40dp.
- **Corner Radius:** Stadium shape (fully rounded).
- **Padding:**
  - Text-only: 24dp horizontal.
  - With Icon: 16dp leading (icon side), 24dp trailing.

### Text Fields

- **Height:** 56dp (standard).
- **Content Padding:** 16dp horizontal.
- **Border Radius:**
  - Outlined: 4dp corners.
  - Filled: 4dp top corners, flat bottom.
- **Indicator Line (Filled):** 1dp (unfocused), 2dp (focused).

## 3. Flutter Implementation Patterns

### Button Style

```dart
FilledButton(
  style: FilledButton.styleFrom(
    minimumSize: const Size.fromHeight(40),
    padding: const EdgeInsets.symmetric(horizontal: 24),
    shape: const StadiumBorder(),
  ),
  onPressed: () {},
  child: const Text('Button Text'),
)
```

### Text Field Style

```dart
TextFormField(
  decoration: InputDecoration(
    border: OutlineInputBorder(borderRadius: BorderRadius.circular(4)), // Outlined
    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
  ),
)
```

### Adaptive Layout

```dart
AdaptiveScaffold(
  destinations: destinations,
  body: (_) => const PrimaryContent(),
  secondaryBody: (_) => const SidePaneContent(), // Visible on Medium+
)
```
