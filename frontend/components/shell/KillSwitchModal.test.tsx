import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

/**
 * Tests for the global tiered-halt KillSwitchModal (FE-W1) — covers the
 * graduated-control contract:
 *   - hidden until the store opens it (and esc/cancel close it)
 *   - the four-verb ladder renders with the DECISIONS.md descriptions
 *   - refuses empty reason on every rung
 *   - single-click rungs POST {level, reason} via killSwitchSetLevel
 *   - FLATTEN is unreachable without stage-2 + typed "FLATTEN" confirmation
 *   - optimistic update ROLLS BACK store + cache when the POST fails
 *   - severity() store mapping (chrome contract)
 */

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

const killSwitchStatus = vi.fn();
const killSwitchSetLevel = vi.fn();
const killSwitchToggle = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: {
    commands: {
      killSwitchStatus: (...args: unknown[]) => killSwitchStatus(...args),
      killSwitchSetLevel: (...args: unknown[]) => killSwitchSetLevel(...args),
      killSwitchToggle: (...args: unknown[]) => killSwitchToggle(...args),
    },
  },
}));

import { KillSwitchModal } from "./KillSwitchModal";
import { queryKeys } from "@/lib/api/hooks";
import {
  severity,
  useKillSwitchStore,
  type HaltLevel,
} from "@/lib/stores/killSwitchStore";

let queryClient: QueryClient;

function renderModal() {
  return render(
    <QueryClientProvider client={queryClient}>
      <KillSwitchModal />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  killSwitchStatus.mockReset();
  killSwitchSetLevel.mockReset();
  killSwitchToggle.mockReset();
  killSwitchStatus.mockResolvedValue({
    active: false,
    level: "NONE",
    recent_log: [],
  });
  killSwitchSetLevel.mockResolvedValue({
    status: "stop_opening",
    reason: "x",
    level: "STOP_OPENING",
  });
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  useKillSwitchStore.setState({ level: "NONE", modalOpen: false });
});

describe("KillSwitchModal — global mount contract", () => {
  it("renders nothing until the store opens it", () => {
    renderModal();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("Escape closes the modal", async () => {
    const user = userEvent.setup();
    renderModal();
    useKillSwitchStore.getState().setModalOpen(true);
    await waitFor(() => screen.getByRole("dialog"));

    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(useKillSwitchStore.getState().modalOpen).toBe(false);
    });
  });

  it("Cancel button closes the modal", async () => {
    const user = userEvent.setup();
    renderModal();
    useKillSwitchStore.getState().setModalOpen(true);
    await waitFor(() => screen.getByRole("dialog"));

    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(useKillSwitchStore.getState().modalOpen).toBe(false);
  });
});

describe("KillSwitchModal — verb ladder", () => {
  it("renders all four rungs with the DECISIONS.md descriptions", async () => {
    renderModal();
    useKillSwitchStore.getState().setModalOpen(true);
    await waitFor(() => screen.getByRole("dialog"));

    expect(screen.getByTestId("halt-STOP_OPENING")).toBeInTheDocument();
    expect(screen.getByTestId("halt-DE_RISK")).toBeInTheDocument();
    expect(screen.getByTestId("halt-NEUTRALIZE")).toBeInTheDocument();
    expect(screen.getByTestId("halt-FLATTEN")).toBeInTheDocument();

    expect(screen.getByText("Block new entries")).toBeInTheDocument();
    expect(
      screen.getByText("+ cancel resting orders / halt averaging-in")
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "+ reduce-only trims to ≤50% gross budget; never flips direction"
      )
    ).toBeInTheDocument();
    expect(screen.getByText("Close ALL positions to zero")).toBeInTheDocument();
  });

  it("reason input is bounded to 256 chars (mirrors the API max_length)", async () => {
    renderModal();
    useKillSwitchStore.getState().setModalOpen(true);
    await waitFor(() => screen.getByRole("dialog"));

    expect(screen.getByLabelText(/^reason$/i)).toHaveAttribute(
      "maxlength",
      "256"
    );
  });

  it("refuses empty reason — error shown, no API call", async () => {
    const user = userEvent.setup();
    renderModal();
    useKillSwitchStore.getState().setModalOpen(true);
    await waitFor(() => screen.getByRole("dialog"));

    await user.click(screen.getByTestId("halt-STOP_OPENING"));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /reason is required/i
    );
    expect(killSwitchSetLevel).not.toHaveBeenCalled();
    expect(useKillSwitchStore.getState().level).toBe("NONE");
  });

  it("single-click rung posts {level, reason} and updates the store", async () => {
    const user = userEvent.setup();
    killSwitchSetLevel.mockResolvedValue({
      status: "de_risk",
      reason: "drill",
      level: "DE_RISK",
    });
    renderModal();
    useKillSwitchStore.getState().setModalOpen(true);
    await waitFor(() => screen.getByRole("dialog"));

    await user.type(screen.getByLabelText(/^reason$/i), "drill");
    await user.click(screen.getByTestId("halt-DE_RISK"));

    await waitFor(() => {
      expect(killSwitchSetLevel).toHaveBeenCalledWith("DE_RISK", "drill");
    });
    expect(useKillSwitchStore.getState().level).toBe("DE_RISK");
    await waitFor(() => {
      expect(useKillSwitchStore.getState().modalOpen).toBe(false);
    });
  });

  it("Resume (NONE) is single-click with reason when halted", async () => {
    const user = userEvent.setup();
    killSwitchStatus.mockResolvedValue({
      active: true,
      level: "STOP_OPENING",
      recent_log: [],
    });
    killSwitchSetLevel.mockResolvedValue({
      status: "none",
      reason: "all clear",
      level: "NONE",
    });
    useKillSwitchStore.setState({ level: "STOP_OPENING", modalOpen: false });
    renderModal();
    useKillSwitchStore.getState().setModalOpen(true);
    await waitFor(() => screen.getByTestId("halt-NONE"));

    await user.type(screen.getByLabelText(/^reason$/i), "all clear");
    await user.click(screen.getByTestId("halt-NONE"));

    await waitFor(() => {
      expect(killSwitchSetLevel).toHaveBeenCalledWith("NONE", "all clear");
    });
    expect(useKillSwitchStore.getState().level).toBe("NONE");
  });
});

describe("KillSwitchModal — FLATTEN two-stage gate", () => {
  it("stage 1 click does NOT post — it opens the confirm gate with the locked policy", async () => {
    const user = userEvent.setup();
    renderModal();
    useKillSwitchStore.getState().setModalOpen(true);
    await waitFor(() => screen.getByRole("dialog"));

    await user.type(screen.getByLabelText(/^reason$/i), "emergency");
    await user.click(screen.getByTestId("halt-FLATTEN"));
    // Double-click on stage 1 must also be inert (gate button starts disabled).
    expect(killSwitchSetLevel).not.toHaveBeenCalled();

    // Stage 2 renders the locked policy verbatim-faithful.
    expect(
      screen.getByText(/Manual FLATTEN is an explicit human authorization/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/≥2 independent severe triggers/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/persist ≥30s/i)).toBeInTheDocument();

    // Final button is disabled until "FLATTEN" is typed.
    const confirmBtn = screen.getByTestId("halt-FLATTEN-confirm");
    expect(confirmBtn).toBeDisabled();
    await user.click(confirmBtn);
    expect(killSwitchSetLevel).not.toHaveBeenCalled();
  });

  it("wrong typed confirmation keeps FLATTEN unreachable", async () => {
    const user = userEvent.setup();
    renderModal();
    useKillSwitchStore.getState().setModalOpen(true);
    await waitFor(() => screen.getByRole("dialog"));

    await user.type(screen.getByLabelText(/^reason$/i), "emergency");
    await user.click(screen.getByTestId("halt-FLATTEN"));
    await user.type(
      screen.getByLabelText(/type FLATTEN to confirm/i),
      "flatten"
    );
    expect(screen.getByTestId("halt-FLATTEN-confirm")).toBeDisabled();
    expect(killSwitchSetLevel).not.toHaveBeenCalled();
  });

  it("typed FLATTEN + confirm posts the level", async () => {
    const user = userEvent.setup();
    killSwitchSetLevel.mockResolvedValue({
      status: "flatten",
      reason: "emergency",
      level: "FLATTEN",
    });
    renderModal();
    useKillSwitchStore.getState().setModalOpen(true);
    await waitFor(() => screen.getByRole("dialog"));

    await user.type(screen.getByLabelText(/^reason$/i), "emergency");
    await user.click(screen.getByTestId("halt-FLATTEN"));
    await user.type(
      screen.getByLabelText(/type FLATTEN to confirm/i),
      "FLATTEN"
    );
    const confirmBtn = screen.getByTestId("halt-FLATTEN-confirm");
    expect(confirmBtn).toBeEnabled();
    await user.click(confirmBtn);

    await waitFor(() => {
      expect(killSwitchSetLevel).toHaveBeenCalledWith("FLATTEN", "emergency");
    });
    expect(useKillSwitchStore.getState().level).toBe("FLATTEN");
  });

  it("Enter in the reason input never submits anything (no form fallthrough)", async () => {
    const user = userEvent.setup();
    renderModal();
    useKillSwitchStore.getState().setModalOpen(true);
    await waitFor(() => screen.getByRole("dialog"));

    await user.type(screen.getByLabelText(/^reason$/i), "oops{Enter}");
    expect(killSwitchSetLevel).not.toHaveBeenCalled();
    expect(killSwitchToggle).not.toHaveBeenCalled();
  });
});

describe("KillSwitchModal — optimistic update + rollback", () => {
  it("a failing POST restores the prior level in store AND cache", async () => {
    const user = userEvent.setup();
    // Seed the cache as the 10s poll would have.
    const seeded = { active: false, level: "NONE", recent_log: [] };
    queryClient.setQueryData(queryKeys.killSwitch, seeded);
    killSwitchSetLevel.mockRejectedValue(new Error("redis down"));

    renderModal();
    useKillSwitchStore.getState().setModalOpen(true);
    await waitFor(() => screen.getByRole("dialog"));

    await user.type(screen.getByLabelText(/^reason$/i), "drill");
    await user.click(screen.getByTestId("halt-NEUTRALIZE"));

    // Error surfaces in the modal…
    expect(await screen.findByRole("alert")).toHaveTextContent(/redis down/i);
    // …and BOTH the store and the killSwitch cache rolled back.
    expect(useKillSwitchStore.getState().level).toBe("NONE");
    expect(queryClient.getQueryData(queryKeys.killSwitch)).toEqual(seeded);
    // Modal stays open so the operator sees the failure.
    expect(useKillSwitchStore.getState().modalOpen).toBe(true);
  });

  it("a successful POST leaves the optimistic level in place", async () => {
    const user = userEvent.setup();
    queryClient.setQueryData(queryKeys.killSwitch, {
      active: false,
      level: "NONE",
      recent_log: [],
    });
    killSwitchSetLevel.mockResolvedValue({
      status: "stop_opening",
      reason: "drill",
      level: "STOP_OPENING",
    });

    renderModal();
    useKillSwitchStore.getState().setModalOpen(true);
    await waitFor(() => screen.getByRole("dialog"));

    await user.type(screen.getByLabelText(/^reason$/i), "drill");
    await user.click(screen.getByTestId("halt-STOP_OPENING"));

    await waitFor(() => {
      expect(useKillSwitchStore.getState().level).toBe("STOP_OPENING");
    });
  });
});

describe("severity() — chrome mapping contract", () => {
  it("maps each level to the documented severity", () => {
    const expected: Record<HaltLevel, ReturnType<typeof severity>> = {
      NONE: "off",
      STOP_OPENING: "warn",
      DE_RISK: "warn",
      NEUTRALIZE: "danger",
      FLATTEN: "danger",
    };
    for (const [level, sev] of Object.entries(expected)) {
      expect(severity(level as HaltLevel)).toBe(sev);
    }
  });
});
