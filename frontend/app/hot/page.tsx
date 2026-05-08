import { redirect } from "next/navigation";

export default function HotRoot() {
  // Default landing per surface spec §1; symbol switcher lives in the
  // /hot/[symbol] header for everything else.
  redirect("/hot/BTC-PERP");
}
