import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ErrorBoundary } from "./ErrorBoundary";

function Boom(): JSX.Element {
  throw new Error("render exploded");
}

describe("ErrorBoundary", () => {
  afterEach(() => cleanup());

  it("renders children when nothing throws", () => {
    render(
      <ErrorBoundary>
        <p>all good</p>
      </ErrorBoundary>,
    );
    expect(screen.getByText("all good")).toBeTruthy();
  });

  it("contains a render crash instead of blanking the page", () => {
    // React logs the caught error; silence it so the suite output stays readable.
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );

    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByText(/something broke/i)).toBeTruthy();
    expect(screen.getByText("render exploded")).toBeTruthy();
    spy.mockRestore();
  });

  it("recovers when the retry button is pressed and children stop throwing", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    let shouldThrow = true;

    function Flaky(): JSX.Element {
      if (shouldThrow) throw new Error("temporary");
      return <p>recovered</p>;
    }

    render(
      <ErrorBoundary>
        <Flaky />
      </ErrorBoundary>,
    );
    expect(screen.getByRole("alert")).toBeTruthy();

    shouldThrow = false;
    fireEvent.click(screen.getByRole("button", { name: /try again/i }));

    expect(screen.getByText("recovered")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
    spy.mockRestore();
  });

  it("keeps the error message when it is empty", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    function Silent(): JSX.Element {
      throw new Error("");
    }
    render(
      <ErrorBoundary>
        <Silent />
      </ErrorBoundary>,
    );
    expect(screen.getByText(/unexpected error/i)).toBeTruthy();
    spy.mockRestore();
  });
});
