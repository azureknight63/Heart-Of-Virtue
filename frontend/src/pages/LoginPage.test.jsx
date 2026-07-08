import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import LoginPage from './LoginPage';
import { useAuth } from '../hooks/useApi';
import { MemoryRouter } from 'react-router-dom';

const mockNavigate = vi.fn();

// Mock useAuth
vi.mock('../hooks/useApi', () => ({
    useAuth: vi.fn(),
}));

// Mock useNavigate so we can assert navigate('/menu') is called after login/register
vi.mock('react-router-dom', async (importOriginal) => {
    const actual = await importOriginal();
    return {
        ...actual,
        useNavigate: () => mockNavigate,
    };
});

describe('LoginPage', () => {
    const mockLogin = vi.fn();
    const mockRegister = vi.fn();

    beforeEach(() => {
        vi.clearAllMocks();
        useAuth.mockReturnValue({
            login: mockLogin,
            register: mockRegister,
        });
    });

    const renderLoginPage = () => {
        return render(
            <MemoryRouter>
                <LoginPage />
            </MemoryRouter>
        );
    };

    it('renders login form by default', () => {
        renderLoginPage();
        expect(screen.getByText('Heart of Virtue')).toBeDefined();
        expect(screen.getByLabelText(/Username/i)).toBeDefined();
        expect(screen.getByLabelText(/Password/i)).toBeDefined();
        expect(screen.getByRole('button', { name: /Enter Game/i })).toBeDefined();
    });

    it('toggles between login and register', () => {
        renderLoginPage();
        const toggleBtn = screen.getByText(/Create Account/i);
        fireEvent.click(toggleBtn);
        expect(screen.getByRole('button', { name: /Create Account/i })).toBeDefined();
        expect(screen.getByText(/Back to Login/i)).toBeDefined();
    });

    it('handles successful login', async () => {
        mockLogin.mockResolvedValue({ success: true });
        renderLoginPage();

        fireEvent.change(screen.getByLabelText(/Username/i), { target: { value: 'testuser' } });
        fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'password123' } });
        fireEvent.click(screen.getByRole('button', { name: /Enter Game/i }));

        await waitFor(() => {
            expect(mockLogin).toHaveBeenCalledWith('testuser', 'password123');
            expect(mockNavigate).toHaveBeenCalledWith('/menu');
        });
    });

    it('handles login failure with 401', async () => {
        mockLogin.mockRejectedValue({
            response: {
                status: 401,
                data: { message: 'Unauthorized' }
            }
        });
        renderLoginPage();

        fireEvent.change(screen.getByLabelText(/Username/i), { target: { value: 'testuser' } });
        fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'wrong' } });
        fireEvent.click(screen.getByRole('button', { name: /Enter Game/i }));

        await waitFor(() => {
            expect(screen.getByText('Invalid username or password; try again or register a new account.')).toBeDefined();
        });
    });

    it('renders Terms of Service link', () => {
        renderLoginPage();
        expect(screen.getByText(/Terms of Service & Privacy Policy/i)).toBeDefined();
    });

    it('opens ToS modal when link is clicked', () => {
        renderLoginPage();
        fireEvent.click(screen.getByText(/Terms of Service & Privacy Policy/i));
        expect(screen.getByText(/Terms & Privacy/i)).toBeDefined();
    });

    it('closes ToS modal when onClose is triggered', () => {
        renderLoginPage();
        fireEvent.click(screen.getByText(/Terms of Service & Privacy Policy/i));
        expect(screen.getByText(/Terms & Privacy/i)).toBeDefined();
        fireEvent.click(screen.getByRole('button', { name: /Close/i }));
        expect(screen.queryByText(/Terms & Privacy/i)).toBeNull();
    });

    it('handles successful registration', async () => {
        mockRegister.mockResolvedValue({ success: true });
        renderLoginPage();

        fireEvent.click(screen.getByText(/Create Account/i));
        fireEvent.change(screen.getByLabelText(/Username/i), { target: { value: 'newuser' } });
        fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'password123456789' } });
        fireEvent.change(screen.getByLabelText(/Email Address/i), { target: { value: 'test@example.com' } });
        fireEvent.click(screen.getByRole('button', { name: /Create Account/i }));

        await waitFor(() => {
            expect(mockRegister).toHaveBeenCalledWith('newuser', 'password123456789', 'test@example.com');
            expect(mockNavigate).toHaveBeenCalledWith('/menu');
        });
    });

    it('rejects registration with a password under 16 characters without calling the API', async () => {
        renderLoginPage();
        fireEvent.click(screen.getByText(/Create Account/i));
        fireEvent.change(screen.getByLabelText(/Username/i), { target: { value: 'newuser' } });
        fireEvent.change(screen.getByLabelText(/New Password/i), { target: { value: 'short' } });
        fireEvent.change(screen.getByLabelText(/Email Address/i), { target: { value: 'test@example.com' } });
        fireEvent.click(screen.getByRole('button', { name: /Create Account/i }));

        await waitFor(() => {
            expect(screen.getByText(/Password must be at least 16 characters long/i)).toBeInTheDocument();
        });
        expect(mockRegister).not.toHaveBeenCalled();
    });

    it('toggles from register mode back to login mode', () => {
        renderLoginPage();
        fireEvent.click(screen.getByText(/Create Account/i));
        expect(screen.getByRole('button', { name: /Create Account/i })).toBeInTheDocument();

        fireEvent.click(screen.getByText(/Back to Login/i));
        expect(screen.getByRole('button', { name: /Enter Game/i })).toBeInTheDocument();
    });

    it('shows a network-unreachable message when the login request has no response', async () => {
        mockLogin.mockRejectedValue(new Error('Network Error'));
        renderLoginPage();

        fireEvent.change(screen.getByLabelText(/Username/i), { target: { value: 'testuser' } });
        fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'password123' } });
        fireEvent.click(screen.getByRole('button', { name: /Enter Game/i }));

        await waitFor(() => {
            expect(screen.getByText(/The game server is unreachable/i)).toBeInTheDocument();
        });
    });

    it('shows a network-unreachable message on a 500-level server error', async () => {
        mockLogin.mockRejectedValue({ response: { status: 503 } });
        renderLoginPage();

        fireEvent.change(screen.getByLabelText(/Username/i), { target: { value: 'testuser' } });
        fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'password123' } });
        fireEvent.click(screen.getByRole('button', { name: /Enter Game/i }));

        await waitFor(() => {
            expect(screen.getByText(/The game server is unreachable/i)).toBeInTheDocument();
        });
    });

    it('shows the server-provided message for other 4xx errors', async () => {
        mockLogin.mockRejectedValue({ response: { status: 400, data: { message: 'Username is taken' } } });
        renderLoginPage();

        fireEvent.change(screen.getByLabelText(/Username/i), { target: { value: 'testuser' } });
        fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'password123' } });
        fireEvent.click(screen.getByRole('button', { name: /Enter Game/i }));

        await waitFor(() => {
            expect(screen.getByText('Username is taken')).toBeInTheDocument();
        });
    });

    it('falls back to a generic message when a 4xx error has no server message', async () => {
        mockLogin.mockRejectedValue({ response: { status: 400 } });
        renderLoginPage();

        fireEvent.change(screen.getByLabelText(/Username/i), { target: { value: 'testuser' } });
        fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'password123' } });
        fireEvent.click(screen.getByRole('button', { name: /Enter Game/i }));

        await waitFor(() => {
            expect(screen.getByText('Authentication failed. Please try again.')).toBeInTheDocument();
        });
    });

    it('shows a processing state on the submit button while logging in', async () => {
        let resolveLogin;
        mockLogin.mockReturnValue(new Promise((resolve) => { resolveLogin = resolve; }));
        renderLoginPage();

        fireEvent.change(screen.getByLabelText(/Username/i), { target: { value: 'testuser' } });
        fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'password123' } });
        fireEvent.click(screen.getByRole('button', { name: /Enter Game/i }));

        expect(screen.getByText('Processing...')).toBeInTheDocument();
        await waitFor(() => resolveLogin({ success: true }));
    });

    it('navigates to the landing page via the back-to-home link', () => {
        renderLoginPage();
        fireEvent.click(screen.getByText(/Back to home/i));
        expect(mockNavigate).toHaveBeenCalledWith('/landing');
    });

    it('clears a prior error when switching from login to register', async () => {
        mockLogin.mockRejectedValue({ response: { status: 401 } });
        renderLoginPage();

        fireEvent.change(screen.getByLabelText(/Username/i), { target: { value: 'testuser' } });
        fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'wrong' } });
        fireEvent.click(screen.getByRole('button', { name: /Enter Game/i }));
        await waitFor(() => {
            expect(screen.getByText(/Invalid username or password/i)).toBeInTheDocument();
        });

        fireEvent.click(screen.getByText(/Create Account/i));
        expect(screen.queryByText(/Invalid username or password/i)).not.toBeInTheDocument();
    });
});

describe('LoginPage embers canvas effect', () => {
    let rafCallbacks;

    beforeEach(() => {
        vi.clearAllMocks();
        useAuth.mockReturnValue({ login: vi.fn(), register: vi.fn() });

        HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
            fillStyle: '',
            clearRect: vi.fn(),
            beginPath: vi.fn(),
            arc: vi.fn(),
            fill: vi.fn(),
            scale: vi.fn(),
        }));

        rafCallbacks = [];
        global.requestAnimationFrame = vi.fn((cb) => {
            rafCallbacks.push(cb);
            return rafCallbacks.length;
        });
        global.cancelAnimationFrame = vi.fn();
    });

    const renderLoginPage = () => render(<MemoryRouter><LoginPage /></MemoryRouter>);

    it('starts the ember particle animation and ticks it forward', () => {
        renderLoginPage();
        expect(global.requestAnimationFrame).toHaveBeenCalled();

        const tick = rafCallbacks[0];
        expect(() => tick()).not.toThrow();
    });

    it('resizes the embers canvas on window resize', () => {
        renderLoginPage();
        expect(() => fireEvent(window, new Event('resize'))).not.toThrow();
    });

    it('stops the animation and removes the resize listener on unmount', () => {
        const { unmount } = renderLoginPage();
        unmount();
        expect(global.cancelAnimationFrame).toHaveBeenCalled();
    });

    it('does nothing when the canvas has no 2D context available', () => {
        HTMLCanvasElement.prototype.getContext = vi.fn(() => null);
        expect(() => renderLoginPage()).not.toThrow();
    });
});
