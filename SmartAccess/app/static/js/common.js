/* SmartAccess 公共函数库 */

/**
 * 获取带 Authorization 的请求头
 * @param {object} extra - 额外的头部字段
 * @returns {object} 包含 Authorization 的 headers 对象
 */
function authHeaders(extra = {}) {
    const token = localStorage.getItem('token');
    const headers = {};
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    return { ...headers, ...extra };
}

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
        // 清除本地存储的Token
        localStorage.removeItem('token');
        localStorage.removeItem('username');
        localStorage.removeItem('role');
        // 跳转到登录页
        window.location.href = '/web/auth';
    }
}

/**
 * 显示提示信息
 * @param {string} message - 提示信息
 * @param {string} type - 类型：success, error, warning, info
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
 * @param {string} type - 类型：success, danger, warning, info
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
    
    // 5 秒后自动关闭
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
 * 获取API 请求基础配置
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
 * 根据用户角色控制侧边栏导航可见性
 * admin: 所有功能
 * access_user: 仅仪表盘（无数据权限，展示欢迎页）
 * 在每个页面 DOMContentLoaded 后自动执行
 */
function applyRoleNavigation() {
    const role = localStorage.getItem('role') || 'access_user';
    // 管理员可见所有
    if (role === 'admin') return;

    // 门禁用户：只保留仪表盘，其他隐藏
    const adminOnlyPages = [
        '/web/users', '/web/visitors', '/web/face', '/web/hardware',
        '/web/nfc', '/web/bluetooth', '/web/remote-door', '/web/logs',
        '/web/settings', '/docs'
    ];
    document.querySelectorAll('.nav-item').forEach(item => {
        const link = item.querySelector('a');
        if (link) {
            const href = link.getAttribute('href');
            if (adminOnlyPages.some(p => href && href.startsWith(p))) {
                item.style.display = 'none';
            }
        }
    });

    // 如果当前页面不是仪表盘，且非管理员，跳转到仪表盘
    const currentPath = window.location.pathname;
    if (adminOnlyPages.some(p => currentPath.startsWith(p))) {
        window.location.href = '/web/dashboard';
    }
}

// 页面加载后自动应用角色导航
document.addEventListener('DOMContentLoaded', applyRoleNavigation);
