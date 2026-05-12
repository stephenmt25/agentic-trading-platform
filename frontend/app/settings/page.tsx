import { redirect } from "next/navigation";

/**
 * /settings is the profiles & settings surface; the canonical landing
 * section is Profiles per docs/design/05-surface-specs/06-profiles-settings.md.
 * The user-menu link in ChromeBar points here.
 */
export default function SettingsIndex() {
  redirect("/settings/profiles");
}
