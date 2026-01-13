import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import LoginPage from './LoginPage';
import { useAuth } from '../hooks/useApi';
import { MemoryRouter } from 'react-router-dom';

// Mock useAuth
vi.mock('../hooks/useApi', () => ({
    useAuth: vi.fn(),
}));

describe('LoginPage', () => {
    const mockLogin = vi.fn();
    const mockRegister = vi.fn();

    beforeEach(() => {
        vi.clearAllMocks();
        useAuth.mockReturnValue({
            login: mockLogin,
            register: mockRegister,
        });

        // Mock window.location.href
        delete window.location;
        window.location = { href: '' };
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
        expect(screen.getByPlaceholderText('Enter your name')).toBeDefined();
        expect(screen.getByPlaceholderText('Enter your password')).toBeDefined();
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

        fireEvent.change(screen.getByPlaceholderText('Enter your name'), { target: { value: 'testuser' } });
        fireEvent.change(screen.getByPlaceholderText('Enter your password'), { target: { value: 'password123' } });
        fireEvent.click(screen.getByRole('button', { name: /Enter Game/i }));

        await waitFor(() => {
            expect(mockLogin).toHaveBeenCalledWith('testuser', 'password123');
            expect(window.location.href).toBe('/menu');
        });
    });

    it('handles login failure', async () => {
        mockLogin.mockRejectedValue({
            response: { data: { message: 'Invalid credentials' } }
        });
        renderLoginPage();

        fireEvent.change(screen.getByPlaceholderText('Enter your name'), { target: { value: 'testuser' } });
        fireEvent.change(screen.getByPlaceholderText('Enter your password'), { target: { value: 'wrong' } });
        fireEvent.click(screen.getByRole('button', { name: /Enter Game/i }));

        await waitFor(() => {
            expect(screen.getByText('Invalid credentials')).toBeDefined();
        });
    });

    it('handles successful registration', async () => {
        mockRegister.mockResolvedValue({ success: true });
        renderLoginPage();

        fireEvent.click(screen.getByText(/Create Account/i));
        fireEvent.change(screen.getByPlaceholderText('Enter your name'), { target: { value: 'newuser' } });
        fireEvent.change(screen.getByPlaceholderText('Enter your password'), { target: { value: 'password123' } });
        fireEvent.click(screen.getByRole('button', { name: /Create Account/i }));

        await waitFor(() => {
            expect(mockRegister).toHaveBeenCalledWith('newuser', 'password123');
            expect(window.location.href).toBe('/menu');
        });
    });
});
