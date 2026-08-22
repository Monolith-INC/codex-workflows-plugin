# GoRouter (Legacy): The Taming Protocol

## I. Route Identity (The Source of Truth)

1. **String Prohibition.** **Reject** hardcoded route strings (e.g., `'/details'`) inside Widgets or Logic.
2. **Constants Mandate.** All route paths and names **must** be defined as `static const` strings in a centralized `AppRoutes` class.
3. **Naming Convention.** Route names **must** mirror their path structure (e.g., `static const userDetails = 'user-details'`) to avoid collision.

## II. Navigation Service (Encapsulation)

1. **Wrapper Mandate.** Widgets **must not** call `GoRouter.of(context)` or `context.go()` directly.
2. **Navigator Facade.** All navigation actions **must** pass through a specialized `AppNavigator` service class.
    * *Correct:* `navigator.goToUserDetails(id)`
    * *Incorrect:* `context.go(AppRoutes.userDetails, extra: id)`
3. **Argument safety.** The `AppNavigator` is responsible for bundling arguments. It **must** validate inputs before attempting the route transition.

## III. Data Extraction

1. **Safe Parsing.** **Reject** direct access to `state.pathParameters` inside the UI.
2. **Factory Extraction.** You **must** implement a `RouteArgs.fromState(GoRouterState state)` factory for every route receiving data. This creates a firewall against null/malformed parameters crashing the build method.
3. **Fallback Policy.** If parameter extraction fails, the factory **must** throw a specific `RouteException` that redirects the user to a 404 or Error page instantly.
