import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";

import { ErrorNote, NOTE_TITLES } from "./SystemNote";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/** Contains a render crash to one panel instead of blanking the page.
 * A runtime error unmounts the whole tree, so one bad read from an older API
 * leaves a white screen with no way back. A class component because
 * getDerivedStateFromError has no hook equivalent. */

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Kept in the console rather than sent anywhere: there is no error
    // reporting service, and a silent catch would make this invisible.
    console.error("Unhandled render error", error, info.componentStack);
  }

  private reset = () => this.setState({ error: null });

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;
    return (
      <div className="page-section">
        <ErrorNote
          title={NOTE_TITLES.crashed}
          action={(
            <button className="btn btn-secondary" type="button" onClick={this.reset}>
              Try again
            </button>
          )}
        >
          {error.message || "An unexpected error stopped the page from rendering."}
        </ErrorNote>
      </div>
    );
  }
}
