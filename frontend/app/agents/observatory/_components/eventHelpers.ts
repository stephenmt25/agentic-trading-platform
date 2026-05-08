import type { AgentKind } from "@/components/agentic/AgentAvatar";
import { KIND_TO_BACKEND } from "./Roster";

const BACKEND_TO_KIND: Record<string, AgentKind> = Object.fromEntries(
  Object.entries(KIND_TO_BACKEND).map(([k, v]) => [v, k as AgentKind])
) as Record<string, AgentKind>;

export function backendIdToKind(id: string): AgentKind | null {
  return BACKEND_TO_KIND[id] ?? null;
}
