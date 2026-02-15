/**
 * Redirect /settings → /dashboard/settings
 *
 * WHY: Settings used to live at /settings. Now it's inside the dashboard
 * layout at /dashboard/settings. This redirect ensures bookmarks and
 * any lingering links still work.
 */
import { redirect } from "next/navigation";

export default function SettingsRedirect() {
  redirect("/dashboard/settings");
}
