/**
 * Theme Management for APRSD Admin Extension
 * Handles dark/light theme switching and persistence
 */

(function() {
    'use strict';

    const THEME_STORAGE_KEY = 'aprsd-admin-theme';
    const THEME_ATTRIBUTE = 'data-theme';
    const DEFAULT_THEME = 'light';

    /**
     * Get the current theme from localStorage or system preference
     */
    function getStoredTheme() {
        const stored = localStorage.getItem(THEME_STORAGE_KEY);
        if (stored) {
            return stored;
        }

        // Check system preference
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            return 'dark';
        }

        return DEFAULT_THEME;
    }

    /**
     * Set the theme on the document
     */
    function setTheme(theme) {
        const html = document.documentElement;
        const themeToggle = document.getElementById('theme-toggle');

        if (theme === 'dark') {
            html.setAttribute(THEME_ATTRIBUTE, 'dark');
            if (themeToggle) {
                themeToggle.setAttribute(THEME_ATTRIBUTE, 'dark');
            }
        } else {
            html.removeAttribute(THEME_ATTRIBUTE);
            if (themeToggle) {
                themeToggle.setAttribute(THEME_ATTRIBUTE, 'light');
            }
        }

        localStorage.setItem(THEME_STORAGE_KEY, theme);

        // Update charts theme if function exists
        if (typeof updateAllChartsTheme === 'function') {
            setTimeout(function() {
                updateAllChartsTheme();
            }, 100);
        }
    }

    /**
     * Toggle between light and dark theme
     */
    function toggleTheme() {
        const currentTheme = document.documentElement.getAttribute(THEME_ATTRIBUTE) === 'dark' ? 'dark' : 'light';
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        setTheme(newTheme);
    }

    /**
     * Initialize theme on page load
     */
    function initTheme() {
        // Get current theme (may have been set by inline script)
        const currentTheme = document.documentElement.getAttribute(THEME_ATTRIBUTE) === 'dark' ? 'dark' : 'light';
        const storedTheme = getStoredTheme();

        // Only set if different (to avoid unnecessary updates)
        if (currentTheme !== storedTheme) {
            setTheme(storedTheme);
        } else {
            // Ensure toggle button state is correct
            const themeToggle = document.getElementById('theme-toggle');
            if (themeToggle) {
                themeToggle.setAttribute(THEME_ATTRIBUTE, currentTheme);
            }
        }

        // Set up theme toggle button
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', toggleTheme);
        }

        // Listen for system theme changes
        if (window.matchMedia) {
            const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
            mediaQuery.addEventListener('change', function(e) {
                // Only auto-switch if user hasn't manually set a preference
                if (!localStorage.getItem(THEME_STORAGE_KEY)) {
                    setTheme(e.matches ? 'dark' : 'light');
                }
            });
        }
    }

    // Initialize theme when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTheme);
    } else {
        initTheme();
    }

    // Export for external use if needed
    window.aprsdAdminTheme = {
        setTheme: setTheme,
        toggleTheme: toggleTheme,
        getTheme: function() {
            return document.documentElement.getAttribute(THEME_ATTRIBUTE) === 'dark' ? 'dark' : 'light';
        }
    };
})();
