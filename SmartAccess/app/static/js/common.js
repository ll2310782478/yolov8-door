/* SmartAccess 公共函数库 */

/**
 * 切换侧边栏展开/折叠状态
 */
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (sidebar) {
        sidebar.classList.toggle('collapsed');
        // 保存用户偏好
        localStorage.setItem('sidebar-collapsed', 
            sidebar.classList.contains('collapsed') ? 'true' : 'false');
    }
}

/**
 * 用户登出
 */
function logout() {
    if (confirm('确定要退出登录吗？')) {
        // 清除本地存储的 Token
        localStorage.removeItem('smartaccess_token');
        localStorage.removeItem('smartaccess_username');
        // 跳转到登录页
        window.location.href = '/web/auth';
    }
}

/**
 * 显示提示信息
 * @param {string} message - 提示信息
 * @param {string} type - 类型: success, error, warning, info
 * @param {number} duration - 显示时长（毫秒）
 */
function showToast(message, type = 'success', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease-out reverse';
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, duration);
}

/**
 * 显示警告消息
 * @param {string} message - 消息内容
 * @param {string} type - 类型: success, danger, warning, info
 */
function showAlert(message, type = 'info') {
    const alertArea = document.getElementById('alertArea');
    if (!alertArea) return;
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.innerHTML = `
        <span>${message}</span>
        <button class="alert-close" onclick="this.parentElement.remove()">×</button>
    `;
    
    alertArea.insertBefore(alert, alertArea.firstChild);
    
    // 5秒后自动关闭
    setTimeout(() => {
        if (alert.parentElement) {
            alert.remove();
        }
    }, 5000);
}

/**
 * 显示确认对话框
 * @param {string} message - 确认消息
 * @param {Function} onConfirm - 确认回调
 * @param {Function} onCancel - 取消回调
 */
function showConfirm(message, onConfirm, onCancel) {
    if (confirm(message)) {
        onConfirm && onConfirm();
    } else {
        onCancel && onCancel();
    }
}

/**
 * 获取API请求基础配置
 * @returns {object} 基础配置对象
 */
function getApiConfig() {
    return {
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    };
}

/**
 * 获取认证请求头
 * @param {object} extra - 额外的请求头
 * @returns {object} 包含 Authorization 的请求头对象
 */
function authHeaders(extra = {}) {
    const token = localStorage.getItem('smartaccess_token');
    return token ? { 'Authorization': `Bearer ${token}`, ...extra } : { ...extra };
}

/**
 * API GET请求
 * @param {string} url - 请求URL
 * @returns {Promise} 返回Promise
 */
async function apiGet(url) {
    try {
        const response = await fetch(url, {
            method: 'GET',
            ...getApiConfig()
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('GET请求失败:', error);
        showToast(`请求失败: ${error.message}`, 'error');
        throw error;
    }
}

/**
 * API POST请求
 * @param {string} url - 请求URL
 * @param {object} data - 请求数据
 * @returns {Promise} 返回Promise
 */
async function apiPost(url, data) {
    try {
        const response = await fetch(url, {
            method: 'POST',
            ...getApiConfig(),
            body: JSON.stringify(data)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('POST请求失败:', error);
        showToast(`请求失败: ${error.message}`, 'error');
        throw error;
    }
}

/**
 * API PUT请求
 * @param {string} url - 请求URL
 * @param {object} data - 请求数据
 * @returns {Promise} 返回Promise
 */
async function apiPut(url, data) {
    try {
        const response = await fetch(url, {
            method: 'PUT',
            ...getApiConfig(),
            body: JSON.stringify(data)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('PUT请求失败:', error);
        showToast(`请求失败: ${error.message}`, 'error');
        throw error;
    }
}

/**
 * API DELETE请求
 * @param {string} url - 请求URL
 * @returns {Promise} 返回Promise
 */
async function apiDelete(url) {
    try {
        const response = await fetch(url, {
            method: 'DELETE',
            ...getApiConfig()
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('DELETE请求失败:', error);
        showToast(`请求失败: ${error.message}`, 'error');
        throw error;
    }
}

/**
 * UTC时间转换为本地时间（东八区）
 * @param {string} dateStr - UTC时间字符串
 * @returns {object|null} 返回{utc, display}对象或null
 */
function parseUtcPlus8(dateStr) {
    if (!dateStr) return null;
    
    const utc = new Date(dateStr.endsWith('Z') ? dateStr : `${dateStr}Z`);
    if (isNaN(utc.getTime())) return null;
    
    const display = new Date(utc.getTime() + 8 * 3600 * 1000);
    return { utc, display };
}

/**
 * 格式化日期时间
 * @param {Date} date - 日期对象
 * @param {string} format - 格式字符串 (默认: 'YYYY-MM-DD HH:mm:ss')
 * @returns {string} 格式化后的日期字符串
 */
function formatDate(date, format = 'YYYY-MM-DD HH:mm:ss') {
    if (!(date instanceof Date)) {
        date = new Date(date);
    }
    
    const pad = (num) => String(num).padStart(2, '0');
    
    const replacements = {
        'YYYY': date.getFullYear(),
        'MM': pad(date.getMonth() + 1),
        'DD': pad(date.getDate()),
        'HH': pad(date.getHours()),
        'mm': pad(date.getMinutes()),
        'ss': pad(date.getSeconds())
    };
    
    let result = format;
    for (const [key, value] of Object.entries(replacements)) {
        result = result.replace(key, value);
    }
    
    return result;
}

/**
 * 计算两个日期之间的时间差
 * @param {Date|string} start - 开始时间
 * @param {Date|string} end - 结束时间
 * @returns {object} 返回{days, hours, minutes, seconds}
 */
function getTimeDiff(start, end) {
    const startDate = new Date(start);
    const endDate = new Date(end);
    
    const diffMs = Math.abs(endDate - startDate);
    const seconds = Math.floor(diffMs / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    return {
        days,
        hours: hours % 24,
        minutes: minutes % 60,
        seconds: seconds % 60,
        total: diffMs
    };
}

/**
 * 获取相对时间显示（如"5分钟前"）
 * @param {Date|string} date - 日期
 * @returns {string} 相对时间字符串
 */
function getRelativeTime(date) {
    const now = new Date();
    const targetDate = new Date(date);
    const diffMs = now - targetDate;
    
    if (diffMs < 0) {
        return '刚刚';
    }
    
    const seconds = Math.floor(diffMs / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    if (seconds < 60) {
        return '刚刚';
    } else if (minutes < 60) {
        return `${minutes}分钟前`;
    } else if (hours < 24) {
        return `${hours}小时前`;
    } else if (days < 30) {
        return `${days}天前`;
    } else {
        return formatDate(targetDate, 'YYYY-MM-DD');
    }
}

/**
 * 打开模态框
 * @param {string} modalId - 模态框元素ID
 */
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('show');
    }
}

/**
 * 关闭模态框
 * @param {string} modalId - 模态框元素ID
 */
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('show');
    }
}

/**
 * 刷新页面
 */
function refreshPage() {
    location.reload();
}

/**
 * 返回上一页
 */
function goBack() {
    window.history.back();
}

/**
 * 复制文本到剪贴板
 * @param {string} text - 要复制的文本
 */
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast('已复制到剪贴板', 'success', 2000);
    } catch (error) {
        console.error('复制失败:', error);
        showToast('复制失败', 'error');
    }
}

/**
 * 下载文件
 * @param {string} url - 文件URL
 * @param {string} filename - 文件名
 */
function downloadFile(url, filename) {
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || 'download';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

/**
 * 验证电子邮件
 * @param {string} email - 邮箱地址
 * @returns {boolean} 是否有效
 */
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

/**
 * 验证电话号码
 * @param {string} phone - 电话号码
 * @returns {boolean} 是否有效
 */
function isValidPhone(phone) {
    const phoneRegex = /^1[3-9]\d{9}$/;
    return phoneRegex.test(phone);
}

/**
 * 生成随机ID
 * @param {number} length - 长度
 * @returns {string} 随机ID
 */
function generateId(length = 8) {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let id = '';
    for (let i = 0; i < length; i++) {
        id += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return id;
}

/**
 * 深拷贝对象
 * @param {object} obj - 对象
 * @returns {object} 拷贝后的对象
 */
function deepCopy(obj) {
    return JSON.parse(JSON.stringify(obj));
}

/**
 * 初始化页面
 * 在页面加载完成后自动执行
 */
function initPage() {
    // 恢复侧边栏状态
    const sidebarCollapsed = localStorage.getItem('sidebar-collapsed') === 'true';
    const sidebar = document.getElementById('sidebar');
    if (sidebar && sidebarCollapsed) {
        sidebar.classList.add('collapsed');
    }
    
    // 添加全局错误处理
    window.addEventListener('error', (event) => {
        console.error('全局错误:', event.error);
        showToast(`错误: ${event.error.message}`, 'error');
    });
    
    // 添加网络状态监听
    window.addEventListener('offline', () => {
        showToast('网络已断开连接', 'warning');
    });
    
    window.addEventListener('online', () => {
        showToast('网络已连接', 'success', 2000);
    });
}

/**
 * 页面加载完成时初始化
 */
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPage);
} else {
    initPage();
}

/**
 * 添加按键快捷键支持
 * Alt+Q: 返回上一页
 * Alt+L: 刷新页面
 * Alt+M: 打开侧边栏菜单
 */
document.addEventListener('keydown', (e) => {
    if (e.altKey) {
        if (e.key === 'q' || e.key === 'Q') {
            e.preventDefault();
            goBack();
        } else if (e.key === 'l' || e.key === 'L') {
            e.preventDefault();
            refreshPage();
        } else if (e.key === 'm' || e.key === 'M') {
            e.preventDefault();
            toggleSidebar();
        }
    }
});
