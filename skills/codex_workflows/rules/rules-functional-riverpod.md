
# Functional Riverpod Pattern

## Context

Use this pattern when implementing Riverpod Notifiers that require complex state transitions, side effects (like debouncing), or logic branching.

## Principles

1. **Functional over Imperative**: Avoid `if/else` blocks. Use Dart 3 **Switch Expressions** for all branching logic.
2. **Immutability**: Avoid local mutable variables. Use functional pipelines to transform data.
3. **Self-Documenting Code**: Do not write comments explaining "what" the code does. The logic flow should be obvious from the structure.
4. **`fpdart` Integration**: Use `Option` types fornullable values or side-effect carriers (e.g., `Option<Timer>`).
5. **Side Effect Management**:
    - Use `ref.listen` to handle state transitions without rebuilding the provider.
    - Chain listeners using the cascade operator `..`.

## Example Implementation

```dart
@riverpod
class LoadingStatus extends _$LoadingStatus {
  // Use Option for side-effect carriers
  Option<Timer> _timer = none();

  @override
  bool build() {
    // Chain listeners with cascade operator
    ref
      ..listen(providerA, (_, __) => _handleTransition())
      ..listen(providerB, (_, __) => _handleTransition())
      ..onDispose(() => _timer.map((t) => t.cancel()));

    return _calculateState();
  }

  bool _calculateState() =>
      ref.read(providerA).isLoading ||
      ref.read(providerB).isRequesting;

  // Pattern matching for transitions
  void _handleTransition() => switch ((_calculateState(), state, _timer.isSome())) {
        (true, _, _) => _forceLoading(),      // Case: Should be loading -> Force it
        (false, true, false) => _startTimer(), // Case: Should be idle, but currently loading & no timer -> Start debounce
        _ => null,                             // Default: Do nothing
      };

  void _forceLoading() {
    _timer.map((t) => t.cancel());
    _timer = none();
    state = true;
  }

  void _startTimer() => _timer = some(
        Timer(
          const Duration(seconds: 3),
          () => state = false,
        ),
      );
}
```
