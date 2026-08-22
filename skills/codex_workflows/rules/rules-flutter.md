# Flutter: The View Stricture

**Codex Anchor**: `[[Knowledge/Dart_Flutter_Patterns]]`
*Read the anchor above during Planning Phase for UI purity rules, widget refactoring thresholds, and Dart 3+ Pattern usage.*

## I. Architecture (Separation of Concerns)

### Widget Purity

1. **Strict View Layer.** Widgets are pure declarations of UI. They must never contain business logic, data fetching, or complex transformation.
2. **Controller Binding.** Logic belongs in Controllers, ViewModels, or BLoCs. Widgets strictly bind to these state holders.
3. **Refactoring Threshold.** Reject any build method exceeding 30 lines. Reject any Widget class exceeding 100 lines. Decompose immediately.

### State Management

1. **Stateless Mandate.** Default to `StatelessWidget`.
2. **Modern State.** Prefer `flutter_hooks` for local ephemeral state (animation, scroll) and `Provider`/`GetX` for business state.
3. **Unidirectional Flow.** Data flows down; events flow up. Never mutate state directly from a child widget.
4. **Dart 3+ Features.** Use **Records** for multiple return values instead of custom classes or tuples when the data is local and transient.
5. **Immutability.** All data classes MUST be immutable (use `freezed`). Widgets MUST be immutable.

## II. Performance (Efficiency is Paramount)

### Rendering & Rebuilds

1. **Const Constructors.** Mandatory for all widgets and sub-widgets that do not depend on runtime parameters.
2. **Keys.** Mandatory for lists and stateful swaps.
3. **Builder Pattern.** Mandatory for dynamic lists (`ListView.builder`).

### Asset Management

1. **Vector Graphics.** Mandate SVGs for icons.
2. **Isolates.** Use `compute()` for any JSON parsing or heavy logic exceeding 8ms (1 frame).

## III. Style & Structure

### Composition

1. **Atomic Components.** Prefer many small, single-purpose widgets over monolithic "Page" widgets.
2. **Private Sub-widgets.** **Reject** helper methods (e.g., `_buildHeader()`). **Must** use small, private `StatelessWidget` classes.
3. **Records & Patterns.** Use Pattern Matching for complex UI state rendering (e.g., `switch (state) { ... }` with Records).

### Responsiveness

1. **Constraint-Based.** Use `Flex`, `Expanded`, and `LayoutBuilder` instead of hardcoded sizes.
2. **Safe Areas.** All root execution paths must account for `SafeArea`.
