import { redirect } from "next/navigation";

export default function HotRoot() {
  // Default landing matches the symbols ingestion currently publishes
  // (services/ingestion/src/main.py:47 — BTC/USDT, ETH/USDT). The surface
  // spec said BTC-PERP; we'll track futures when ingestion does.
  redirect("/hot/BTC-USDT");
}
