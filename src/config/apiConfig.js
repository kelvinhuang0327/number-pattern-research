/**
 * Shared API origin and URL helpers.
 * Keep frontend modules on one consistent backend host.
 */
export function getApiOrigin() {
    const browserWindow = globalThis?.window;
    if (browserWindow) {
        const host = browserWindow.location.hostname;
        if (host === 'localhost' || host === '127.0.0.1') {
            // Use IPv4 loopback to avoid localhost IPv6 mismatch.
            return 'http://127.0.0.1:8002';
        }
    }

    // Fallback for non-local deployment.
    return 'https://your-api-domain.com';
}

export function getApiUrl(path) {
    return `${getApiOrigin()}${path}`;
}
