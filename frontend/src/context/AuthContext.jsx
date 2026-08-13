import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import apiEndpoints from '../api/endpoints';
import { AUTH_TOKEN_KEY, USERNAME_KEY, clearLocalSession } from '../utils/session';

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
        const token = localStorage.getItem(AUTH_TOKEN_KEY);
        const username = localStorage.getItem(USERNAME_KEY);
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

    /**
     * Shared tail of login and register, which differ only in which endpoint
     * they call.
     */
    const establishSession = (response, username) => {
        const { session_id } = response.data.data;
        localStorage.setItem(AUTH_TOKEN_KEY, session_id);
        localStorage.setItem(USERNAME_KEY, username);
        setIsAuthenticated(true);
        setUser({ username });
        return response.data;
    };

    /** Clears auth state and RETHROWS — callers use `throw clearSessionAndRethrow(e)`. */
    const clearSessionAndRethrow = (error) => {
        setIsAuthenticated(false);
        setUser(null);
        throw error;
    };

    const login = async (username, password) => {
        try {
            return establishSession(
                await apiEndpoints.auth.login(username, password),
                username
            );
        } catch (error) {
            throw clearSessionAndRethrow(error);
        }
    };

    const logout = async () => {
        try {
            await apiEndpoints.auth.logout();
        } finally {
            // Every session-scoped key: leaving one behind (a dead auth token,
            // the prior account's username) lets the next person to sign in on
            // this machine inherit stale identifiers from the last session.
            // Shared with the 401 interceptor so the key list cannot drift
            // between the two teardown paths.
            clearLocalSession();
            setIsAuthenticated(false);
            setUser(null);
            // Force reload to clear state and redirect to login, respecting subpath deployment
            const baseUrl = import.meta.env.BASE_URL || '/';
            window.location.href = baseUrl + 'login';
        }
    };

    const register = async (username, password, email) => {
        try {
            return establishSession(
                await apiEndpoints.auth.register(username, password, email),
                username
            );
        } catch (error) {
            throw clearSessionAndRethrow(error);
        }
    };

    const value = {
        isAuthenticated,
        loading,
        user,
        login,
        logout,
        register,
        checkAuth,
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
};
