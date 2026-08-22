# Rules for Riverpod Development

## 1. Code Generation

* **Mandatory Usage:** All NEW providers MUST be created using `riverpod_generator`.
* **Syntax:** Use the `@riverpod` annotation.
  * **AutoDispose:** Enabled by default. No argument needed (e.g., `@riverpod`).
  * **KeepAlive:** Explicitly use `@Riverpod(keepAlive: true)` for providers that must persist state (e.g., user session, complex navigation state), but preferred approach is to let them dispose and restore state from a repository/cache.

## 2. Provider Structure

* **Class-Based Notifiers:** REQUIRED for any provider that exposes methods to modify state (side effects).
  * **Pattern:** `class MyNotifier extends _$MyNotifier { ... }`
* **Functional Providers:** PERMITTED only for read-only data fetching or transformation.
* **Build Method:**
  * **No Side Effects:** The `build()` method MUST be pure. NEVER trigger navigation, snackbars, or write to other providers inside `build()`.
  * **Async Initialization:** Return `Future<T>` or `Stream<T>` if data retrieval is asynchronous. NOT `AsyncValue<T>`.

## 3. Data Fetching & Refreshes

* **Refresh Logic:**
  * **Consumers:** Use `ref.refresh(provider.future)` to re-fetch data.
  * **Pull-to-Refresh:** In UI, `onRefresh` callbacks MUST await the future returned by `ref.refresh`.
* **Loading States:**
  * **Preserve Data:** When refreshing, Riverpod keeps the previous data while loading. UIs MUST handle `AsyncValue` pattern matching to show existing data during a refresh (background update) instead of wiping the screen with a loader.
  * **Pattern:**

  ```dart
  switch (asyncValue) {
    AsyncValue(:final value?) => DataWidget(value),
    AsyncError(:final error) => ErrorWidget(error),
    _ => const LoadingWidget(),
  }
  ```

## 4. Cancellation & Disposal

* **Cleanup:** Providers interacting with external resources (HTTP clients, streams, controllers) MUST register a disposal callback.

    ```dart
    ref.onDispose(() {
      client.close();
    });
    ```

* **Debouncing:** For search-as-you-type, use the disposal check pattern:

    ```dart
    await Future.delayed(const Duration(milliseconds: 500));
    if (didDispose) return; // Stop if provider was disposed during delay
    ```

## 5. Interactions

* **Reading Providers:**
  * **Inside `build`:** ALWAYS use `ref.watch`.
  * **Inside callbacks (onPressed):** ALWAYS use `ref.read`.
  * **Inside Notifiers:** Use `ref.read` to fetch other notifiers for side effects.
* **Listeners:** Use `ref.listen` within the widget `build` method for one-off events (navigation, showing errors).

## 6. Project Specific Constraints (Lono Mobile)

* **Legacy Interop:** When a new `riverpod_generator` provider needs to interact with legacy `StateNotifierProvider`s, use `ref.read` cautiously.
* **Http Client:** Always create a new `Client` in the method or `build` scope, and ensure it is closed via `ref.onDispose`.

## 7. Anti-Patterns (Forbidden)

* **DO NOT** use `.family` parameter for dynamic provider creation inside loops unless absolutely necessary.
* **DO NOT** manually catch errors in `build()` and return `AsyncData(null)`. Let the error propagate to `AsyncError`.
* **DO NOT** modify local widget state (ephemeral state) using Riverpod.
