# RxDart: The Reactive Flow

## I. Stream Composition

1. **Declarative Mandate.** **Reject** manual `.listen()` inside business logic. Use operators (`map`, `switchMap`, `combineLatest`) to compose output streams from input streams.
2. **Operator Discipline.**
    * **Mandatory** `debounceTime` for user input.
    * **Mandatory** `distinctUnique` to prevent redundant emission processing.
    * **Mandatory** `switchMap` for network requests to cancel stale calls.

## II. Memory Safety

1. **Subscription Management.** If a `listen()` is unavoidable (e.g., in UI), it **must** be bound to a `CompositeSubscription` or handled by a flutter_hook to ensure disposal.
2. **Subject Restrictions.**
    * **BehaviorSubject:** **Approved** for State holding (current value access).
    * **PublishSubject:** **Approved** for Events (clicks, toasts).
    * **ReplaySubject:** **Restricted.** Use only with explicit bounds (`maxSize`) to prevent memory leaks.
