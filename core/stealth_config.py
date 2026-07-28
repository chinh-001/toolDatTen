"""
Stealth Configuration Module - Cấu hình chống phát hiện automation cho trình duyệt.
Chứa tất cả Chrome launch arguments và JavaScript init scripts để bypass
các hệ thống anti-bot của Google (Gemini, Accounts, v.v.).
"""


def get_stealth_launch_args(profile_folder="Default"):
    """
    Trả về danh sách Chrome launch arguments tối ưu cho stealth.

    Args:
        profile_folder (str): Tên thư mục profile ("Default", "Profile 1", ...).

    Returns:
        list: Danh sách các argument dạng string.
    """
    return [
        f"--profile-directory={profile_folder}",

        # === Chống phát hiện automation ===
        "--disable-blink-features=AutomationControlled",
        "--disable-features=AutomationControlled,TranslateUI",

        # === Tắt các UI gây nhiễu ===
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-search-engine-choice-screen",
        "--disable-infobars",
        "--disable-background-timer-throttling",

        # === Fix profile lock issues ===
        "--disable-features=LockProfileCookieDatabase",

        # === Giảm fingerprint khác biệt ===
        "--disable-component-extensions-with-background-pages",
        "--disable-default-apps",
        "--disable-extensions-file-access-check",

        # === Giả lập trình duyệt thật ===
        "--lang=vi-VN,vi,en-US,en",
        "--disable-dev-shm-usage",
    ]


def get_stealth_ignore_args():
    """
    Trả về danh sách các default args của Playwright/Patchright cần bỏ qua.
    Các args này làm lộ automation.

    Returns:
        list: Danh sách argument cần ignore.
    """
    return [
        "--enable-automation",
        "--disable-sync",
        "--disable-component-extensions-with-background-pages",
        "--disable-default-apps",
    ]


def get_stealth_init_script():
    """
    Trả về JavaScript init script toàn diện để patch tất cả các dấu hiệu automation.
    Script này chạy TRƯỚC mọi script khác trên trang.

    Returns:
        str: JavaScript code dạng string.
    """
    return """
    // ============================================================
    // STEALTH INIT SCRIPT - Chống phát hiện automation toàn diện
    // ============================================================

    // 1. Patch navigator.webdriver (quan trọng nhất)
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
        configurable: true
    });

    // 2. Patch chrome.runtime (Google kiểm tra object này)
    if (!window.chrome) {
        window.chrome = {};
    }
    if (!window.chrome.runtime) {
        window.chrome.runtime = {
            connect: function() { return {}; },
            sendMessage: function() {},
            onMessage: {
                addListener: function() {},
                removeListener: function() {},
                hasListener: function() { return false; }
            },
            id: undefined
        };
    }

    // 3. Patch chrome.app (một số trang kiểm tra)
    if (!window.chrome.app) {
        window.chrome.app = {
            isInstalled: false,
            InstallState: {
                DISABLED: 'disabled',
                INSTALLED: 'installed',
                NOT_INSTALLED: 'not_installed'
            },
            RunningState: {
                CANNOT_RUN: 'cannot_run',
                READY_TO_RUN: 'ready_to_run',
                RUNNING: 'running'
            },
            getDetails: function() { return null; },
            getIsInstalled: function() { return false; },
            installState: function() { return 'not_installed'; }
        };
    }

    // 4. Patch chrome.csi (Chrome Client-Side Instrumentation)
    if (!window.chrome.csi) {
        window.chrome.csi = function() {
            return {
                startE: Date.now(),
                onloadT: Date.now(),
                pageT: Math.random() * 1000 + 500,
                tran: 15
            };
        };
    }

    // 5. Patch chrome.loadTimes
    if (!window.chrome.loadTimes) {
        window.chrome.loadTimes = function() {
            return {
                commitLoadTime: Date.now() / 1000,
                connectionInfo: 'h2',
                finishDocumentLoadTime: Date.now() / 1000,
                finishLoadTime: Date.now() / 1000,
                firstPaintAfterLoadTime: 0,
                firstPaintTime: Date.now() / 1000,
                navigationType: 'Other',
                npnNegotiatedProtocol: 'h2',
                requestTime: Date.now() / 1000 - 0.16,
                startLoadTime: Date.now() / 1000,
                wasAlternateProtocolAvailable: false,
                wasFetchedViaSpdy: true,
                wasNpnNegotiated: true
            };
        };
    }

    // 6. Patch navigator.plugins (headless thiếu plugins)
    if (navigator.plugins.length === 0) {
        const fakePluginData = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer',
              description: 'Portable Document Format',
              mimeType: { type: 'application/x-google-chrome-pdf', suffixes: 'pdf' }
            },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai',
              description: '', mimeType: { type: 'application/pdf', suffixes: 'pdf' }
            },
            { name: 'Native Client', filename: 'internal-nacl-plugin',
              description: '',
              mimeType: { type: 'application/x-nacl', suffixes: '' }
            }
        ];

        const fakePluginArray = Object.create(PluginArray.prototype);
        for (let i = 0; i < fakePluginData.length; i++) {
            const fp = fakePluginData[i];
            const plugin = Object.create(Plugin.prototype);
            Object.defineProperties(plugin, {
                name: { value: fp.name },
                filename: { value: fp.filename },
                description: { value: fp.description },
                length: { value: 1 }
            });
            fakePluginArray[i] = plugin;
        }

        Object.defineProperty(fakePluginArray, 'length', {
            value: fakePluginData.length
        });

        Object.defineProperty(navigator, 'plugins', {
            get: () => fakePluginArray,
            configurable: true
        });
    }

    // 7. Patch navigator.languages
    Object.defineProperty(navigator, 'languages', {
        get: () => ['vi-VN', 'vi', 'en-US', 'en'],
        configurable: true
    });

    // 8. Patch Permissions API (chặn phát hiện qua notification permission)
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = function(parameters) {
        if (parameters.name === 'notifications') {
            return Promise.resolve({ state: Notification.permission });
        }
        return originalQuery.call(this, parameters);
    };

    // 9. Patch WebGL renderer (headless dùng SwiftShader - bị detect)
    const getParameterProto = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        // UNMASKED_VENDOR_WEBGL
        if (parameter === 37445) {
            return 'Google Inc. (NVIDIA)';
        }
        // UNMASKED_RENDERER_WEBGL
        if (parameter === 37446) {
            return 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0, D3D11)';
        }
        return getParameterProto.call(this, parameter);
    };

    // Patch WebGL2 tương tự
    if (typeof WebGL2RenderingContext !== 'undefined') {
        const getParameterProto2 = WebGL2RenderingContext.prototype.getParameter;
        WebGL2RenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) {
                return 'Google Inc. (NVIDIA)';
            }
            if (parameter === 37446) {
                return 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0, D3D11)';
            }
            return getParameterProto2.call(this, parameter);
        };
    }

    // 10. Patch iframe contentWindow detection
    // Một số anti-bot inject iframe rỗng rồi check contentWindow.chrome
    try {
        const iframeProto = HTMLIFrameElement.prototype;
        const origContentWindow = Object.getOwnPropertyDescriptor(iframeProto, 'contentWindow');
        if (origContentWindow) {
            Object.defineProperty(iframeProto, 'contentWindow', {
                get: function() {
                    const win = origContentWindow.get.call(this);
                    if (win) {
                        try {
                            if (!win.chrome) win.chrome = window.chrome;
                        } catch(e) {}
                    }
                    return win;
                }
            });
        }
    } catch(e) {}

    // 11. Ẩn Playwright/Automation stack trace
    // Override Error.prototype.stack để loại bỏ các dòng chứa 'playwright', 'patchright', 'puppeteer'
    const originalStackDescriptor = Object.getOwnPropertyDescriptor(Error.prototype, 'stack');
    if (originalStackDescriptor && originalStackDescriptor.get) {
        Object.defineProperty(Error.prototype, 'stack', {
            get: function() {
                const stack = originalStackDescriptor.get.call(this);
                if (typeof stack === 'string') {
                    return stack.split('\\n').filter(line => {
                        const lower = line.toLowerCase();
                        return !lower.includes('playwright') &&
                               !lower.includes('patchright') &&
                               !lower.includes('puppeteer') &&
                               !lower.includes('__playwright');
                    }).join('\\n');
                }
                return stack;
            },
            configurable: true
        });
    }

    // 12. Patch console.debug detection (một số trang dùng console.debug để phát hiện DevTools)
    // Giữ nguyên hành vi nhưng ẩn automation markers
    """
