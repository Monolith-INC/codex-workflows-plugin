# Provider: The Dependency Graph

## I. Scoping & Access

1. **Strict Scoping.** Providers **must** be initialized at the lowest common ancestor of the widgets that need them. Global providers are **restricted** to Authentication and Theme.
2. **Selector Mandate.** **Reject** `Consumer` or `context.watch` if the widget only requires a slice of the state. Use `Selector<T, S>` to prevent unnecessary rebuilds.
3. **No Logic in UI.** `Provider` calls inside `build()` methods **must** strictly be for access. Logic execution belongs in `onPressed` callbacks or `initState`.

## II. Dependency Injection

1. **Interface Binding.** **Always** provide concrete implementations against abstract interfaces (e.g., `Provider<AuthRepo>(create: (_) => AuthRepoImpl())`).
2. **Lazy Loading.** Lazy initialization is **mandatory**. Eager loading is **prohibited** except for services strictly required at startup (e.g., LocalStorageService).
3. **Disposal.** Explicitly implement `dispose` in your ChangeNotifiers to close streams and controllers.
