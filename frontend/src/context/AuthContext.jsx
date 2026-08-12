import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import apiEndpoints from '../api/endpoints';
import { LOCAL_SAVE_KEY } from '../utils/localSave';
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
     * they call. Both previously repeated this sequence — and the same
     * four-line comment — verbatim, so the autosave-clearing step had two
     * places to fall out of.
     */
    const establishSession = (response, username) => {
        const { session_id } = response.data.data;
        // Establishing a new identity clears any prior session's autosave.
        // Teardown paths already do this; doing it here too means
        // cross-account separation no longer depends on every one of
        // them having fired (a crash mid-logout, say).
        localStorage.removeItem(LOCAL_SAVE_KEY);
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
            // Every session-scoped key, including the local autosave: leaving
            // that behind let the next account to sign in on this machine see
            // the previous player's character in the menu — and pick
            // "Continue". Shared with the 401 interceptor so the key list
            // cannot drift between the two teardown paths.
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
        checkAuth
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
};
