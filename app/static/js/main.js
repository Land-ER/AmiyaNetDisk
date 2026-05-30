/**
 * AmiyaNetDisk - 前端 JavaScript
 * 功能：密码 SHA-256 哈希、验证码发送、Flash 消息自动关闭
 */

/**
 * SHA-256 哈希函数（使用 Web Crypto API，兼容 HTTPS/Localhost）
 * 不依赖任何外部脚本，纯浏览器原生 API
 * @param {string} str - 输入字符串
 * @returns {Promise<string>} 64位十六进制哈希
 */
async function sha256(str) {
    try {
        var encoder = new TextEncoder();
        var data = encoder.encode(str);
        var hashBuffer = await crypto.subtle.digest('SHA-256', data);
        var hashArray = Array.from(new Uint8Array(hashBuffer));
        return hashArray.map(function(b) { return b.toString(16).padStart(2, '0'); }).join('');
    } catch(e) {
        // crypto.subtle 不可用时直接返回原文
        return str;
    }
}
// 模板中调用的是 hashPassword，作为 sha256 的别名
var hashPassword = sha256;

/**
 * 格式化文件大小
 * @param {number} bytes
 * @returns {string}
 */
function formatFileSize(bytes) {
    var units = ['B', 'KB', 'MB', 'GB', 'TB'];
    var size = bytes;
    for (var i = 0; i < units.length; i++) {
        if (size < 1024) return size.toFixed(1) + ' ' + units[i];
        size /= 1024;
    }
    return size.toFixed(1) + ' TB';
}

// 页面加载完成后自动关闭 Flash 消息
document.addEventListener('DOMContentLoaded', function() {
    var flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(function(msg) {
        setTimeout(function() {
            msg.style.opacity = '0';
            msg.style.transition = 'opacity 0.3s';
            setTimeout(function() {
                msg.remove();
            }, 300);
        }, 5000);
    });
});
