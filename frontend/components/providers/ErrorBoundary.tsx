"use client";

import React, { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex items-center justify-center h-screen bg-background">
          <div className="flex flex-col items-center gap-6 max-w-md text-center p-8">
            <div className="h-16 w-16 rounded-full border border-destructive/30 flex items-center justify-center">
              <svg
                className="w-8 h-8 text-red-500"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
                />
              </svg>
            </div>

            <div>
              <h2 className="text-xl font-bold text-foreground mb-2">
                Something went wrong
              </h2>
              <p className="text-sm text-muted-foreground leading-relaxed">
                An unexpected error occurred. You can try reloading the page or
                resetting the current view.
              </p>
            </div>

            {this.state.error && (
              <div className="w-full p-3 border border-destructive/30 rounded-md">
                <p className="text-xs text-red-500 font-mono break-words text-left">
                  {this.state.error.message}
                </p>
              </div>
            )}

            <div className="flex gap-3">
              <button
                onClick={this.handleReset}
                className="px-4 py-2.5 border border-border hover:bg-accent text-foreground text-sm font-medium rounded-md transition-colors min-h-[44px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
              >
                TRY AGAIN
              </button>
              <button
                onClick={() => window.location.reload()}
                className="px-4 py-2.5 bg-primary hover:bg-primary/90 text-primary-foreground text-sm font-medium rounded-md transition-colors min-h-[44px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
              >
                RELOAD PAGE
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
