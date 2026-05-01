import { redirect } from "next/navigation";

// /analyze is absorbed into /trade. Redirect for bookmarks.
export default function AnalyzeRedirect() {
  redirect("/trade");
}
