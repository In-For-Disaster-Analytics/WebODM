import $ from 'jquery';

const loadManager = () => {
    global.$ = $;
    window.$ = $;
    window.jQuery = $;
    window.tapisTokenInfo = { has_token: false };
    return require('../classes/TapisTokenManager').default;
};

describe('TapisTokenManager', () => {
    beforeEach(() => {
        jest.resetModules();
        jest.useFakeTimers();
        document.body.innerHTML = '';
        window.tapisTokenInfo = { has_token: false };
    });

    afterEach(() => {
        if (window.tapisTokenManager) {
            window.tapisTokenManager.stopMonitoring();
        }
        delete window.tapisTokenManager;
        delete window.tapisTokenInfo;
        jest.clearAllTimers();
        jest.useRealTimers();
    });

    it('logs out immediately when the Tapis token is expired', () => {
        const TapisTokenManager = loadManager();
        const manager = new TapisTokenManager();
        manager.redirectToLogout = jest.fn();
        manager.checkInterval = setInterval(() => {}, 30000);
        window.tapisTokenInfo = {
            expires_at: new Date(Date.now() - 1000).toISOString(),
            has_token: true
        };

        manager.checkTokenExpiration();

        expect(manager.redirectToLogout).toHaveBeenCalledTimes(1);
        expect(manager.logoutTriggered).toBe(true);
        expect(manager.checkInterval).toBeNull();
    });

    it('logs out when token expiry metadata is invalid', () => {
        const TapisTokenManager = loadManager();
        const manager = new TapisTokenManager();
        manager.redirectToLogout = jest.fn();
        window.tapisTokenInfo = {
            expires_at: 'not-a-date',
            has_token: true
        };

        manager.checkTokenExpiration();

        expect(manager.redirectToLogout).toHaveBeenCalledTimes(1);
    });

    it('only triggers logout once', () => {
        const TapisTokenManager = loadManager();
        const manager = new TapisTokenManager();
        manager.redirectToLogout = jest.fn();

        manager.handleTokenExpiration();
        manager.handleTokenExpiration();

        expect(manager.redirectToLogout).toHaveBeenCalledTimes(1);
    });

    it('shows a warning without offering token refresh before expiry', () => {
        const TapisTokenManager = loadManager();
        const manager = new TapisTokenManager();
        manager.redirectToLogout = jest.fn();
        window.tapisTokenInfo = {
            expires_at: new Date(Date.now() + 5 * 60000).toISOString(),
            has_token: true
        };

        manager.checkTokenExpiration();

        const warningText = $('#tapis-token-warning').text();
        expect(warningText).toContain('Log Out Now');
        expect(warningText).not.toContain('Refresh Now');
        expect(manager.redirectToLogout).not.toHaveBeenCalled();
    });
});
