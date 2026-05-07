import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OrderEntryPanel } from "./OrderEntryPanel";

/**
 * Critical-path tests per frontend/DESIGN.md:
 *   - kill-switch-armed must always render correctly (banner + disabled submit)
 *   - submit button must adopt the consequence color (bid for buy, ask for sell)
 *   - keyboard shortcuts B/S/M must work and be unbreakable by other inputs
 *   - risk-block must disable submit and show the warn banner
 */

describe("OrderEntryPanel — critical-path", () => {
  it("submit adopts BID color on buy side", () => {
    render(
      <OrderEntryPanel
        symbol="BTC-PERP"
        midPrice={42318.27}
        defaultSide="buy"
        defaultSize="0.001"
      />
    );
    const submit = screen.getByTestId("order-submit");
    expect(submit.className).toMatch(/bg-bid-500/);
    expect(submit.className).not.toMatch(/bg-ask-500/);
  });

  it("submit adopts ASK color on sell side", () => {
    render(
      <OrderEntryPanel
        symbol="BTC-PERP"
        midPrice={42318.27}
        defaultSide="sell"
        defaultSize="0.001"
      />
    );
    const submit = screen.getByTestId("order-submit");
    expect(submit.className).toMatch(/bg-ask-500/);
    expect(submit.className).not.toMatch(/bg-bid-500/);
  });

  it("kill-switch-armed: submit is disabled, danger banner is shown", () => {
    const onSubmit = vi.fn();
    render(
      <OrderEntryPanel
        symbol="BTC-PERP"
        midPrice={42318.27}
        defaultSize="0.001"
        state="kill-switch-armed"
        onSubmit={onSubmit}
      />
    );
    const submit = screen.getByTestId("order-submit") as HTMLButtonElement;
    expect(submit).toBeDisabled();
    expect(screen.getByTestId("kill-switch-banner")).toBeInTheDocument();
    // The danger intent is what the kill state collapses to
    expect(submit.className).toMatch(/bg-danger-500/);
  });

  it("risk-block: submit is disabled, warn banner shown with reason", () => {
    render(
      <OrderEntryPanel
        symbol="BTC-PERP"
        midPrice={42318.27}
        defaultSize="0.001"
        state="risk-block"
        riskBlockReason="would exceed max position"
      />
    );
    const submit = screen.getByTestId("order-submit") as HTMLButtonElement;
    expect(submit).toBeDisabled();
    const banner = screen.getByTestId("risk-block-banner");
    expect(banner).toBeInTheDocument();
    expect(banner).toHaveTextContent("would exceed max position");
  });

  it("validating: submit shows spinner state", () => {
    render(
      <OrderEntryPanel
        symbol="BTC-PERP"
        midPrice={42318.27}
        defaultSize="0.001"
        state="validating"
      />
    );
    const submit = screen.getByTestId("order-submit") as HTMLButtonElement;
    expect(submit).toBeDisabled();
    expect(submit).toHaveAttribute("aria-busy", "true");
  });

  it("keyboard: B sets side to buy, S sets side to sell, M sets order type to market", async () => {
    const user = userEvent.setup();
    const onSideChange = vi.fn();
    const onOrderTypeChange = vi.fn();
    const { container } = render(
      <OrderEntryPanel
        symbol="BTC-PERP"
        midPrice={42318.27}
        defaultSide="sell"
        defaultOrderType="limit"
        defaultSize="0.001"
        onSideChange={onSideChange}
        onOrderTypeChange={onOrderTypeChange}
      />
    );
    const form = container.querySelector('[role="form"]') as HTMLDivElement;
    form.focus();

    await user.keyboard("B");
    expect(onSideChange).toHaveBeenCalledWith("buy");

    await user.keyboard("S");
    expect(onSideChange).toHaveBeenCalledWith("sell");

    await user.keyboard("M");
    expect(onOrderTypeChange).toHaveBeenCalledWith("market");
  });

  it("keyboard shortcuts do NOT fire while focus is in a text input", async () => {
    const user = userEvent.setup();
    const onSideChange = vi.fn();
    render(
      <OrderEntryPanel
        symbol="BTC-PERP"
        midPrice={42318.27}
        defaultSide="buy"
        defaultSize="0.001"
        onSideChange={onSideChange}
      />
    );
    const sizeInput = screen.getByLabelText("Order size") as HTMLInputElement;
    sizeInput.focus();
    await user.keyboard("S");
    // Side should not have flipped — the user is typing into the size field
    expect(onSideChange).not.toHaveBeenCalled();
    expect(sizeInput.value).toContain("S");
  });

  it("market order hides the price input and uses '@ market' label", () => {
    render(
      <OrderEntryPanel
        symbol="BTC-PERP"
        midPrice={42318.27}
        defaultSide="buy"
        defaultOrderType="market"
        defaultSize="0.001"
      />
    );
    const submit = screen.getByTestId("order-submit");
    expect(submit).toHaveTextContent(/@ market/i);
    expect(screen.queryByLabelText("Order price")).not.toBeInTheDocument();
  });

  it("calls onSubmit with the typed payload when submit is clicked", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(
      <OrderEntryPanel
        symbol="BTC-PERP"
        midPrice={42318.27}
        defaultSide="buy"
        defaultOrderType="limit"
        defaultSize="0.005"
        defaultPrice="42318.27"
        defaultLeverage={5}
        onSubmit={onSubmit}
      />
    );
    const submit = screen.getByTestId("order-submit");
    await user.click(submit);
    expect(onSubmit).toHaveBeenCalledWith({
      symbol: "BTC-PERP",
      side: "buy",
      type: "limit",
      size: 0.005,
      price: 42318.27,
      leverage: 5,
      reduceOnly: false,
      postOnly: false,
    });
  });

  it("tab order is side → size → price → leverage → submit", () => {
    render(
      <OrderEntryPanel
        symbol="BTC-PERP"
        midPrice={42318.27}
        defaultSide="buy"
        defaultOrderType="limit"
        defaultSize="0.001"
        defaultPrice="42318.27"
      />
    );
    const sideButtons = screen.getAllByRole("radio");
    expect(sideButtons[0]).toHaveAttribute("tabindex", "1");
    const sizeInput = screen.getByLabelText("Order size") as HTMLInputElement;
    expect(sizeInput.tabIndex).toBe(2);
    const priceInput = screen.getByLabelText("Order price") as HTMLInputElement;
    expect(priceInput.tabIndex).toBe(3);
    const leverage = screen.getByLabelText("Leverage") as HTMLInputElement;
    expect(leverage.tabIndex).toBe(4);
    const submit = screen.getByTestId("order-submit") as HTMLButtonElement;
    expect(submit.tabIndex).toBe(5);
  });
});
