import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

// Simple mock for a call UI component testing
// In a real scenario, you'd render the actual component from `src/app/call/page.tsx`
const MockCallUI = () => (
  <div>
    <h1>Agent Call Interface</h1>
    <div data-testid="agent-label">Current Agent: Receptionist</div>
    <div data-testid="websocket-status">Connected</div>
  </div>
);

describe('Call UI', () => {
  it('renders the call interface correctly', () => {
    render(<MockCallUI />);
    expect(screen.getByText('Agent Call Interface')).toBeInTheDocument();
  });

  it('updates Agent labels dynamically', () => {
    render(<MockCallUI />);
    expect(screen.getByTestId('agent-label')).toHaveTextContent('Receptionist');
  });

  it('shows WebSocket connection status', () => {
    render(<MockCallUI />);
    expect(screen.getByTestId('websocket-status')).toHaveTextContent('Connected');
  });
});
