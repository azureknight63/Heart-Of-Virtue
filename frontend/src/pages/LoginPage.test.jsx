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
});
