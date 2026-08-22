# Flutter: Testing Protocols

## I. Testing Mandates

1. **Zero-regression Policy.** All fixed bugs **must** be accompanied by a regression test (Unit or Widget).
2. **New Feature Coverage.** All new business logic **must** have unit tests. All new UI components **must** have widget tests.

## II. Tools & Packages

1. **Unit Tests.** Use `package:test`.
2. **Widget Tests.** Use `package:flutter_test`.
3. **Integration Tests.** Use `package:integration_test`.
4. **Assertions.** strictly prefer `package:checks` over `package:matcher` for new tests due to better readability and type safety.
    * *Example:* `check(result).equals(expected);` instead of `expect(result, expected);`.

## III. Test Structure

1. **Pattern.** Tests **must** follow the `Arrange-Act-Assert` (or `Given-When-Then`) pattern.
2. **Mocks.** Prefer Fakes/Stubs over Mocks.
    * *Condition:* If Mocks are unavoidable, use `mockito` or `mocktail`.
