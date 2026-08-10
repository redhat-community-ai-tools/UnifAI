/**
 * Security helpers for the OAuth "sign in" popup flow (`credentials_callback`
 * postMessage) shared by `BuiltInElementCard` and `FieldValidationTwoFactorAuth`.
 *
 * The popup is redirected by the external authorization server straight to
 * our identity service's callback route — a different origin than the
 * frontend — which then relays the result back via
 * `window.opener.postMessage()`. A window reference alone (`event.source`)
 * isn't enough to trust the message, since the popup could later navigate to
 * another origin while keeping the same `Window` object. We require both:
 *   - the message was sent by the exact popup window we opened
 *     (`event.source === popup`), and
 *   - it came from the origin we actually told the authorization server to
 *     redirect back to (`event.origin === expectedCallbackOrigin`).
 *
 * The identity service's public origin isn't exposed to the client via any
 * runtime config today, but it doesn't need to be: every OAuth authorization
 * URL we open the popup with already carries a `redirect_uri` query param
 * set to that callback URL (see `OAuth2Strategy.initiate`, server-side), so
 * we recover the expected origin straight from the URL used to open the
 * popup instead of introducing new config plumbing.
 */

export function getExpectedCallbackOrigin(authorizationUrl?: string | null): string | null {
  if (!authorizationUrl) return null;
  try {
    const redirectUri = new URL(authorizationUrl).searchParams.get('redirect_uri');
    if (!redirectUri) return null;
    return new URL(redirectUri).origin;
  } catch {
    return null;
  }
}

/** Validates an incoming `message` event against the popup we opened and its expected callback origin. */
export function isTrustedCredentialsCallback(
  event: MessageEvent,
  popup: Window | null,
  authorizationUrl?: string | null,
): boolean {
  if (event.data?.type !== 'credentials_callback') return false;
  if (!popup || event.source !== popup) return false;
  const expectedOrigin = getExpectedCallbackOrigin(authorizationUrl);
  return !!expectedOrigin && event.origin === expectedOrigin;
}
