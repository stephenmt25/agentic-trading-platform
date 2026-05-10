import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/**
 * Tests for the global KillSwitchModal — covers the contract that lets us
 * mount it once in RedesignShell:
 *   - hidden until the store opens it (and esc/cancel close it)
 *   - refuses empty reason
 *   - on submit, calls api.commands.killSwitchToggle and broadcasts new state
 *   - flips between "Arm soft" and "Disarm" off the store-derived armed state
 */

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

const killSwitchStatus = vi.fn();
const killSwitchToggle = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: {
    commands: {
      killSwitchStatus: (...args: unknown[]) => killSwitchStatus(...args),
      killSwitchToggle: (...args: unknown[]) => killSwitchToggle(...args),
    },
  },
}));

import { KillSwitchModal } from "./KillSwitchModal";
import { useKillSwitchStore } from "@/lib/stores/killSwitchStore";

beforeEach(() => {
  killSwitchStatus.mockReset();
  killSwitchToggle.mockReset();
  killSwitchStatus.mockResolvedValue({ active: false, recent_log: [] });
  killSwitchToggle.mockResolvedValue({ status: "ok", reason: null });
  // Reset store between tests
  useKillSwitchStore.setState({ state: "off", modalOpen: false });
});

describe("KillSwitchModal — global mount contract", () => {
  it("renders nothing until the store opens it", () => {
    render(<KillSwitchModal />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders 'Arm soft' when state is off and submits with reason", async () => {
    const user = userEvent.setup();
    render(<KillSwitchModal />);
    useKillSwitchStore.getState().setModalOpen(true);

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
    expect(
      screen.getByRole("heading", { name: /arm soft kill switch/i })
    ).toBeInTheDocument();

    await user.type(screen.getByLabelText(/reason/i), "scheduled drill");
    await user.click(screen.getByRole("button", { name: /^arm soft$/i }));

    await waitFor(() => {
      expect(killSwitchToggle).toHaveBeenCalledWith(true, "scheduled drill");
    });
    expect(useKillSwitchStore.getState().state).toBe("soft");
    expect(useKillSwitchStore.getState().modalOpen).toBe(false);
  });

  it("renders 'Disarm' and submits deactivation when state is soft", async () => {
    const user = userEvent.setup();
    killSwitchStatus.mockResolvedValue({ active: true, recent_log: [] });
    useKillSwitchStore.setState({ state: "soft", modalOpen: false });
    render(<KillSwitchModal />);
    useKillSwitchStore.getState().setModalOpen(true);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /disarm kill switch/i })
      ).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/reason/i), "all clear");
    await user.click(screen.getByRole("button", { name: /^disarm$/i }));

    await waitFor(() => {
      expect(killSwitchToggle).toHaveBeenCalledWith(false, "all clear");
    });
    expect(useKillSwitchStore.getState().state).toBe("off");
  });

  it("refuses empty reason — shows an error and does not call the API", async () => {
    const user = userEvent.setup();
    render(<KillSwitchModal />);
    useKillSwitchStore.getState().setModalOpen(true);
    await waitFor(() => screen.getByRole("dialog"));

    await user.click(screen.getByRole("button", { name: /^arm soft$/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/reason is required/i);
    expect(killSwitchToggle).not.toHaveBeenCalled();
    expect(useKillSwitchStore.getState().modalOpen).toBe(true);
  });

  it("Escape closes the modal", async () => {
    const user = userEvent.setup();
    render(<KillSwitchModal />);
    useKillSwitchStore.getState().setModalOpen(true);
    await waitFor(() => screen.getByRole("dialog"));

    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(useKillSwitchStore.getState().modalOpen).toBe(false);
    });
  });

  it("Cancel button closes the modal", async () => {
    const user = userEvent.setup();
    render(<KillSwitchModal />);
    useKillSwitchStore.getState().setModalOpen(true);
    await waitFor(() => screen.getByRole("dialog"));

    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(useKillSwitchStore.getState().modalOpen).toBe(false);
  });
});
