"use client";

import { useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

/**
 * Smart back-navigation hook for PWA standalone mode.
 *
 * Problem: In a PWA with `display: standalone`, there's no browser back button.
 * Users rely on in-app back arrows and the native swipe-back gesture.
 * If a user deep-links directly into a page (e.g. /session/abc), there's no
 * history to go back to — `router.back()` would leave the app or do nothing.
 *
 * Solution: Track whether the user has navigated within the app. If yes,
 * `router.back()` works correctly. If no (deep link or first page load),
 * fall back to a safe destination.
 *
 * @param fallback - Route to navigate to when there's no in-app history
 *                   (default: "/dashboard")
 */
export function useSmartBack(fallback = "/dashboard") {
  const router = useRouter();
  const hasNavigated = useRef(false);

  useEffect(() => {
    // After the first client-side navigation, Next.js will push a history entry.
    // We detect this by checking history.length on mount vs. a threshold.
    // In standalone PWA mode, history starts at 1 (the initial page).
    // After one in-app navigation it becomes 2+.
    // We also mark future navigations via the popstate listener.
    if (typeof window !== "undefined" && window.history.length > 2) {
      hasNavigated.current = true;
    }

    const onPopState = () => {
      hasNavigated.current = true;
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const goBack = useCallback(() => {
    if (hasNavigated.current || window.history.length > 2) {
      router.back();
    } else {
      router.push(fallback);
    }
  }, [router, fallback]);

  return goBack;
}
