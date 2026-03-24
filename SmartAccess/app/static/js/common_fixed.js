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
        // 清除本地存储的Token
        localStorage.removeItem('token');
        localStorage.removeItem('username');
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
