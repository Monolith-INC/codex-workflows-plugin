# Rule: Dart 3+ Strictness & Coding Standards

**Codex Anchor**: `[[Knowledge/Dart_Flutter_Patterns]]`
*Read the anchor above during Planning Phase if you require deep architectural context on state management or pattern rationale.*

## I. Async Safety

1. **Reject** `async void` methods (fire-and-forget) except for event handlers.
2. **Must** use `Future<void>` and `await` for all asynchronous operations.

## II. Error Handling

3. **Reject** silent failures. All `catch` blocks must handle recovery or rethrow/log.
4. Empty catch blocks are strictly prohibited.

## III. Modern Dart Patterns

5. **Prefer Records** for multiple return values instead of custom classes or tuples when data is local.
6. **Pattern Matching**: Use Pattern Matching for complex switch/if-case expressions (Dart 3+ feature).

## IV. Logging & Utilities

7. **Reject** `print()`. Use the `logging` package or `dart:developer.log`.
8. Adhere to the `Effective Dart` documentation standards for all public APIs.
