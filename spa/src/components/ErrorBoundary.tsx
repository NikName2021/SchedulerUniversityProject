import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCcw, Home } from 'lucide-react';

interface Props {
  children?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div style={{ 
          padding: '4rem 2rem', 
          textAlign: 'center', 
          backgroundColor: 'white', 
          borderRadius: '32px', 
          border: '1px solid #fee2e2',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
          maxWidth: '600px',
          margin: '4rem auto'
        }}>
          <div style={{ 
            width: '80px', 
            height: '80px', 
            borderRadius: '24px', 
            backgroundColor: '#fef2f2', 
            color: '#ef4444', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            margin: '0 auto 2rem'
          }}>
            <AlertTriangle size={40} />
          </div>
          
          <h2 style={{ fontSize: '1.5rem', fontWeight: 900, color: '#111827', marginBottom: '1rem' }}>Что-то пошло не так</h2>
          <p style={{ color: '#6b7280', fontWeight: 500, marginBottom: '2rem', lineHeight: 1.6 }}>
            Произошла непредвиденная ошибка в интерфейсе. Мы уже зафиксировали её. Попробуйте обновить страницу или вернуться на главную.
          </p>
          
          {this.state.error && (
            <div style={{ 
              backgroundColor: '#f9fafb', 
              padding: '1rem', 
              borderRadius: '12px', 
              fontSize: '0.75rem', 
              fontFamily: 'monospace', 
              color: '#374151',
              textAlign: 'left',
              marginBottom: '2rem',
              overflowX: 'auto',
              border: '1px solid #e5e7eb'
            }}>
              {this.state.error.toString()}
            </div>
          )}

          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
            <button 
              onClick={() => window.location.reload()}
              style={{ 
                padding: '0.875rem 1.5rem', 
                borderRadius: '14px', 
                backgroundColor: 'white', 
                border: '1px solid #e5e7eb', 
                fontWeight: 700, 
                display: 'flex', 
                alignItems: 'center', 
                gap: '0.5rem',
                cursor: 'pointer'
              }}
            >
              <RefreshCcw size={18} /> Обновить
            </button>
            <a 
              href="/"
              style={{ 
                padding: '0.875rem 1.5rem', 
                borderRadius: '14px', 
                backgroundColor: '#111827', 
                color: 'white',
                textDecoration: 'none',
                fontWeight: 700, 
                display: 'flex', 
                alignItems: 'center', 
                gap: '0.5rem',
                cursor: 'pointer'
              }}
            >
              <Home size={18} /> На главную
            </a>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
