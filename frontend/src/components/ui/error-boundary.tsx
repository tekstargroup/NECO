"use client"

import React, { Component, type ErrorInfo, type ReactNode } from "react"

interface Props {
  children: ReactNode
  fallback?: ReactNode
  tabName?: string
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[NECO] ErrorBoundary caught in ${this.props.tabName ?? "unknown tab"}:`, error, info.componentStack)
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback
      return (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-sm font-medium text-red-800">
            Something went wrong{this.props.tabName ? ` in ${this.props.tabName}` : ""}.
          </p>
          <p className="mt-1 text-xs text-red-600">
            {this.state.error?.message || "An unexpected error occurred."}
          </p>
          <button
            type="button"
            className="mt-3 rounded border border-red-300 bg-white px-3 py-1 text-xs text-red-700 hover:bg-red-50"
            onClick={() => this.setState({ hasError: false, error: null })}
          >
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
