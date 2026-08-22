# Riverpod API & Architecture Rules

## 1. Provider Selection

- **Use `@riverpod` Generator**: Prioritize code generation for all new providers to ensure type safety and boilerplate reduction.
- **`FutureProvider`**: Use for simple, read-only data fetching (GET requests) that benefits from automatic caching and lifecycle management.
- **`AsyncNotifierProvider`**: Use for complex data fetching, data mutations (POST/PUT/DELETE), or when manual state management/optimistic updates are required.

## 2. Architecture (Repository Pattern)

- **Decouple Network Logic**: **NEVER** place direct `http` or `dio` calls inside a Provider.
- **Repository Interface**: Define an abstract class (interface) for each feature's data source (e.g., `IUserRepository`).
- **Repository Provider**: Create a simple `Provider` that returns the Repository implementation.
- **Consumption**: Providers should fetch data by watching the Repository Provider:

  ```dart
  @riverpod
  Future<Data> myData(MyDataRef ref) {
    return ref.watch(myRepositoryProvider).fetchData();
  }
  ```

## 3. UI Integration

- **Pattern Matching**: ALWAYS use `switch(asyncValue)` or `asyncValue.when` to handle the three states: **Data**, **Error**, and **Loading**.
- **State Priority**: Handle states in this order to ensure responsiveness:
    1. **Data** (Show content)
    2. **Error** (Show error message/retry)
    3. **Loading** (Show progress indicator)
- **Non-Blocking Refresh**: Use `asyncValue.isRefreshing` check to show a non-intrusive progress indicator (e.g., linear progress bar) instead of replacing the entire UI with a loading spinner during a refresh.

## 4. Error Handling & Resilience

- **Network Timeouts**: **CRITICAL**. Always configure the underlying network client with a reasonable timeout (e.g., 10-15 seconds) to prevent the UI from hanging indefinitely in a "Loading" state.
- **Domain Errors**: Map raw network exceptions (e.g., `SocketException`, `HttpException`) to domain-specific errors in the Repository layer before they reach the Provider.

## 5. Caching & Lifecycle

- **Invalidation**: Use `ref.invalidate(provider)` to clear cache and forcibly trigger a re-fetch.
- **Persistence**: Use `ref.keepAlive()` (or `keepAlive: true` in annotation) to prevent immediate disposal of cached data when the UI unmounts, if the data is expensive to fetch.

## 6. Testing

- **Mocking**: Test providers by determining the `RepositoryProvider` override behavior in a `ProviderScope` or `ProviderContainer`.
- **State Verification**: For async providers, verify the state transitions: `AsyncLoading` -> `AsyncData` or `AsyncLoading` -> `AsyncError`.
