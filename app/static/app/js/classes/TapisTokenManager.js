/**
 * TapisTokenManager - Handles automatic logout when Tapis JWT tokens expire
 */
class TapisTokenManager {
    constructor() {
        this.checkInterval = null;
        this.warningShown = false;
        this.init();
    }

    init() {
        // Check if user has Tapis token info available
        if (window.tapisTokenInfo && window.tapisTokenInfo.expires_at) {
            this.startTokenMonitoring();
        }
    }

    startTokenMonitoring() {
        // Check token every 30 seconds
        this.checkInterval = setInterval(() => {
            this.checkTokenExpiration();
        }, 30000);

        // Also check immediately
        this.checkTokenExpiration();
    }

    checkTokenExpiration() {
        if (!window.tapisTokenInfo || !window.tapisTokenInfo.expires_at) {
            return;
        }

        const expiresAt = new Date(window.tapisTokenInfo.expires_at);
        const now = new Date();
        const timeUntilExpiry = expiresAt - now;
        const minutesUntilExpiry = Math.floor(timeUntilExpiry / 60000);

        // Show warning 10 minutes before expiration
        if (minutesUntilExpiry <= 10 && minutesUntilExpiry > 0 && !this.warningShown) {
            this.showExpirationWarning(minutesUntilExpiry);
            this.warningShown = true;
        }

        // Auto-logout when token expires
        if (timeUntilExpiry <= 0) {
            this.handleTokenExpiration();
        }
    }

    showExpirationWarning(minutes) {
        const message = `Your Tapis session will expire in ${minutes} minute(s). Please save your work and refresh the page to re-authenticate.`;
        
        // Create a prominent warning banner
        const warningBanner = $(`
            <div id="tapis-token-warning" class="alert alert-warning alert-dismissible" style="
                position: fixed; 
                top: 0; 
                left: 0; 
                right: 0; 
                z-index: 9999; 
                margin: 0; 
                border-radius: 0;
                text-align: center;
            ">
                <button type="button" class="close" data-dismiss="alert">
                    <span>&times;</span>
                </button>
                <strong>Tapis Session Expiring!</strong> ${message}
                <button class="btn btn-sm btn-primary ml-2" onclick="window.location.reload();">
                    Refresh Now
                </button>
            </div>
        `);

        $('body').prepend(warningBanner);

        // Also show browser notification if supported
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification('Tapis Session Expiring', {
                body: message,
                icon: '/static/app/img/favicon.ico'
            });
        }
    }

    handleTokenExpiration() {
        // Clear the monitoring interval
        if (this.checkInterval) {
            clearInterval(this.checkInterval);
        }

        // Show expiration modal
        const modal = $(`
            <div class="modal fade" id="tapis-expired-modal" tabindex="-1" data-backdrop="static" data-keyboard="false">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header bg-danger text-white">
                            <h4 class="modal-title">Tapis Session Expired</h4>
                        </div>
                        <div class="modal-body">
                            <p><strong>Your Tapis authentication session has expired.</strong></p>
                            <p>You will be logged out automatically and need to re-authenticate to continue using Tapis features.</p>
                            <p>Any unsaved work may be lost.</p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-primary" onclick="window.location.href='/logout/'">
                                Logout Now
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `);

        $('body').append(modal);
        $('#tapis-expired-modal').modal('show');

        // Auto-logout after 10 seconds if user doesn't click
        setTimeout(() => {
            window.location.href = '/logout/';
        }, 10000);
    }

    // Method to update token info if refreshed
    updateTokenInfo(tokenInfo) {
        window.tapisTokenInfo = tokenInfo;
        this.warningShown = false;
        
        if (!this.checkInterval) {
            this.startTokenMonitoring();
        }
    }

    // Method to stop monitoring (when user logs out manually)
    stopMonitoring() {
        if (this.checkInterval) {
            clearInterval(this.checkInterval);
            this.checkInterval = null;
        }
        $('#tapis-token-warning').remove();
    }
}

// Initialize the token manager
$(document).ready(() => {
    window.tapisTokenManager = new TapisTokenManager();
});

export default TapisTokenManager;