/**
 * Smart Metrics Dashboard Enhancement
 * Addresses API errors, SSL issues, and provides intelligent refresh logic
 */
class SmartMetricsManager {
    constructor() {
        this.refreshMode = 'smart'; // smart, auto, manual
        this.refreshInterval = null;
        this.lastDataHash = null;
        this.refreshTimer = 30;
        this.isLoading = false;
        this.refreshInProgress = false; // NEW: Prevent concurrent refreshes
        this.retryCount = 0;
        this.maxRetries = 3;
        this.apiErrors = new Map();
        this.lastSuccessfulUpdate = null;
        this.backoffMultiplier = 1;
        
        // Performance tracking
        this.performanceMetrics = {
            totalRequests: 0,
            successfulRequests: 0,
            failedRequests: 0,
            avgResponseTime: 0
        };
        
        this.init();
    }

    init() {
        this.loadInitialMetrics();
        this.startIntelligentRefresh();
        this.setupVisibilityHandling();
        this.setupErrorRecovery();
        
        console.log('🚀 Smart Metrics Manager initialized');
    }

    async loadInitialMetrics() {
        // Load with progressive enhancement
        try {
            await this.loadBasicMetrics();
            await this.loadEngagementMetrics();
            this.updateHealthStatus('success', 'All metrics loaded');
        } catch (error) {
            console.error('Initial load failed:', error);
            this.handleApiError(error);
        }
    }

    async loadBasicMetrics() {
        const startTime = Date.now();
        
        try {
            // Use the new smart overview endpoint
            const response = await fetch('/api/v1/metrics/smart-overview', {
                headers: {
                    'Cache-Control': 'no-cache',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            
            // Update performance metrics
            this.performanceMetrics.totalRequests++;
            this.performanceMetrics.successfulRequests++;
            this.performanceMetrics.avgResponseTime = 
                (this.performanceMetrics.avgResponseTime + (Date.now() - startTime)) / 2;

            // Update UI with basic metrics
            this.updateBasicMetricsUI(data);
            
            // Update refresh recommendations
            this.updateRefreshStrategy(data.smart_refresh_recommendations);
            
            this.lastSuccessfulUpdate = Date.now();
            this.resetBackoff();

            return data;

        } catch (error) {
            this.performanceMetrics.failedRequests++;
            throw error;
        }
    }

    async loadEngagementMetrics() {
        // Only load engagement if not too many recent API errors
        const recentErrors = Array.from(this.apiErrors.values())
            .filter(error => Date.now() - error.lastOccurred < 300000); // 5 minutes

        if (recentErrors.length > 5) {
            console.log('⏭️ Skipping engagement refresh due to recent API errors');
            return;
        }

        try {
            const response = await fetch('/api/v1/metrics/engagement');
            if (response.ok) {
                const data = await response.json();
                this.updateEngagementUI(data);
            }
        } catch (error) {
            console.warn('Engagement metrics failed:', error);
            this.trackApiError('engagement', error);
        }
    }

    updateBasicMetricsUI(data) {
        // Enhanced number animations with error handling - Fixed IDs to match HTML
        this.safeUpdateNumber('total-comments', data.total_comments_posted || 0);
        this.safeUpdateNumber('total-videos', data.total_videos_processed || 0);
        this.safeUpdateNumber('total-engagement', data.total_engagement || 0);
        this.safeUpdateNumber('deleted-comments', data.deleted_comments || 0);
        
        // Update agent statistics with enhanced display
        this.updateAgentStatsUI(data.agent_statistics || {});
        
        // Update performance indicators
        this.updatePerformanceIndicators(data.api_health || {});
    }

    updateEngagementUI(data) {
        this.safeUpdateNumber('totalLikes', data.total_likes || 0);
        this.safeUpdateNumber('totalReplies', data.total_replies || 0);
        
        // Update videos list with smart error handling  
        this.updateVideosListUI(data.video_details || []);
    }

    updatePerformanceIndicators(apiHealth) {
        // Update API health indicators and performance metrics
        const healthStatus = apiHealth.status || 'unknown';
        const responseTime = apiHealth.avg_response_time || 0;
        const successRate = apiHealth.success_rate || 0;
        
        // Update health status indicator
        this.updateHealthStatus('api', healthStatus);
        
        // Update performance stats if elements exist
        const responseTimeElement = document.getElementById('avgResponseTime');
        if (responseTimeElement) {
            responseTimeElement.textContent = `${responseTime.toFixed(0)}ms`;
        }
        
        const apiSuccessElement = document.getElementById('apiSuccessRate');
        if (apiSuccessElement) {
            apiSuccessElement.textContent = `${successRate.toFixed(1)}%`;
        }
    }

    updateRefreshStrategy(refreshRecommendations) {
        // Update refresh strategy based on server recommendations
        if (!refreshRecommendations) return;
        
        const { recommended_interval, strategy, last_analysis } = refreshRecommendations;
        
        // Update refresh interval if recommended
        if (recommended_interval && recommended_interval !== this.currentRefreshInterval) {
            this.currentRefreshInterval = recommended_interval;
            console.log(`🔄 Updated refresh interval to ${recommended_interval}ms based on server recommendations`);
        }
        
        // Apply strategy adjustments
        if (strategy) {
            switch(strategy) {
                case 'aggressive':
                    this.backoffMultiplier = Math.max(this.backoffMultiplier * 0.8, 1.0);
                    break;
                case 'conservative':
                    this.backoffMultiplier = Math.min(this.backoffMultiplier * 1.2, 5.0);
                    break;
                case 'adaptive':
                    // Keep current strategy
                    break;
            }
        }
        
        // Log strategy updates for debugging
        if (last_analysis) {
            console.log(`📊 Refresh strategy: ${strategy || 'default'}, Analysis: ${last_analysis}`);
        }
    }

    updateAgentStatsUI(agentStats) {
        const agentContainer = document.getElementById('agents-container');
        if (!agentContainer) return;

        const agentCards = Object.entries(agentStats).map(([agentName, stats]) => {
            const successRate = stats.success_rate || 0;
            const displayName = this.formatAgentName(agentName);
            const subtitle = this.getAgentSubtitle(agentName);
            const primaryValue = stats.videos_processed || stats.comments_posted || 0;
            
            return `
                <div class="agent-card">
                    <img src="/favicon.ico" alt="Agent" class="agent-icon" />
                    <span class="agent-name">${displayName}</span>
                    <div class="agent-value">${primaryValue.toLocaleString()}</div>
                    <div class="agent-subtitle">${subtitle}</div>
                    <div class="success-rate ${this.getSuccessClass(successRate)}">
                        ${successRate.toFixed(0)}%
                    </div>
                </div>
            `;
        }).join('');

        agentContainer.innerHTML = agentCards;
    }

    updateVideosListUI(videos) {
        const videosContainer = document.getElementById('videos-container');
        if (!videosContainer) return;

        if (!videos || videos.length === 0) {
            videosContainer.innerHTML = this.getEmptyState();
            return;
        }

        // Group videos by engagement status for better UX
        const successfulVideos = videos.filter(v => v.engagement?.status === 'success');
        const errorVideos = videos.filter(v => v.engagement?.status === 'error');
        const unknownVideos = videos.filter(v => !v.engagement?.status || v.engagement.status === 'unknown');

        const videoCards = videos.map((video, index) => {
            const engagement = video.engagement || {};
            const hasError = engagement.status === 'error';
            const isLoading = engagement.status === 'loading';
            
            return `
                <div class="video-card ${hasError ? 'error' : ''} ${isLoading ? 'loading' : ''}" 
                     style="animation-delay: ${index * 0.1}s">
                    <div class="video-header">
                        <div class="video-thumbnail">
                            ${video.thumbnail_url ? 
                                `<img src="${video.thumbnail_url}" alt="Video thumbnail" style="width: 100%; height: 100%; object-fit: cover; border-radius: 12px;">` :
                                `<svg class="play-icon" viewBox="0 0 24 24" fill="currentColor">
                                    <path d="M8 5v14l11-7z"/>
                                </svg>`
                            }
                        </div>
                        <div class="video-info">
                            <h3 class="video-title">${this.escapeHtml(video.video_title || 'Unknown Video')}</h3>
                            <div class="video-meta">
                                <span>${this.formatDate(video.posted_at)}</span>
                                ${hasError ? '<span class="error-indicator">• ⚠️ API Error</span>' : ''}
                            </div>
                        </div>
                    </div>
                    
                    <div class="comment-section">
                        <div class="comment-preview">
                            ${this.escapeHtml((video.comment_text || '').substring(0, 120))}
                            ${(video.comment_text || '').length > 120 ? '...' : ''}
                        </div>
                        
                        <div class="comment-actions">
                            <div class="engagement-stats">
                                <span class="stat">
                                    <svg class="stat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
                                    </svg>
                                    ${engagement.likes || 0}
                                </span>
                                <span class="stat">
                                    <svg class="stat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                                    </svg>
                                    ${engagement.replies || 0}
                                </span>
                                ${hasError ? `
                                    <span class="stat error">
                                        <svg class="stat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                                            <line x1="12" y1="9" x2="12" y2="13"/>
                                            <line x1="12" y1="17" x2="12.01" y2="17"/>
                                        </svg>
                                        Error
                                    </span>
                                ` : ''}
                            </div>
                            
                            <a href="${video.comment_url || '#'}" 
                               target="_blank" 
                               class="comment-link ${!video.comment_url ? 'disabled' : ''}">
                                <svg class="link-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                                    <polyline points="15,3 21,3 21,9"/>
                                    <line x1="10" y1="14" x2="21" y2="3"/>
                                </svg>
                                view
                            </a>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        videosContainer.innerHTML = videoCards;

        // Add summary if there are errors
        if (errorVideos.length > 0) {
            this.showErrorSummary(errorVideos.length, videos.length);
        }
    }

    renderEngagementRing(engagement) {
        const likes = engagement.likes || 0;
        const maxLikes = 100; // Normalize to 100 for visual representation
        const percentage = Math.min((likes / maxLikes) * 100, 100);
        
        return `
            <div class="engagement-ring">
                <svg class="ring-progress" viewBox="0 0 36 36">
                    <path class="ring-bg" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"/>
                    <path class="ring-progress-bar" 
                          stroke-dasharray="${percentage}, 100" 
                          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"/>
                </svg>
                <div class="ring-content">
                    <div class="ring-number">${likes}</div>
                    <div class="ring-label">likes</div>
                </div>
            </div>
        `;
    }

    startIntelligentRefresh() {
        // Clear any existing intervals
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }

        // Smart refresh: adjust frequency based on activity and errors
        this.refreshInterval = setInterval(() => {
            this.intelligentRefreshCheck();
        }, this.calculateRefreshInterval());
    }

    calculateRefreshInterval() {
        // OPTIMIZED: Base interval increased to 2 minutes for better API quota management
        let interval = 120000; // 2 minutes base
        
        // Increase interval if many errors (more aggressive)
        const errorCount = this.apiErrors.size;
        if (errorCount > 3) {
            interval *= 2; // 4 minutes
        }
        if (errorCount > 7) {
            interval *= 3; // 12 minutes
        }
        
        // Less aggressive refresh even with recent activity
        if (this.lastSuccessfulUpdate && Date.now() - this.lastSuccessfulUpdate < 300000) {
            interval = Math.max(interval * 0.8, 60000); // Minimum 1 minute (was 15 seconds)
        }
        
        // Cap maximum interval at 15 minutes
        interval = Math.min(interval * this.backoffMultiplier, 900000);
        
        console.log(`📊 Next refresh in ${Math.round(interval/1000)}s (errors: ${errorCount})`);
        return interval;
    }

    async intelligentRefreshCheck() {
        // Check if we should refresh based on various factors
        const shouldRefresh = await this.shouldPerformRefresh();
        
        if (shouldRefresh) {
            await this.performSmartRefresh();
        } else {
            console.log('⏭️ Skipping refresh cycle - not needed');
        }
    }

    async shouldPerformRefresh() {
        // Don't refresh if page is not visible
        if (document.hidden) {
            return false;
        }
        
        // Don't refresh if currently loading
        if (this.isLoading) {
            return false;
        }
        
        // OPTIMIZED: Increased minimum refresh time to 2 minutes
        if (!this.lastSuccessfulUpdate || Date.now() - this.lastSuccessfulUpdate > 600000) {
            return true; // Always refresh if more than 10 minutes (was 5)
        }
        
        // Check if there might be new data (less frequently)
        try {
            const healthResponse = await fetch('/api/v1/metrics/health');
            if (healthResponse.ok) {
                const health = await healthResponse.json();
                return health.recommendations?.includes('refresh_recommended') || 
                       health.retry_queue_size === 0; // Safe to refresh
            }
        } catch (error) {
            console.log('Health check failed:', error);
        }
        
        return false;
    }

    async performSmartRefresh() {
        // REQUEST DEDUPLICATION: Prevent concurrent requests
        if (this.isLoading || this.refreshInProgress) return;
        
        this.isLoading = true;
        this.refreshInProgress = true; // NEW: Additional flag for deduplication
        this.updateHealthStatus('info', 'Refreshing metrics...');
        
        try {
            // Load basic metrics first (faster) - with timeout
            const basicMetricsPromise = Promise.race([
                this.loadBasicMetrics(),
                new Promise((_, reject) => setTimeout(() => reject(new Error('Basic metrics timeout')), 10000))
            ]);
            
            await basicMetricsPromise;
            
            // Load engagement data with error handling and timeout
            const engagementPromise = Promise.race([
                this.loadEngagementMetrics(),
                new Promise((_, reject) => setTimeout(() => reject(new Error('Engagement metrics timeout')), 15000))
            ]);
            
            await engagementPromise;
            
            this.updateHealthStatus('success', `Updated ${new Date().toLocaleTimeString()}`);
            this.resetBackoff();
            this.lastSuccessfulUpdate = Date.now(); // Track successful updates
            
        } catch (error) {
            console.error('Smart refresh failed:', error);
            this.handleApiError(error);
            this.increaseBackoff();
        } finally {
            this.isLoading = false;
            this.refreshInProgress = false; // NEW: Clear deduplication flag
        }
    }

    trackApiError(context, error) {
        const errorKey = `${context}_${error.message.substring(0, 50)}`;
        
        if (this.apiErrors.has(errorKey)) {
            const existing = this.apiErrors.get(errorKey);
            existing.count++;
            existing.lastOccurred = Date.now();
        } else {
            this.apiErrors.set(errorKey, {
                context,
                message: error.message,
                count: 1,
                firstOccurred: Date.now(),
                lastOccurred: Date.now()
            });
        }
        
        // Clean up old errors (older than 1 hour)
        for (const [key, errorData] of this.apiErrors.entries()) {
            if (Date.now() - errorData.lastOccurred > 3600000) {
                this.apiErrors.delete(key);
            }
        }
    }

    handleApiError(error) {
        this.retryCount++;
        
        if (this.retryCount <= this.maxRetries) {
            const delay = Math.min(1000 * Math.pow(2, this.retryCount), 30000); // Exponential backoff, max 30s
            this.updateHealthStatus('error', `Error occurred. Retrying in ${Math.round(delay/1000)}s... (${this.retryCount}/${this.maxRetries})`);
            
            setTimeout(() => {
                this.performSmartRefresh();
            }, delay);
        } else {
            this.updateHealthStatus('error', 'Multiple failures. Reduced refresh rate.');
            this.increaseBackoff();
            this.retryCount = 0; // Reset for next cycle
        }
    }

    increaseBackoff() {
        this.backoffMultiplier = Math.min(this.backoffMultiplier * 1.5, 4); // Max 4x backoff
        this.startIntelligentRefresh(); // Restart with new interval
    }

    resetBackoff() {
        this.backoffMultiplier = 1;
        this.retryCount = 0;
    }

    setupVisibilityHandling() {
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && this.refreshMode === 'smart') {
                // Page became visible, check if we need to refresh
                const timeSinceLastUpdate = this.lastSuccessfulUpdate ? 
                    (Date.now() - this.lastSuccessfulUpdate) / 1000 : Infinity;
                
                if (timeSinceLastUpdate > 60) {
                    setTimeout(() => this.performSmartRefresh(), 1000);
                }
            }
        });
    }

    setupErrorRecovery() {
        // Periodically clean up error tracking and attempt recovery
        setInterval(() => {
            // Clean up old errors
            const cutoff = Date.now() - 1800000; // 30 minutes
            for (const [key, errorData] of this.apiErrors.entries()) {
                if (errorData.lastOccurred < cutoff) {
                    this.apiErrors.delete(key);
                }
            }
            
            // Attempt to recover if we've been in error state for a while
            if (this.backoffMultiplier > 1 && this.apiErrors.size < 3) {
                console.log('🔄 Attempting error recovery...');
                this.backoffMultiplier = Math.max(this.backoffMultiplier * 0.8, 1);
                this.startIntelligentRefresh();
            }
        }, 300000); // Every 5 minutes
    }

    // Utility functions
    safeUpdateNumber(elementId, value) {
        const element = document.getElementById(elementId);
        if (element && !isNaN(value)) {
            this.animateNumber(element, value);
        }
    }

    animateNumber(element, targetValue, duration = 1000) {
        const startValue = parseInt(element.textContent) || 0;
        const startTime = Date.now();
        
        const updateNumber = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const easeOut = 1 - Math.pow(1 - progress, 3);
            const currentValue = Math.round(startValue + (targetValue - startValue) * easeOut);
            
            element.textContent = currentValue.toLocaleString();
            
            if (progress < 1) {
                requestAnimationFrame(updateNumber);
            }
        };
        
        requestAnimationFrame(updateNumber);
    }

    updateHealthStatus(type, message) {
        const statusElement = document.getElementById('healthStatus');
        if (statusElement) {
            statusElement.className = `health-status ${type}`;
            statusElement.textContent = message;
        }
    }

    formatAgentName(name) {
        // Map technical names to user-friendly names
        const friendlyNames = {
            'channel_parser': 'Video Discovery',
            'content_scraper': 'Content Collector', 
            'content_analyzer': 'Smart Analysis',
            'comment_generator': 'AI Writer',
            'comment_poster': 'Auto Publisher'
        };
        
        return friendlyNames[name] || name.split('_').map(word => 
            word.charAt(0).toUpperCase() + word.slice(1)
        ).join(' ');
    }

    getAgentSubtitle(name) {
        // Map agent names to appropriate subtitles
        const subtitles = {
            'channel_parser': 'channels found',
            'content_scraper': 'videos gathered',
            'content_analyzer': 'videos analyzed',
            'comment_generator': 'comments created',
            'comment_poster': 'comments posted'
        };
        
        return subtitles[name] || 'processed';
    }

    getSuccessClass(rate) {
        if (rate >= 90) return 'success';
        if (rate >= 70) return 'warning';
        return 'error';
    }

    formatDate(dateString) {
        if (!dateString) return 'Unknown';
        const date = new Date(dateString);
        const now = new Date();
        const diffInHours = (now - date) / (1000 * 60 * 60);
        
        if (diffInHours < 1) return 'Just now';
        if (diffInHours < 24) return `${Math.floor(diffInHours)}h ago`;
        const diffInDays = Math.floor(diffInHours / 24);
        return `${diffInDays}d ago`;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    getEmptyState() {
        return `
            <div class="empty-state">
                <div class="empty-icon">📊</div>
                <h3>No Posted Comments Yet</h3>
                <p>Start a workflow to see metrics and engagement data here!</p>
                <button class="refresh-button" onclick="window.smartMetrics.performSmartRefresh()">
                    Check for Updates
                </button>
            </div>
        `;
    }

    showErrorSummary(errorCount, totalCount) {
        const summaryHtml = `
            <div class="error-summary">
                <div class="error-icon">⚠️</div>
                <div class="error-text">
                    <strong>${errorCount} of ${totalCount} comments</strong> have engagement tracking issues.
                    This may be due to API rate limits or deleted comments.
                </div>
                <button class="retry-engagement" onclick="window.smartMetrics.loadEngagementMetrics()">
                    Retry Engagement Data
                </button>
            </div>
        `;
        
        const container = document.getElementById('videos-container');
        container.insertAdjacentHTML('afterbegin', summaryHtml);
    }

    // Public API for manual control
    async manualRefresh() {
        await this.performSmartRefresh();
    }

    getPerformanceStats() {
        return {
            ...this.performanceMetrics,
            apiErrors: this.apiErrors.size,
            backoffMultiplier: this.backoffMultiplier,
            lastUpdate: this.lastSuccessfulUpdate
        };
    }
}

// Auto-initialize when DOM is loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.smartMetrics = new SmartMetricsManager();
    });
} else {
    window.smartMetrics = new SmartMetricsManager();
}

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SmartMetricsManager;
} 