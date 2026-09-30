import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/** Contains a render crash to one panel instead of blanking the page.
 *
 * A runtime error in a React tree unmounts the whole tree by default, so a
 * single bad read -- a field missing from an older API response, say -- leaves
 * the user staring at a white screen with no way back. This catches it, shows
 * the same `ErrorNote` every other failure uses, and offers a retry.
 *
 * A class component because `getDerivedStateFromError` has no hook equivalent.
 */
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
        <div className="system-note system-note-error" role="alert">
          <span className="system-note-signal" aria-hidden="true" />
          <strong>Something broke on this page</strong>
          <span>
            {error.message || "An unexpected error stopped the page from rendering."}
          </span>
          <div className="note-actions">
            <button className="btn btn-secondary" type="button" onClick={this.reset}>
              Try again
            </button>
          </div>
        </div>
      </div>
    );
  }
}
