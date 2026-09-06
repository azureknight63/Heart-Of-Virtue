import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import apiEndpoints from '../api/endpoints';
import { USERNAME_KEY, clearLocalSession, redirectToLogin } from '../utils/session';

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

    /**
     * Decide, without a network round-trip, whether to render the app as
     * signed in.
     *
     * Since issue #493 the credential is an HttpOnly cookie, so there is no
     * token here to inspect — the stored username is the marker that a session
     * was established on this browser. That is deliberately a *belief*, not a
     * check: it was one before too (a long-expired `authToken` also rendered as
     * signed in), and the authority remains the server. Any request made
     * against a dead cookie 401s, and the axios interceptor clears this marker
     * and redirects to login.
     *
     * A `/api/auth/validate` call on mount was the alternative. It was not
     * taken: it puts a blocking request in front of the first paint on every
     * page load to reach the same end state one beat sooner, and it does not
     * remove the need for the 401 path, since the cookie can die at any later
     * moment anyway.
     */
    const checkAuth = useCallback(() => {
        const username = localStorage.getItem(USERNAME_KEY);
        if (username) {
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
        // The session id is NOT stored. The API set an HttpOnly cookie on this
        // very response (issue #493) and that is the credential from here on;
        // `response.data.data.session_id` is still in the body for non-browser
        // callers, and writing it to localStorage would put back exactly the
        // script-readable copy this change removed.
        //
        // Also drop any `authToken` a pre-#493 visit left behind, so an
        // upgrading browser does not keep a stale credential in storage.
        clearLocalSession();
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
            // Every session-scoped key: leaving one behind (the prior account's
            // username, a legacy pre-#493 auth token) lets the next person to
            // sign in on this machine inherit stale identifiers from the last
            // session. Shared with the 401 interceptor so the key list cannot
            // drift between the two teardown paths.
            //
            // The credential itself is not here to clear: the logout request
            // above is what expires the HttpOnly cookie, which is why it runs
            // first and its failure does not skip this cleanup.
            setIsAuthenticated(false);
            setUser(null);
            // Clears the markers and redirects, respecting subpath deployment.
            redirectToLogin();
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
