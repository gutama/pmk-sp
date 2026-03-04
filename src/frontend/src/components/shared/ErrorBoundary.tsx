import { Component, ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';

interface Props { children: ReactNode; }
interface State { hasError: boolean; error?: Error; }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center p-8 text-center">
          <AlertTriangle size={32} className="text-red-500 mb-3" />
          <h3 className="font-semibold text-gray-900 mb-1">Rendering Error</h3>
          <p className="text-sm text-gray-500">{this.state.error?.message}</p>
        </div>
      );
    }
    return this.props.children;
  }
}
