/**
 * SpacePilot Telemetry & Analytics Wrapper
 * Supports Google Analytics 4 (gtag) and PostHog with graceful no-op fallbacks.
 */

declare global {
  interface Window {
    gtag?: (...args: any[]) => void;
    posthog?: {
      capture: (event: string, properties?: Record<string, any>) => void;
      identify: (distinctId: string, userProperties?: Record<string, any>) => void;
    };
  }
}

export const telemetry = {
  // Track high-intent button clicks (e.g. CLI copy, Studio launch)
  trackClick: (buttonName: string, meta?: Record<string, any>) => {
    if (window.gtag) {
      window.gtag('event', 'button_click', {
        button_name: buttonName,
        ...meta,
      });
    }
    if (window.posthog?.capture) {
      window.posthog.capture('button_clicked', {
        button_name: buttonName,
        ...meta,
      });
    }
  },

  // Track take exploration & camera interaction
  trackDirectorAction: (action: string, meta?: Record<string, any>) => {
    if (window.gtag) {
      window.gtag('event', 'director_action', {
        action_type: action,
        ...meta,
      });
    }
    if (window.posthog?.capture) {
      window.posthog.capture('director_action', {
        action_type: action,
        ...meta,
      });
    }
  },

  // Track code snippet tab switches
  trackCodeSnippetView: (tab: string) => {
    if (window.gtag) {
      window.gtag('event', 'view_code_snippet', { tab });
    }
    if (window.posthog?.capture) {
      window.posthog.capture('code_tab_viewed', { tab });
    }
  },
};
