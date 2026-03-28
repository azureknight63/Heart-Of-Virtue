import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import apiEndpoints from '../api/endpoints';

const AuthContext = createContext();

export const useAuthContext = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuthContext must be used within an AuthProvider');
    }
    return context;
};

export const AuthProvider = ({ children }) => {
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [loading, setLoading] = useState(true);
    const [user, setUser] = useState(null);

    const checkAuth = useCallback(() => {
        const token = localStorage.getItem('authToken');
        const username = localStorage.getItem('username');
        if (token) {
            setIsAuthenticated(true);
            setUser({ username });
        } else {
            setIsAuthenticated(false);
            setUser(null);
        }
        setLoading(false);
    }, []);

    useEffect(() => {
        checkAuth();
    }, [checkAuth]);

    const login = async (username, password) => {
        try {
            const response = await apiEndpoints.auth.login(username, password);
            const { session_id } = response.data.data;
            localStorage.setItem('authToken', session_id);
            localStorage.setItem('username', username);
            setIsAuthenticated(true);
            setUser({ username });
            return response.data;
        } catch (error) {
            setIsAuthenticated(false);
            setUser(null);
            throw error;
        }
    };

    const logout = async () => {
        try {
            await apiEndpoints.auth.logout();
        } finally {
            localStorage.removeItem('authToken');
            localStorage.removeItem('username');
            setIsAuthenticated(false);
            setUser(null);
            // Force reload to clear state and redirect to login, respecting subpath
            const baseUrl = import.meta.env.BASE_URL || '/';
            window.location.href = baseUrl + 'login';
        }
    };

    const register = async (username, password, email) => {
        try {
            const response = await apiEndpoints.auth.register(username, password, email);
            const { session_id } = response.data.data;
            localStorage.setItem('authToken', session_id);
            localStorage.setItem('username', username);
            setIsAuthenticated(true);
            setUser({ username });
            return response.data;
        } catch (error) {
            setIsAuthenticated(false);
            setUser(null);
            throw error;
        }
    };

    const value = {
        isAuthenticated,
        loading,
        user,
        login,
        logout,
        register,
        checkAuth
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
};
